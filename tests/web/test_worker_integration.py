"""Integration tests for worker service."""

import asyncio
import sys
from pathlib import Path

# Ensure src is in path before any imports
project_root = Path(__file__).parent.parent.parent
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from web.core.database import Database
from web.jobs.service import JobService
from web.jobs.schemas import JobCreate, JobStatus
from web.storage import StorageService, StorageConfig
from web.services import Worker, WorkerManager, ProgressManager


@pytest.fixture
async def db_setup(tmp_path):
    """Setup test database."""
    db_path = tmp_path / "test.db"
    await Database.initialize(str(db_path))
    yield
    await Database.close()


@pytest.fixture
async def services(tmp_path, db_setup):
    """Create test services."""
    # Configure storage
    StorageConfig.upload_dir = tmp_path / "uploads"
    StorageConfig.output_dir = tmp_path / "output"
    StorageConfig.temp_dir = tmp_path / "temp"
    StorageConfig.init()

    # Create services
    job_service = JobService()
    storage_service = StorageService()
    progress_manager = ProgressManager()

    return {
        "jobs": job_service,
        "storage": storage_service,
        "progress": progress_manager
    }


@pytest.fixture
async def worker(services):
    """Create test worker."""
    return Worker(
        job_service=services["jobs"],
        storage_service=services["storage"],
        progress_manager=services["progress"],
        poll_interval=0.1  # Fast polling for tests
    )


@pytest.fixture
def mock_processor():
    """Create mock processor."""
    processor = AsyncMock()
    processor.process_pdf = AsyncMock(return_value={
        "success": True,
        "job_id": "test-job",
        "instrument_info": {
            "manufacturer": "Test",
            "model": "Model-1"
        },
        "statistics": {
            "pages_analyzed": 5,
            "tables_found": 3
        }
    })
    processor.cleanup = AsyncMock()
    return processor


class TestWorker:
    """Test worker service."""

    @pytest.mark.asyncio
    async def test_worker_lifecycle(self, worker):
        """Test worker start/stop."""
        # Start worker
        await worker.start()
        assert worker.running is True
        assert worker._task is not None

        # Stop worker
        await worker.stop()
        assert worker.running is False

    @pytest.mark.asyncio
    async def test_process_job_success(self, services, worker, mock_processor, tmp_path):
        """Test successful job processing."""
        # Create a test PDF
        pdf_path = tmp_path / "uploads" / "test.pdf"
        pdf_path.parent.mkdir(exist_ok=True)
        pdf_path.write_bytes(b"fake pdf content")

        # Create a job
        job = await services["jobs"].create_job(JobCreate(
            filename="test.pdf",
            file_size=1000,
            pdf_path=str(pdf_path),
            metadata={"test": "data"}
        ))

        # Set mock processor
        worker.processor = mock_processor

        # Process the job
        await worker._process_job(job.id)

        # Verify job was updated
        updated_job = await services["jobs"].get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.msf_path is not None
        assert updated_job.progress == 100

        # Verify processor was called
        mock_processor.process_pdf.assert_called_once()

        # Verify progress events were added
        events = await services["progress"].get_events(job.id)
        assert len(events) > 0
        assert any(e.phase == "complete" for e in events)

    @pytest.mark.asyncio
    async def test_process_job_failure(self, services, worker, mock_processor, tmp_path):
        """Test job processing failure."""
        # Create a test PDF
        pdf_path = tmp_path / "uploads" / "test.pdf"
        pdf_path.parent.mkdir(exist_ok=True)
        pdf_path.write_bytes(b"fake pdf")

        # Create a job
        job = await services["jobs"].create_job(JobCreate(
            filename="test.pdf",
            file_size=1000,
            pdf_path=str(pdf_path)
        ))

        # Configure processor to fail
        mock_processor.process_pdf.return_value = {
            "success": False,
            "error": "Processing failed",
            "job_id": job.id
        }
        worker.processor = mock_processor

        # Process the job
        await worker._process_job(job.id)

        # Verify job was retried (not failed yet)
        updated_job = await services["jobs"].get_job(job.id)
        assert updated_job.status == JobStatus.PENDING
        assert updated_job.retry_count == 1
        assert "Retry 1/3" in updated_job.error

    @pytest.mark.asyncio
    async def test_process_job_max_retries(self, services, worker, mock_processor, tmp_path):
        """Test job failure after max retries."""
        # Create a test PDF
        pdf_path = tmp_path / "uploads" / "test.pdf"
        pdf_path.parent.mkdir(exist_ok=True)
        pdf_path.write_bytes(b"fake pdf")

        # Create a job with max retries already
        job = await services["jobs"].create_job(JobCreate(
            filename="test.pdf",
            file_size=1000,
            pdf_path=str(pdf_path)
        ))

        # Update retry count to max
        await services["jobs"].update_job_status(
            job.id,
            JobStatus.PENDING,
            retry_count=3
        )

        # Configure processor to fail
        mock_processor.process_pdf.return_value = {
            "success": False,
            "error": "Final failure",
            "job_id": job.id
        }
        worker.processor = mock_processor

        # Process the job
        await worker._process_job(job.id)

        # Verify job failed permanently
        updated_job = await services["jobs"].get_job(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error == "Final failure"

    @pytest.mark.asyncio
    async def test_process_missing_pdf(self, services, worker):
        """Test processing with missing PDF file."""
        # Create a job with non-existent PDF
        job = await services["jobs"].create_job(JobCreate(
            filename="missing.pdf",
            file_size=1000,
            pdf_path="/nonexistent/path.pdf"
        ))

        # Process the job
        await worker._process_job(job.id)

        # Verify job was marked for retry
        updated_job = await services["jobs"].get_job(job.id)
        assert updated_job.status == JobStatus.PENDING
        assert "not found" in updated_job.error.lower()

    @pytest.mark.asyncio
    async def test_worker_queue_polling(self, services, worker, mock_processor, tmp_path):
        """Test worker polls and processes queue."""
        # Create test PDFs and jobs
        jobs = []
        for i in range(3):
            pdf_path = tmp_path / "uploads" / f"test{i}.pdf"
            pdf_path.parent.mkdir(exist_ok=True)
            pdf_path.write_bytes(b"fake pdf")

            job = await services["jobs"].create_job(JobCreate(
                filename=f"test{i}.pdf",
                file_size=1000,
                pdf_path=str(pdf_path)
            ))
            jobs.append(job)

        # Set mock processor
        worker.processor = mock_processor
        worker.poll_interval = 0.01  # Very fast polling

        # Start worker
        await worker.start()

        # Wait for jobs to be processed
        await asyncio.sleep(0.5)

        # Stop worker
        await worker.stop()

        # Verify all jobs were processed
        for job in jobs:
            updated = await services["jobs"].get_job(job.id)
            assert updated.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_single_job(self, services, worker, mock_processor, tmp_path):
        """Test processing single job directly."""
        # Create a test PDF and job
        pdf_path = tmp_path / "uploads" / "test.pdf"
        pdf_path.parent.mkdir(exist_ok=True)
        pdf_path.write_bytes(b"fake pdf")

        job = await services["jobs"].create_job(JobCreate(
            filename="test.pdf",
            file_size=1000,
            pdf_path=str(pdf_path)
        ))

        # Set mock processor
        worker.processor = mock_processor

        # Process single job
        success = await worker.process_single_job(job.id)

        assert success is True
        updated_job = await services["jobs"].get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED


class TestWorkerManager:
    """Test worker manager."""

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, services):
        """Test manager start/stop."""
        manager = WorkerManager(
            num_workers=2,
            job_service=services["jobs"],
            storage_service=services["storage"],
            progress_manager=services["progress"]
        )

        # Start workers
        await manager.start()
        assert len(manager.workers) == 2
        assert all(w.running for w in manager.workers)

        # Stop workers
        await manager.stop()
        assert len(manager.workers) == 0

    @pytest.mark.asyncio
    async def test_manager_shared_processor(self, services):
        """Test workers share same processor."""
        manager = WorkerManager(
            num_workers=3,
            job_service=services["jobs"],
            storage_service=services["storage"],
            progress_manager=services["progress"]
        )

        await manager.start()

        # Verify all workers share the same processor
        processors = [w.processor for w in manager.workers]
        assert all(p is processors[0] for p in processors)

        await manager.stop()

    def test_manager_stats(self, services):
        """Test manager statistics."""
        manager = WorkerManager(
            num_workers=2,
            job_service=services["jobs"],
            storage_service=services["storage"],
            progress_manager=services["progress"]
        )

        stats = manager.get_stats()
        assert stats["num_workers"] == 2
        assert stats["active_workers"] == 0  # Not started yet
        assert "processor_stats" in stats


