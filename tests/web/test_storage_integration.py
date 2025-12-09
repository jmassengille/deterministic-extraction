"""Integration tests for storage system with job tracking."""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.web.core.database import Database
from src.web.jobs import JobService, JobCreate, JobStatus
from src.web.storage import (
    FileManager,
    CleanupManager,
    StorageConfig,
    FileValidationError,
)


@pytest.fixture
async def db_setup(tmp_path):
    """Setup test database."""
    db_path = tmp_path / "test.db"
    await Database.initialize(str(db_path))
    yield
    await Database.close()


@pytest.fixture
def storage_dirs(tmp_path):
    """Setup storage directories."""
    StorageConfig.upload_dir = tmp_path / "uploads"
    StorageConfig.output_dir = tmp_path / "output"
    StorageConfig.temp_dir = tmp_path / "temp"
    StorageConfig.init()
    return tmp_path


@pytest.fixture
def file_manager():
    """Create file manager instance."""
    return FileManager()


@pytest.fixture
def cleanup_manager():
    """Create cleanup manager instance."""
    return CleanupManager()


@pytest.fixture
def sample_pdf_content():
    """Create sample PDF content."""
    # Make sure it's bigger than minimum file size (1KB)
    return b"%PDF-1.4\n%Sample PDF content for testing\n" + b"x" * 2000 + b"\n%%EOF"


class TestFileManager:
    """Test FileManager with job integration."""

    @pytest.mark.asyncio
    async def test_process_upload_success(
        self, db_setup, storage_dirs, file_manager, sample_pdf_content
    ):
        """Test complete upload processing workflow."""
        async def chunks():
            yield sample_pdf_content

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {
                "pages": 5,
                "encrypted": False,
                "has_metadata": True,
            }

            result = await file_manager.process_upload(
                chunks(),
                "document.pdf",
                len(sample_pdf_content),
                metadata={"source": "test"},
            )

            assert result["job_id"]
            assert result["filename"] == "document.pdf"
            assert result["file_size"] == len(sample_pdf_content)
            assert result["file_hash"]
            assert result["pdf_metadata"]["pages"] == 5
            assert Path(result["pdf_path"]).exists()

            # Verify job was created
            job = await file_manager.jobs.get_job(result["job_id"])
            assert job.filename == "document.pdf"
            assert job.status == JobStatus.PENDING
            assert job.pdf_path == result["pdf_path"]

    @pytest.mark.asyncio
    async def test_process_upload_validation_failure(
        self, db_setup, storage_dirs, file_manager
    ):
        """Test upload with validation failure."""
        async def bad_chunks():
            yield b"not a pdf"

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            from pypdf.errors import PdfReadError
            mock_validate.side_effect = PdfReadError("Invalid PDF")

            with pytest.raises(Exception) as exc:
                await file_manager.process_upload(
                    bad_chunks(),
                    "bad.pdf",
                    9,
                )

            # Verify file was cleaned up
            upload_files = list(StorageConfig.upload_dir.glob("*.pdf"))
            assert len(upload_files) == 0

    @pytest.mark.asyncio
    async def test_mark_file_processed(
        self, db_setup, storage_dirs, file_manager, sample_pdf_content
    ):
        """Test marking job as processed with MSF."""
        # Create a job first
        async def chunks():
            yield sample_pdf_content

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {"pages": 1, "encrypted": False}

            result = await file_manager.process_upload(
                chunks(),
                "test.pdf",
                len(sample_pdf_content),
            )

        job_id = result["job_id"]
        msf_path = storage_dirs / "output" / "test.msf"
        msf_path.write_text("<msf>test</msf>")

        # Mark as processed
        await file_manager.mark_file_processed(
            job_id,
            str(msf_path),
            metadata={"processing_time": 5.2},
        )

        # Verify job update
        job = await file_manager.jobs.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.msf_path == str(msf_path)
        assert job.progress == 100
        assert job.metadata["processing_time"] == 5.2

    @pytest.mark.asyncio
    async def test_get_download_path(
        self, db_setup, storage_dirs, file_manager, sample_pdf_content
    ):
        """Test getting download path for completed job."""
        # Create and complete a job
        async def chunks():
            yield sample_pdf_content

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {"pages": 1, "encrypted": False}

            result = await file_manager.process_upload(
                chunks(),
                "test.pdf",
                len(sample_pdf_content),
            )

        job_id = result["job_id"]
        msf_path = storage_dirs / "output" / "test.msf"
        msf_path.write_text("<msf>content</msf>")

        await file_manager.mark_file_processed(job_id, str(msf_path))

        # Get download path
        download_path = await file_manager.get_download_path(job_id)
        assert download_path == str(msf_path)
        assert Path(download_path).exists()

    @pytest.mark.asyncio
    async def test_get_download_path_not_ready(
        self, db_setup, storage_dirs, file_manager, sample_pdf_content
    ):
        """Test download path for incomplete job."""
        # Create pending job
        async def chunks():
            yield sample_pdf_content

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {"pages": 1, "encrypted": False}

            result = await file_manager.process_upload(
                chunks(),
                "test.pdf",
                len(sample_pdf_content),
            )

        from src.web.common.exceptions import JobStateException

        with pytest.raises(JobStateException) as exc:
            await file_manager.get_download_path(result["job_id"])
        assert "not completed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_cancel_and_cleanup(
        self, db_setup, storage_dirs, file_manager, sample_pdf_content
    ):
        """Test job cancellation with file cleanup."""
        # Create a job
        async def chunks():
            yield sample_pdf_content

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {"pages": 1, "encrypted": False}

            result = await file_manager.process_upload(
                chunks(),
                "test.pdf",
                len(sample_pdf_content),
            )

        job_id = result["job_id"]
        pdf_path = Path(result["pdf_path"])
        assert pdf_path.exists()

        # Cancel job
        cancelled = await file_manager.cancel_and_cleanup(job_id)
        assert cancelled is True

        # Verify cleanup
        assert not pdf_path.exists()
        job = await file_manager.jobs.get_job(job_id)
        assert job.status == JobStatus.CANCELLED


