"""Background worker for processing document jobs."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..core.database import Database
from ..jobs.service import JobService
from ..jobs.schemas import JobStatus, JobUpdate, JobStage
from ..storage import StorageService
from ..storage.service import sanitize_filename_part
from .processor import PipelineProcessor
from .progress_manager import ProgressManager

logger = logging.getLogger(__name__)


class Worker:
    """Background worker for processing jobs from queue."""

    def __init__(
        self,
        job_service: JobService,
        storage_service: StorageService,
        progress_manager: ProgressManager,
        processor: Optional[PipelineProcessor] = None,
        poll_interval: float = 1.0,
        max_retries: int = 3
    ):
        """
        Initialize worker.

        Args:
            job_service: Service for job operations
            storage_service: Service for file operations
            progress_manager: Manager for progress events
            processor: Pipeline processor (created if not provided)
            poll_interval: Seconds between queue polls
            max_retries: Maximum retries for failed jobs
        """
        self.jobs = job_service
        self.storage = storage_service
        self.progress = progress_manager
        self.processor = processor or PipelineProcessor()
        self.poll_interval = poll_interval
        self.max_retries = max_retries

        self.running = False
        self._task = None
        self._shutdown_event = asyncio.Event()

        logger.info(f"Worker initialized (poll interval: {poll_interval}s)")

    async def start(self) -> None:
        """Start the worker."""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("Worker started")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the worker gracefully.

        Args:
            timeout: Maximum seconds to wait for shutdown
        """
        if not self.running:
            return

        logger.info("Stopping worker...")
        self.running = False
        self._shutdown_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Worker shutdown timed out after {timeout}s")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                # Handle external cancellation (e.g., Ctrl+C)
                if self._task and not self._task.done():
                    self._task.cancel()
                    try:
                        await self._task
                    except asyncio.CancelledError:
                        pass

        try:
            await self.processor.cleanup()
        except Exception as e:
            logger.error(f"Error during processor cleanup: {e}")
        logger.info("Worker stopped")

    async def _run(self) -> None:
        """Main worker loop."""
        logger.info("Worker loop started")

        while self.running:
            try:
                # Check for pending jobs
                job = await self.jobs.get_pending_job()

                if job:
                    await self._process_job(job.id)
                else:
                    # No jobs, wait before polling again
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                    except asyncio.TimeoutError:
                        pass  # Continue polling

            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        logger.info("Worker loop ended")

    def _validate_job_prerequisites(self, job, pdf_path: Path) -> None:
        """
        Validate job has required files and valid paths before processing.

        Args:
            job: Job object with metadata
            pdf_path: Path to the PDF file

        Raises:
            FileNotFoundError: If PDF file does not exist
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

    def _create_progress_callback(self, job_id: str):
        """
        Create progress callback for pipeline processing.

        Args:
            job_id: Job identifier

        Returns:
            Async callback function for progress updates
        """
        async def progress_callback(data: dict):
            await self.progress.add_event(
                job_id=data["job_id"],
                progress=data["progress"],
                phase=data["phase"],
                details=data.get("details", {})
            )

            # Update job progress in database - map pipeline phases to generic stages
            stage_map = {
                "toc_analysis": JobStage.ANALYZING_STRUCTURE,
                "structure_analysis": JobStage.ANALYZING_STRUCTURE,
                "table_extraction": JobStage.EXTRACTING_REGIONS,
                "region_extraction": JobStage.EXTRACTING_REGIONS,
                "vision_processing": JobStage.PROCESSING_DATA,
                "llm_extraction": JobStage.PROCESSING_DATA,
                "data_processing": JobStage.PROCESSING_DATA,
                "output_generation": JobStage.GENERATING_OUTPUT,
                "serialization": JobStage.GENERATING_OUTPUT,
                "complete": JobStage.FINALIZING
            }
            stage = stage_map.get(data["phase"], JobStage.PROCESSING_DATA)

            await self.jobs.update_job(
                job_id,
                JobUpdate(
                    progress=data["progress"],
                    current_stage=stage
                )
            )

        return progress_callback

    async def _execute_pipeline(
        self,
        job,
        pdf_path: Path,
        temp_output_path: Path,
        job_id: str
    ) -> dict:
        """
        Execute MetExtractor pipeline and return result.

        Args:
            job: Job object with metadata
            pdf_path: Path to PDF file
            temp_output_path: Temporary output path for MSF
            job_id: Job identifier

        Returns:
            Pipeline result dictionary with success flag and metadata
        """
        progress_callback = self._create_progress_callback(job_id)

        # Use output_formats from job schema (stored in database)
        output_formats = job.output_formats if job.output_formats else ["msf"]

        result = await self.processor.process_pdf(
            pdf_path=pdf_path,
            output_path=temp_output_path,
            job_id=job_id,
            instrument_info=job.metadata,
            progress_callback=progress_callback,
            output_formats=output_formats
        )

        return result

    def _generate_instrument_filename(self, result: dict, job) -> str:
        """
        Generate instrument-specific filename from extraction results.

        Args:
            result: Pipeline result with instrument_info
            job: Job object with filename fallback

        Returns:
            Sanitized instrument name for filename
        """
        inst_info = result.get("instrument_info")
        if inst_info and isinstance(inst_info, dict):
            manufacturer = sanitize_filename_part(inst_info.get("manufacturer", ""))
            model = sanitize_filename_part(inst_info.get("model", ""))
            instrument_type = sanitize_filename_part(
                inst_info.get("instrument_type", "")
            ).lower()

            parts = []
            if manufacturer and manufacturer.lower() != "unknown":
                parts.append(manufacturer)
            if model and model.lower() != "unknown":
                parts.append(model)
            if instrument_type and instrument_type != "unknown":
                parts.append(instrument_type)

            if parts:
                return "_".join(parts)

        return sanitize_filename_part(Path(job.filename).stem)

    def _finalize_output(
        self,
        temp_output_path: Path,
        job_id: str,
        instrument_name: str
    ) -> Path:
        """
        Rename output file to instrument-specific name.

        Args:
            temp_output_path: Temporary output path
            job_id: Job identifier
            instrument_name: Instrument-specific filename

        Returns:
            Final MSF file path
        """
        final_output_path = Path(
            self.storage.generate_output_path(str(job_id), instrument_name)
        )

        if temp_output_path.exists():
            temp_output_path.rename(final_output_path)
            return final_output_path
        else:
            return temp_output_path

    def _convert_instrument_info_to_dict(self, inst_info_raw) -> Optional[dict]:
        """
        Convert instrument_info to dictionary format.

        Args:
            inst_info_raw: Raw instrument info (dict, object, or string)

        Returns:
            Dictionary representation or None
        """
        if not inst_info_raw:
            return None

        if isinstance(inst_info_raw, dict):
            return inst_info_raw
        elif hasattr(inst_info_raw, '__dict__'):
            return inst_info_raw.__dict__
        else:
            return {"raw": str(inst_info_raw)}

    def _build_output_paths(
        self,
        output_files: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Build output_paths dict from pipeline output_files.

        Args:
            output_files: Pipeline output mapping format to file paths
                e.g. {"json": ["path/doc.json"], "csv": ["path/doc.csv"]}

        Returns:
            Dict mapping format to path (str for single-file, dict for multi-file)
                e.g. {"json": "path/doc.json", "csv": "path/doc.csv"}
        """
        if not isinstance(output_files, dict):
            logger.warning(f"Invalid output_files type: {type(output_files)}")
            return {}

        output_paths = {}
        for format_name, files in output_files.items():
            if not isinstance(files, list):
                logger.warning(f"Invalid files type for format {format_name}: {type(files)}")
                continue

            if len(files) == 0:
                continue
            elif len(files) == 1:
                # Single file format
                output_paths[format_name] = str(files[0])
            else:
                # Multi-file format - use filename stems as keys
                output_paths[format_name] = {
                    Path(f).stem: str(f) for f in files
                }

        return output_paths

    async def _update_job_completion(
        self,
        job_id: str,
        job,
        result: dict
    ) -> None:
        """
        Update job status to completed and emit completion events.

        Args:
            job_id: Job identifier
            job: Job object with metadata
            result: Pipeline result with statistics and output_files
        """
        inst_info_dict = self._convert_instrument_info_to_dict(
            result.get("instrument_info")
        )

        # Build output_paths from pipeline output_files
        output_paths = self._build_output_paths(result.get("output_files", {}))

        await self.jobs.update_job(
            job_id,
            JobUpdate(
                status=JobStatus.COMPLETED,
                progress=100,
                current_stage=JobStage.FINALIZING,
                output_paths=output_paths if output_paths else None,
                metadata={
                    **job.metadata,
                    "document_info": inst_info_dict,
                    "statistics": result.get("statistics", {}),
                    "source_pages": result.get("source_pages", [])
                }
            )
        )

        await self.progress.add_event(
            job_id, 100, "complete",
            "Output generation completed successfully"
        )

        logger.info(f"Job {job_id} completed successfully")

    async def _process_job(self, job_id: str) -> None:
        """
        Process single job through validation, extraction, finalization.

        Args:
            job_id: Job identifier
        """
        logger.info(f"Processing job {job_id}")

        try:
            # Get job details
            job = await self.jobs.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # Update status to processing
            await self.jobs.update_job(
                job_id,
                JobUpdate(
                    status=JobStatus.PROCESSING,
                    current_stage=JobStage.LOADING_DOCUMENT
                )
            )

            # Send initial progress
            await self.progress.add_event(
                job_id, 0, "starting",
                "Initializing document processing"
            )

            # Validate prerequisites
            pdf_path = Path(job.pdf_path)
            self._validate_job_prerequisites(job, pdf_path)

            # Generate temporary output path
            temp_output_path = Path(
                self.storage.generate_output_path(str(job_id), "temp")
            )

            # Execute pipeline
            result = await self._execute_pipeline(
                job, pdf_path, temp_output_path, job_id
            )

            if result["success"]:
                # Update job completion with output paths from pipeline result
                await self._update_job_completion(job_id, job, result)

            else:
                # Job failed
                error_msg = result.get("error", "Unknown error")
                retry_count = job.metadata.get("retry_count", 0)
                await self._handle_job_failure(job_id, error_msg, retry_count)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id} processing failed: {error_msg}", exc_info=True)

            try:
                job = await self.jobs.get_job(job_id)
                retry_count = job.metadata.get("retry_count", 0) if job else 0
                await self._handle_job_failure(job_id, error_msg, retry_count)
            except Exception as inner_e:
                logger.error(f"Failed to handle job failure: {inner_e}")

    async def _handle_job_failure(
        self,
        job_id: str,
        error: str,
        retry_count: int
    ) -> None:
        """
        Handle job failure with retry logic.

        Args:
            job_id: Job identifier
            error: Error message
            retry_count: Current retry count
        """
        if retry_count < self.max_retries:
            # Retry job
            new_retry_count = retry_count + 1

            # Get current job to preserve metadata
            job = await self.jobs.get_job(job_id)
            updated_metadata = job.metadata if job else {}
            updated_metadata["retry_count"] = new_retry_count

            await self.jobs.update_job(
                job_id,
                JobUpdate(
                    status=JobStatus.PENDING,  # Back to pending for retry
                    error=f"Retry {new_retry_count}/{self.max_retries}: {error}",
                    metadata=updated_metadata
                )
            )

            await self.progress.add_event(
                job_id, 0, "retry",
                f"Retrying ({new_retry_count}/{self.max_retries})"
            )

            logger.info(f"Job {job_id} scheduled for retry {new_retry_count}/{self.max_retries}")

        else:
            # Max retries exceeded, mark as failed
            await self.jobs.update_job(
                job_id,
                JobUpdate(
                    status=JobStatus.FAILED,
                    error=error
                )
            )

            await self.progress.add_event(
                job_id, 0, "error",
                f"Processing failed: {error}"
            )

            logger.error(f"Job {job_id} failed after {self.max_retries} retries: {error}")

    async def process_single_job(self, job_id: str) -> bool:
        """
        Process a single job immediately (for testing).

        Args:
            job_id: Job identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            await self._process_job(job_id)
            job = await self.jobs.get_job(job_id)
            return job and job.status == JobStatus.COMPLETED
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
            return False


class WorkerManager:
    """Manages multiple workers."""

    def __init__(
        self,
        num_workers: int = 1,
        job_service: Optional[JobService] = None,
        storage_service: Optional[StorageService] = None,
        progress_manager: Optional[ProgressManager] = None
    ):
        """
        Initialize worker manager.

        Args:
            num_workers: Number of workers to manage
            job_service: Shared job service
            storage_service: Shared storage service
            progress_manager: Shared progress manager
        """
        self.num_workers = num_workers
        self.workers = []

        # Create shared services if not provided
        self.jobs = job_service or JobService()
        self.storage = storage_service or StorageService()
        self.progress = progress_manager or ProgressManager()

        # Create single shared processor
        self.processor = PipelineProcessor(
            max_workers=num_workers  # Thread pool size matches worker count
        )

        logger.info(f"Worker manager initialized with {num_workers} workers")

    async def start(self) -> None:
        """Start all workers."""
        for i in range(self.num_workers):
            worker = Worker(
                job_service=self.jobs,
                storage_service=self.storage,
                progress_manager=self.progress,
                processor=self.processor  # Share processor
            )
            self.workers.append(worker)
            await worker.start()

        logger.info(f"Started {self.num_workers} workers")

    async def stop(self) -> None:
        """Stop all workers."""
        if not self.workers:
            return

        # Stop all workers concurrently
        tasks = [worker.stop() for worker in self.workers]
        await asyncio.gather(*tasks, return_exceptions=True)

        self.workers.clear()
        logger.info("All workers stopped")

    def get_stats(self) -> dict:
        """Get worker statistics."""
        return {
            "num_workers": self.num_workers,
            "active_workers": len(self.workers),
            "processor_stats": {
                "extraction_method": "vision",
                "max_concurrent_llm": self.processor.max_concurrent_llm
            }
        }