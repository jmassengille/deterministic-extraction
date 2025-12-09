"""Progress streaming routes using Server-Sent Events."""

from uuid import UUID
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..dependencies import ProgressManagerDep, JobServiceDep
from ..common.exceptions import JobNotFoundException

router = APIRouter(prefix="/jobs", tags=["progress"])


async def progress_event_stream(
    job_id: str,
    progress_manager: ProgressManagerDep,
    include_history: bool = True
) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted progress events for a job."""
    try:
        async for event in progress_manager.subscribe(job_id, include_history):
            yield event.to_sse()
    except Exception as e:
        # Send error event and close stream
        error_data = f'data: {{"error": "Stream error: {str(e)}"}}\n\n'
        yield error_data


@router.get("/{job_id}/progress")
async def stream_job_progress(
    job_id: UUID,
    progress_manager: ProgressManagerDep,
    jobs: JobServiceDep,
    include_history: bool = True
):
    """
    Stream real-time progress updates for a job via Server-Sent Events.

    Args:
        job_id: Job UUID to track
        include_history: Whether to send historical events first

    Returns:
        EventSourceResponse for SSE streaming
    """
    # Verify job exists
    try:
        await jobs.get_job(job_id)
    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create SSE stream
    return EventSourceResponse(
        progress_event_stream(
            job_id=str(job_id),
            progress_manager=progress_manager,
            include_history=include_history
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )