"""Background cleanup manager for storage."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from ..core.database import Database
from ..jobs import JobStatus
from .config import StorageConfig
from .service import StorageService

logger = logging.getLogger(__name__)


class CleanupManager:
    """Manager for periodic file cleanup tasks."""

    def __init__(self):
        self.storage = StorageService()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the cleanup background task."""
        if self.running:
            logger.warning("Cleanup manager already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"Cleanup manager started (interval: {StorageConfig.cleanup_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the cleanup background task."""
        global _cleanup_manager

        if not self.running:
            # Reset singleton even if not running (for clean restart)
            _cleanup_manager = None
            return

        self.running = False
        self._shutdown_event.set()

        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Cleanup task stop timeout, cancelling")
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                # Handle cancellation during shutdown (e.g., Ctrl+C)
                if self.task and not self.task.done():
                    self.task.cancel()
                    try:
                        await self.task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.error(f"Error during cleanup stop: {e}")

        # Reset singleton for clean restart
        _cleanup_manager = None
        logger.info("Cleanup manager stopped")

    async def _cleanup_loop(self) -> None:
        """Main cleanup loop."""
        while self.running:
            try:
                await self.run_cleanup()
            except asyncio.CancelledError:
                logger.debug("Cleanup cycle cancelled during shutdown")
                return
            except Exception as e:
                logger.error(f"Cleanup cycle failed: {e}")

            # Wait for next cycle or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=StorageConfig.cleanup_interval
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                continue  # Continue to next cleanup cycle
            except asyncio.CancelledError:
                logger.debug("Cleanup loop cancelled during shutdown")
                return

    async def run_cleanup(self) -> dict:
        """
        Run a single cleanup cycle.

        Returns:
            Dict with cleanup statistics
        """
        logger.info("Starting cleanup cycle")
        stats = {
            "old_msf": 0,
            "old_pdf": 0,
            "orphaned": 0,
            "failed_jobs": 0,
            "errors": [],
        }

        try:
            # Clean old MSF files
            msf_count = await self._cleanup_old_files(
                StorageConfig.output_dir,
                StorageConfig.msf_retention_hours,
                [".msf", ".xml"],
            )
            stats["old_msf"] = msf_count

            # Clean old PDF files (shorter retention)
            pdf_count = await self._cleanup_old_files(
                StorageConfig.upload_dir,
                StorageConfig.pdf_retention_hours,
                [".pdf"],
            )
            stats["old_pdf"] = pdf_count

            # Clean orphaned files
            orphan_count = await self._cleanup_orphaned_files()
            stats["orphaned"] = orphan_count

            # Clean old job records
            job_count = await self._cleanup_old_jobs()
            stats["failed_jobs"] = job_count

            # Clean temp directory
            await self._cleanup_temp_files()

            logger.info(
                f"Cleanup completed: {msf_count} MSF, {pdf_count} PDF, "
                f"{orphan_count} orphaned, {job_count} jobs"
            )

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            stats["errors"].append(str(e))

        return stats

    async def _cleanup_old_files(
        self, directory: Path, retention_hours: int, extensions: List[str]
    ) -> int:
        """
        Clean files older than retention period.

        Args:
            directory: Directory to clean
            retention_hours: Hours to retain files
            extensions: File extensions to clean

        Returns:
            Number of files deleted
        """
        if not directory.exists():
            return 0

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        deleted_count = 0

        try:
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue

                if file_path.suffix.lower() not in extensions:
                    continue

                # Check file age
                try:
                    stat = file_path.stat()
                    modified_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                    if modified_time < cutoff_time:
                        await self.storage.delete_file(str(file_path))
                        deleted_count += 1

                        # Batch processing to avoid blocking
                        if deleted_count % StorageConfig.cleanup_batch_size == 0:
                            await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")

        except Exception as e:
            logger.error(f"Directory cleanup failed for {directory}: {e}")

        return deleted_count

    async def _cleanup_orphaned_files(self) -> int:
        """
        Clean files without associated job records.

        Returns:
            Number of orphaned files deleted
        """
        deleted_count = 0
        pool = Database.get_pool()

        try:
            async with pool.acquire() as conn:
                # Get all active job file paths
                cursor = await conn.execute(
                    """
                    SELECT pdf_path, msf_path
                    FROM jobs
                    WHERE status NOT IN ('cancelled', 'failed')
                    """
                )
                rows = await cursor.fetchall()

                active_paths = set()
                for row in rows:
                    if row[0]:
                        active_paths.add(Path(row[0]))
                    if row[1]:
                        active_paths.add(Path(row[1]))

            # Check upload directory
            if StorageConfig.upload_dir.exists():
                for file_path in StorageConfig.upload_dir.glob("*.pdf"):
                    if file_path not in active_paths:
                        # Check if file is old enough (grace period)
                        stat = file_path.stat()
                        age_hours = (
                            datetime.now(timezone.utc) - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        ).total_seconds() / 3600

                        if age_hours > 2:  # 2 hour grace period
                            await self.storage.delete_file(str(file_path))
                            deleted_count += 1
                            logger.info(f"Deleted orphaned file: {file_path}")

            # Check output directory
            if StorageConfig.output_dir.exists():
                for file_path in StorageConfig.output_dir.glob("*.msf"):
                    if file_path not in active_paths:
                        await self.storage.delete_file(str(file_path))
                        deleted_count += 1
                        logger.info(f"Deleted orphaned file: {file_path}")

        except Exception as e:
            logger.error(f"Orphaned file cleanup failed: {e}")

        return deleted_count

    async def _cleanup_old_jobs(self) -> int:
        """
        Clean old failed/cancelled job records.

        Returns:
            Number of job records deleted
        """
        pool = Database.get_pool()
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)  # Keep for 7 days

        try:
            async with pool.acquire() as conn:
                # Delete old failed/cancelled jobs
                cursor = await conn.execute(
                    """
                    DELETE FROM jobs
                    WHERE status IN ('failed', 'cancelled')
                    AND created_at < ?
                    """,
                    (cutoff_time.isoformat(),),
                )
                deleted_count = cursor.rowcount
                await conn.commit()

                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} old job records")

                return deleted_count

        except Exception as e:
            logger.error(f"Job cleanup failed: {e}")
            return 0

    async def _cleanup_temp_files(self) -> None:
        """Clean temporary files."""
        if not StorageConfig.temp_dir.exists():
            return

        try:
            # Clean any .tmp files older than 1 hour
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            for temp_file in StorageConfig.temp_dir.glob("*.tmp"):
                try:
                    stat = temp_file.stat()
                    if datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc) < cutoff_time:
                        temp_file.unlink()
                        logger.debug(f"Deleted temp file: {temp_file}")
                except Exception as e:
                    logger.error(f"Failed to delete temp file {temp_file}: {e}")

        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}")


# Singleton instance
_cleanup_manager: Optional[CleanupManager] = None


def get_cleanup_manager() -> CleanupManager:
    """Get or create the cleanup manager singleton."""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = CleanupManager()
    return _cleanup_manager