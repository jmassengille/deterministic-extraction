"""High-level file management with job integration."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any

from ..core.database import Database, transaction
from ..jobs import JobService, JobCreate, JobUpdate, JobStatus
from ..common.exceptions import JobNotFoundException, JobStateException
from .service import StorageService
from .exceptions import StorageException, FileValidationError

logger = logging.getLogger(__name__)


class FileManager:
    """Manager for file operations with job tracking."""

    def __init__(self):
        self.storage = StorageService()
        self.jobs = JobService()

    async def process_upload(
        self,
        file_content: AsyncIterator[bytes],
        filename: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Process file upload with job creation.

        Args:
            file_content: Async iterator of file chunks
            filename: Original filename
            file_size: Expected file size
            metadata: Optional metadata for job

        Returns:
            Dict with job info and file details

        Raises:
            FileValidationError: Invalid file
            StorageException: Storage operation failed
        """
        pdf_path = None
        job = None

        try:
            # Save file to storage
            pdf_path, file_hash, actual_size = await self.storage.save_upload(
                file_content, filename, file_size
            )

            # Validate PDF
            pdf_metadata = await self.storage.validate_pdf(pdf_path)

            # Extract output_formats from metadata (passed from upload route)
            job_metadata = metadata or {}
            output_formats = job_metadata.pop("output_formats", ["msf"])

            # Create job record with explicit output_formats
            job_data = JobCreate(
                filename=filename,
                file_size=actual_size,
                pdf_path=pdf_path,
                output_formats=output_formats,
                metadata={
                    **job_metadata,
                    "file_hash": file_hash,
                    "pdf_info": pdf_metadata,
                },
            )
            job = await self.jobs.create_job(job_data)

            logger.info(f"Upload processed: {filename} -> Job {job.id}")

            return {
                "job_id": job.id,
                "filename": filename,
                "file_size": actual_size,
                "file_hash": file_hash,
                "pdf_path": pdf_path,
                "pdf_metadata": pdf_metadata,
                "status": job.status,
                "created_at": job.created_at,
            }

        except FileValidationError:
            # Clean up file if validation failed
            if pdf_path:
                await self.storage.delete_file(pdf_path, ignore_missing=True)
            raise
        except Exception as e:
            # Clean up on any error
            if pdf_path:
                await self.storage.delete_file(pdf_path, ignore_missing=True)
            if job:
                try:
                    await self.jobs.update_job(
                        job.id,
                        JobUpdate(
                            status=JobStatus.FAILED,
                            error=str(e),
                            completed_at=datetime.now(timezone.utc),
                        ),
                    )
                except Exception:
                    pass
            logger.error(f"Upload processing failed: {e}")
            raise StorageException(f"Upload processing failed: {e}")

    async def mark_file_processed(
        self, job_id: str, msf_path: str, metadata: Optional[dict] = None
    ) -> None:
        """
        Mark job as processed with MSF output.

        Args:
            job_id: Job ID
            msf_path: Path to generated MSF
            metadata: Optional processing metadata
        """
        try:
            job = await self.jobs.get_job(job_id)

            # Update job with MSF path
            update_data = JobUpdate(
                msf_path=msf_path,
                status=JobStatus.COMPLETED,
                progress=100,
                completed_at=datetime.now(timezone.utc),
            )

            if metadata:
                current_metadata = job.metadata or {}
                current_metadata.update(metadata)
                update_data.metadata = current_metadata

            await self.jobs.update_job(job_id, update_data)
            logger.info(f"Job {job_id} marked as processed with MSF: {msf_path}")

        except JobNotFoundException:
            logger.error(f"Job not found: {job_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to mark job processed: {e}")
            raise StorageException(f"Failed to update job: {e}")

    async def get_download_path(self, job_id: str) -> Optional[str]:
        """
        Get MSF download path for completed job.

        Args:
            job_id: Job ID

        Returns:
            Path to MSF file or None if not ready

        Raises:
            JobNotFoundException: Job not found
            JobStateException: Job not completed
        """
        try:
            job = await self.jobs.get_job(job_id)

            if job.status != JobStatus.COMPLETED:
                raise JobStateException(
                    f"Job not completed: {job.status}",
                    current_state=job.status,
                    expected_state=JobStatus.COMPLETED,
                )

            if not job.msf_path:
                raise StorageException("MSF path not set for completed job")

            # Verify file exists
            if not Path(job.msf_path).exists():
                raise StorageException("MSF file not found", {"path": job.msf_path})

            return job.msf_path

        except (JobNotFoundException, JobStateException):
            raise
        except Exception as e:
            logger.error(f"Failed to get download path: {e}")
            raise StorageException(f"Failed to get download path: {e}")

    async def cancel_and_cleanup(self, job_id: str) -> bool:
        """
        Cancel job and clean up associated files.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled and cleaned up

        Raises:
            JobNotFoundException: Job not found
        """
        try:
            job = await self.jobs.get_job(job_id)

            # Check if job can be cancelled
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                logger.warning(f"Cannot cancel job in status: {job.status}")
                return False

            # Update job status
            await self.jobs.update_job(
                job_id,
                JobUpdate(
                    status=JobStatus.CANCELLED,
                    completed_at=datetime.now(timezone.utc),
                    error="Cancelled by user",
                ),
            )

            # Clean up files
            files_deleted = 0
            if job.pdf_path:
                if await self.storage.delete_file(job.pdf_path, ignore_missing=True):
                    files_deleted += 1

            if job.msf_path:
                if await self.storage.delete_file(job.msf_path, ignore_missing=True):
                    files_deleted += 1

            logger.info(f"Job {job_id} cancelled, {files_deleted} files cleaned up")
            return True

        except JobNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            raise StorageException(f"Failed to cancel job: {e}")

    async def get_job_files(self, job_id: str) -> dict:
        """
        Get all file paths associated with a job.

        Args:
            job_id: Job ID

        Returns:
            Dict with file paths and info
        """
        try:
            job = await self.jobs.get_job(job_id)
            files = {"pdf": None, "msf": None}

            if job.pdf_path and Path(job.pdf_path).exists():
                files["pdf"] = await self.storage.get_file_info(job.pdf_path)

            if job.msf_path and Path(job.msf_path).exists():
                files["msf"] = await self.storage.get_file_info(job.msf_path)

            return files

        except JobNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get job files: {e}")
            raise StorageException(f"Failed to get job files: {e}")