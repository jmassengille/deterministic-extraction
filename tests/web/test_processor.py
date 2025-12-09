"""Tests for pipeline processor service."""

import asyncio
import sys
from pathlib import Path

# Ensure src is in path before any imports
project_root = Path(__file__).parent.parent.parent
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor

from web.services.processor import PipelineProcessor


@pytest.fixture
def processor():
    """Create processor instance (vision-based)."""
    return PipelineProcessor(
        max_concurrent_llm=2,
        max_workers=1
    )


@pytest.fixture
def mock_pipeline():
    """Create mock pipeline."""
    mock = MagicMock()
    mock.process.return_value = {
        "success": True,
        "output_path": "/path/to/output.msf",
        "instrument_info": {
            "manufacturer": "Agilent",
            "model": "34401A"
        },
        "statistics": {
            "pages_analyzed": 10,
            "tables_found": 5,
            "tables_processed": 5
        }
    }
    return mock


class TestPipelineProcessor:
    """Test pipeline processor."""

    def test_initialization(self):
        """Test processor initialization (vision-based)."""
        processor = PipelineProcessor(
            max_concurrent_llm=10,
            max_workers=4
        )

        assert processor.max_concurrent_llm == 10
        assert isinstance(processor.executor, ThreadPoolExecutor)

    @pytest.mark.asyncio
    async def test_process_pdf_success(self, processor, mock_pipeline, tmp_path):
        """Test successful PDF processing."""
        # Setup
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf")
        output_path = tmp_path / "output.msf"

        with patch.object(processor, "_get_pipeline", return_value=mock_pipeline):
            # Process
            result = await processor.process_pdf(
                pdf_path=pdf_path,
                output_path=output_path,
                job_id="test-job-123",
                instrument_info={
                    "manufacturer": "Agilent",
                    "model": "34401A"
                }
            )

        # Verify
        assert result["success"] is True
        assert result["job_id"] == "test-job-123"
        assert "instrument_info" in result
        assert "statistics" in result

        # Check pipeline was called
        mock_pipeline.process.assert_called_once()
        call_args = mock_pipeline.process.call_args
        assert call_args[0][0] == pdf_path
        assert call_args[0][1] == output_path

    @pytest.mark.asyncio
    async def test_process_pdf_with_progress(self, processor, mock_pipeline, tmp_path):
        """Test PDF processing with progress callback."""
        # Setup
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf")
        output_path = tmp_path / "output.msf"

        progress_events = []

        async def progress_callback(data):
            progress_events.append(data)

        # Mock pipeline to call progress callback
        def mock_process(pdf_path, output_path, instrument_info, progress_callback):
            if progress_callback:
                progress_callback("toc_analysis", pages_total=10)
                progress_callback("table_extraction", tables_done=2, tables_total=5)
                progress_callback("complete")
            return {"success": True, "output_path": str(output_path)}

        mock_pipeline.process.side_effect = mock_process

        with patch.object(processor, "_get_pipeline", return_value=mock_pipeline):
            # Process
            result = await processor.process_pdf(
                pdf_path=pdf_path,
                output_path=output_path,
                job_id="test-job-123",
                progress_callback=progress_callback
            )

        # Verify progress events were captured
        assert len(progress_events) > 0
        assert any(e["phase"] == "toc_analysis" for e in progress_events)
        assert any(e["phase"] == "complete" for e in progress_events)

    @pytest.mark.asyncio
    async def test_process_pdf_failure(self, processor, mock_pipeline, tmp_path):
        """Test PDF processing failure."""
        # Setup
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf")
        output_path = tmp_path / "output.msf"

        mock_pipeline.process.side_effect = Exception("Pipeline failed")

        with patch.object(processor, "_get_pipeline", return_value=mock_pipeline):
            # Process
            result = await processor.process_pdf(
                pdf_path=pdf_path,
                output_path=output_path,
                job_id="test-job-123"
            )

        # Verify
        assert result["success"] is False
        assert "Pipeline failed" in result["error"]
        assert result["job_id"] == "test-job-123"

    def test_calculate_progress(self, processor):
        """Test progress calculation."""
        # Test phase-based progress
        assert processor._calculate_progress("toc_analysis") == 0
        assert processor._calculate_progress("complete") == 100
        assert processor._calculate_progress("error") == 0

        # Test with partial progress
        progress = processor._calculate_progress(
            "table_extraction",
            tables_done=5,
            tables_total=10
        )
        assert 10 < progress < 40  # Should be between base and base+weight

        progress = processor._calculate_progress(
            "vision_processing",
            tables_done=10,
            tables_total=10
        )
        assert progress == 70  # 40 + 30 (full phase weight)

        # Test with pages
        progress = processor._calculate_progress(
            "llm_extraction",
            pages_done=2,
            pages_total=4
        )
        assert 70 < progress < 95  # Halfway through LLM phase

    @pytest.mark.asyncio
    async def test_cleanup(self, processor):
        """Test processor cleanup."""
        await processor.cleanup()
        # Should not raise any errors

    def test_thread_safety(self, processor):
        """Test pipeline instance per thread."""
        with patch("web.services.processor.Pipeline") as MockPipeline:
            mock_pipeline1 = MagicMock()
            mock_pipeline2 = MagicMock()
            MockPipeline.side_effect = [mock_pipeline1, mock_pipeline2]

            # Get pipeline in main thread
            import threading
            thread_id1 = threading.current_thread().ident
            pipeline1 = processor._get_pipeline()

            # Get pipeline in another thread
            def get_in_thread():
                return processor._get_pipeline()

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_in_thread)
                pipeline2 = future.result()

            # Should have created two different instances
            assert MockPipeline.call_count == 2
            assert len(processor._pipelines) == 2

            # Getting again in main thread should return cached
            pipeline1_again = processor._get_pipeline()
            assert MockPipeline.call_count == 2  # No new instance

    @pytest.mark.asyncio
    async def test_sync_callback_wrapper(self, processor):
        """Test synchronous callback wrapper."""
        events = []

        async def async_callback(data):
            events.append(data)

        sync_callback = processor._create_sync_callback("job-123", async_callback)

        # Call sync callback from thread
        def call_sync():
            sync_callback("toc_analysis", pages_total=10)
            sync_callback("complete")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, call_sync)

        # Give time for async callbacks to complete
        await asyncio.sleep(0.1)

        # Check events were captured
        assert len(events) == 2
        assert events[0]["job_id"] == "job-123"
        assert events[0]["phase"] == "toc_analysis"
        assert events[1]["phase"] == "complete"