class TestCleanupManager:
    """Test CleanupManager background tasks."""

    @pytest.mark.asyncio
    async def test_cleanup_old_files(
        self, db_setup, storage_dirs, cleanup_manager
    ):
        """Test cleanup of old files."""
        # Create old MSF file
        old_msf = StorageConfig.output_dir / "old.msf"
        old_msf.write_text("<msf>old</msf>")

        # Make it old
        old_time = (datetime.utcnow() - timedelta(hours=25)).timestamp()
        import os
        os.utime(old_msf, (old_time, old_time))

        # Create recent MSF file
        new_msf = StorageConfig.output_dir / "new.msf"
        new_msf.write_text("<msf>new</msf>")

        # Run cleanup
        stats = await cleanup_manager.run_cleanup()

        # Verify results
        assert stats["old_msf"] == 1
        assert not old_msf.exists()
        assert new_msf.exists()

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files(
        self, db_setup, storage_dirs, cleanup_manager, sample_pdf_content
    ):
        """Test cleanup of orphaned files."""
        # Create orphaned PDF (no job record)
        orphan_pdf = StorageConfig.upload_dir / "orphan.pdf"
        orphan_pdf.write_bytes(sample_pdf_content)

        # Make it old enough
        old_time = (datetime.utcnow() - timedelta(hours=3)).timestamp()
        import os
        os.utime(orphan_pdf, (old_time, old_time))

        # Create job with associated file
        job_service = JobService()
        active_pdf = StorageConfig.upload_dir / "active.pdf"
        active_pdf.write_bytes(sample_pdf_content)

        job = await job_service.create_job(
            JobCreate(
                filename="active.pdf",
                file_size=len(sample_pdf_content),
                pdf_path=str(active_pdf),
            )
        )

        # Run cleanup
        stats = await cleanup_manager.run_cleanup()

        # Verify results
        assert stats["orphaned"] == 1
        assert not orphan_pdf.exists()
        assert active_pdf.exists()

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(
        self, db_setup, storage_dirs, cleanup_manager
    ):
        """Test cleanup of old job records."""
        job_service = JobService()

        # Create old failed job
        old_job = await job_service.create_job(
            JobCreate(
                filename="old.pdf",
                file_size=1000,
                pdf_path="/fake/old.pdf",
            )
        )

        # Manually update to old failed job
        pool = Database.get_pool()
        async with pool.acquire() as conn:
            old_time = (datetime.utcnow() - timedelta(days=8)).isoformat()
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', created_at = ?
                WHERE id = ?
                """,
                (old_time, old_job.id),
            )
            await conn.commit()

        # Create recent failed job
        recent_job = await job_service.create_job(
            JobCreate(
                filename="recent.pdf",
                file_size=1000,
                pdf_path="/fake/recent.pdf",
            )
        )
        await job_service.update_job(
            recent_job.id,
            {"status": JobStatus.FAILED}
        )

        # Run cleanup
        stats = await cleanup_manager.run_cleanup()

        # Verify results
        assert stats["failed_jobs"] == 1

        # Old job should be deleted
        from src.web.common.exceptions import JobNotFoundException
        with pytest.raises(JobNotFoundException):
            await job_service.get_job(old_job.id)

        # Recent job should remain
        job = await job_service.get_job(recent_job.id)
        assert job is not None

    @pytest.mark.asyncio
    async def test_cleanup_temp_files(
        self, storage_dirs, cleanup_manager
    ):
        """Test cleanup of temporary files."""
        # Create old temp file
        old_temp = StorageConfig.temp_dir / "old.tmp"
        old_temp.write_bytes(b"temp data")

        # Make it old
        old_time = (datetime.utcnow() - timedelta(hours=2)).timestamp()
        import os
        os.utime(old_temp, (old_time, old_time))

        # Create recent temp file
        new_temp = StorageConfig.temp_dir / "new.tmp"
        new_temp.write_bytes(b"new temp")

        # Run cleanup
        await cleanup_manager.run_cleanup()

        # Verify results
        assert not old_temp.exists()
        assert new_temp.exists()

    @pytest.mark.asyncio
    async def test_cleanup_manager_lifecycle(self, storage_dirs, cleanup_manager):
        """Test cleanup manager start/stop."""
        # Configure short interval for testing
        StorageConfig.cleanup_interval = 0.1

        # Start manager
        await cleanup_manager.start()
        assert cleanup_manager.running
        assert cleanup_manager.task is not None

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop manager
        await cleanup_manager.stop()
        assert not cleanup_manager.running
        assert cleanup_manager.task.done()