class TestProgressManager:
    """Test progress manager."""

    @pytest.mark.asyncio
    async def test_add_and_get_events(self):
        """Test adding and retrieving events."""
        manager = ProgressManager()

        # Add events
        await manager.add_event("job1", 10, "starting")
        await manager.add_event("job1", 50, "processing")
        await manager.add_event("job1", 100, "complete")

        # Get events
        events = await manager.get_events("job1")
        assert len(events) == 3
        assert events[0].progress == 10
        assert events[-1].phase == "complete"

    @pytest.mark.asyncio
    async def test_event_subscription(self):
        """Test subscribing to events."""
        manager = ProgressManager()

        # Add initial event
        await manager.add_event("job1", 10, "starting")

        # Subscribe
        events = []
        async def collect_events():
            async for event in manager.subscribe("job1", include_history=True):
                events.append(event)
                if event.phase == "complete":
                    break

        # Start subscription
        task = asyncio.create_task(collect_events())

        # Add more events
        await asyncio.sleep(0.01)
        await manager.add_event("job1", 50, "processing")
        await manager.add_event("job1", 100, "complete")

        # Wait for subscription to complete
        await task

        # Verify all events received
        assert len(events) == 3
        assert events[0].progress == 10  # Historical
        assert events[-1].phase == "complete"

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self):
        """Test cleaning up old events."""
        manager = ProgressManager()

        # Add events for multiple jobs
        from datetime import timedelta
        old_time = datetime.utcnow() - timedelta(hours=25)

        # Manually add old event
        event = manager.ProgressEvent(
            job_id="old_job",
            timestamp=old_time,
            progress=100,
            phase="complete",
            message="Old job",
            details={}
        )
        manager._events["old_job"].append(event)

        # Add recent event
        await manager.add_event("recent_job", 50, "processing")

        # Clean up
        cleaned = await manager.cleanup_old_events(keep_hours=24)

        # Verify
        assert cleaned == 1
        assert "old_job" not in manager._events
        assert "recent_job" in manager._events

    @pytest.mark.asyncio
    async def test_get_latest_progress(self):
        """Test getting latest progress."""
        manager = ProgressManager()

        # No events
        progress = await manager.get_latest_progress("job1")
        assert progress is None

        # Add events
        await manager.add_event("job1", 10, "starting")
        await manager.add_event("job1", 50, "processing")

        # Get latest
        progress = await manager.get_latest_progress("job1")
        assert progress == 50