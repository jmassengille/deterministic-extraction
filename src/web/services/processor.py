"""Pipeline adapter for web application integration.

Supports multi-format output (MSF, ACC) with format-aware pipeline creation.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from backend.core.models import InstrumentInfo
from backend.core.pipeline import Pipeline

logger = logging.getLogger(__name__)


class PipelineProcessor:
    """Adapter for running the backend pipeline in async web context."""

    def __init__(
        self,
        max_concurrent_llm: int = 5,
        max_workers: int = 2
    ):
        """
        Initialize pipeline processor.

        Args:
            max_concurrent_llm: Maximum concurrent LLM calls
            max_workers: Maximum thread pool workers for pipeline execution
        """
        self.max_concurrent_llm = max_concurrent_llm
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._pipelines = {}  # Cache pipeline instances per thread
        self._loop = None  # Will be set when processing

        logger.info(
            f"Pipeline processor initialized: Vision extraction, "
            f"LLM concurrency={max_concurrent_llm}, workers={max_workers}"
        )

    def _get_pipeline(
        self,
        output_formats: Optional[List[str]] = None
    ) -> Pipeline:
        """Get or create pipeline instance for current thread and formats.

        Pipelines are cached by (thread_id, output_formats) to reuse when
        the same format configuration is requested.
        """
        import threading
        from backend.config.settings import LLM_MODEL_ASYNC

        thread_id = threading.current_thread().ident
        formats_key = tuple(output_formats) if output_formats else ("msf",)
        cache_key = (thread_id, formats_key)

        if cache_key not in self._pipelines:
            self._pipelines[cache_key] = Pipeline(
                max_concurrent_llm=self.max_concurrent_llm,
                llm_model=LLM_MODEL_ASYNC,
                output_formats=list(formats_key)
            )
            logger.debug(
                f"Created pipeline for thread {thread_id}, "
                f"formats={formats_key}, model={LLM_MODEL_ASYNC}"
            )

        return self._pipelines[cache_key]

    async def process_pdf(
        self,
        pdf_path: Path,
        output_path: Path,
        job_id: str,
        instrument_info: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        output_formats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process PDF through pipeline with progress tracking.

        Args:
            pdf_path: Path to input PDF
            output_path: Path for output MSF
            job_id: Job ID for tracking
            instrument_info: Optional instrument metadata
            progress_callback: Optional async progress callback
            output_formats: List of output formats (msf, acc)

        Returns:
            Dict with processing results and statistics
        """
        try:
            # Convert dict to InstrumentInfo if provided
            inst_info = None
            if instrument_info:
                inst_info = InstrumentInfo(
                    manufacturer=instrument_info.get("manufacturer"),
                    model=instrument_info.get("model"),
                    description=instrument_info.get("description"),
                    instrument_type=instrument_info.get("instrument_type")
                )

            # Create sync callback wrapper if async callback provided
            sync_callback = None
            if progress_callback:
                # Save event loop for callback
                self._loop = asyncio.get_event_loop()
                sync_callback = self._create_sync_callback(
                    job_id, progress_callback
                )

            # Run pipeline in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._run_pipeline,
                pdf_path,
                output_path,
                inst_info,
                sync_callback,
                output_formats
            )

            # Add job_id to result
            result["job_id"] = job_id

            return result

        except Exception as e:
            logger.error(f"Pipeline processing failed for job {job_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id,
                "instrument_info": instrument_info,
                "output_formats": output_formats
            }

    def _run_pipeline(
        self,
        pdf_path: Path,
        output_path: Path,
        instrument_info: Optional[InstrumentInfo],
        progress_callback: Optional[Callable],
        output_formats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run pipeline synchronously in thread pool."""
        pipeline = self._get_pipeline(output_formats=output_formats)
        return pipeline.process(
            pdf_path=pdf_path,
            output_path=output_path,
            instrument_info=instrument_info,
            progress_callback=progress_callback
        )

    def _create_sync_callback(
        self,
        job_id: str,
        async_callback: Callable
    ) -> Callable:
        """
        Create synchronous callback wrapper for async callback.

        Args:
            job_id: Job ID for tracking
            async_callback: Async callback to wrap

        Returns:
            Synchronous callback function
        """
        def sync_wrapper(phase: str, **kwargs):
            # Calculate overall progress percentage
            progress = self._calculate_progress(phase, **kwargs)

            # Create callback data
            callback_data = {
                "job_id": job_id,
                "phase": phase,
                "progress": progress,
                "details": kwargs
            }

            # Schedule async callback in main event loop
            try:
                if self._loop:
                    future = asyncio.run_coroutine_threadsafe(
                        async_callback(callback_data),
                        self._loop
                    )
                    # Don't wait for result to avoid blocking
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

        return sync_wrapper

    def _calculate_progress(self, phase: str, **kwargs) -> int:
        """
        Calculate overall progress percentage based on phase.

        Args:
            phase: Current processing phase
            **kwargs: Phase-specific progress data

        Returns:
            Progress percentage (0-100)
        """
        # Phase weights (total = 100)
        phase_weights = {
            "toc_analysis": (0, 10),      # 0-10%
            "table_extraction": (10, 30),  # 10-40%
            "vision_processing": (40, 30), # 40-70%
            "llm_extraction": (70, 25),    # 70-95%
            "msf_generation": (95, 5),     # 95-100%
            "complete": (100, 0),          # 100%
            "error": (0, 0)                # Keep current
        }

        if phase not in phase_weights:
            return 0

        base, weight = phase_weights[phase]

        # For complete or error, return fixed percentage
        if phase in ("complete", "error"):
            return base

        # Calculate phase progress
        phase_progress = 0

        # Table/page based progress
        if "tables_done" in kwargs and "tables_total" in kwargs:
            total = kwargs.get("tables_total")
            done = kwargs.get("tables_done")
            if total is not None and done is not None and total > 0:
                phase_progress = (done / total) * 100
        elif "pages_done" in kwargs and "pages_total" in kwargs:
            total = kwargs.get("pages_total")
            done = kwargs.get("pages_done")
            if total is not None and done is not None and total > 0:
                phase_progress = (done / total) * 100

        # Calculate overall progress
        overall = base + int((phase_progress / 100) * weight)
        return min(100, max(0, overall))

    async def cleanup(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)
        logger.info("Pipeline processor cleaned up")