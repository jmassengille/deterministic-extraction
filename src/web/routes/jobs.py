"""Job management routes with pluggable format download support."""

from pathlib import Path
from uuid import UUID
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..dependencies import JobServiceDep, StorageServiceDep
from ..jobs.schemas import JobResponse, JobListResponse, JobStatus
from ..common.exceptions import JobNotFoundException, JobStateException, DatabaseException

router = APIRouter(prefix="/jobs", tags=["jobs"])


class FormatInfo(BaseModel):
    """Information about an available output format."""
    format: str
    available: bool
    path: Optional[str] = None
    files: List[Dict[str, str]] = []  # For multi-file formats


class AvailableFormatsResponse(BaseModel):
    """Response model for available download formats."""
    formats: List[FormatInfo]


@router.get("", response_model=JobListResponse)
async def list_jobs(
    jobs: JobServiceDep,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by status")
) -> JobListResponse:
    """List jobs with pagination and optional filtering."""
    try:
        return await jobs.list_jobs(
            page=page,
            per_page=limit,
            status=status
        )
    except DatabaseException as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, jobs: JobServiceDep) -> JobResponse:
    """Get job details by ID."""
    try:
        job = await jobs.get_job(job_id)
        return JobResponse.model_validate(job)
    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except DatabaseException as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: UUID, jobs: JobServiceDep) -> None:
    """Delete a job."""
    try:
        await jobs.delete_job(job_id, hard_delete=True)
    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except JobStateException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DatabaseException as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/formats", response_model=AvailableFormatsResponse)
async def get_available_formats(
    job_id: UUID,
    jobs: JobServiceDep
) -> AvailableFormatsResponse:
    """Get available download formats for a completed job."""
    try:
        job = await jobs.get_job(job_id)
        formats: List[FormatInfo] = []

        # Check output_paths for available formats
        output_paths = job.output_paths or {}
        for fmt, path_info in output_paths.items():
            if isinstance(path_info, str):
                # Single file format
                available = Path(path_info).exists()
                formats.append(FormatInfo(
                    format=fmt,
                    available=available,
                    path=path_info if available else None
                ))
            elif isinstance(path_info, dict):
                # Multi-file format (e.g., multiple intervals)
                files = []
                for key, path in path_info.items():
                    if Path(path).exists():
                        files.append({"key": key, "path": path})
                formats.append(FormatInfo(
                    format=fmt,
                    available=len(files) > 0,
                    files=files
                ))

        return AvailableFormatsResponse(formats=formats)

    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except DatabaseException as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/download")
async def download_file(
    job_id: UUID,
    jobs: JobServiceDep,
    storage: StorageServiceDep,
    format: str = Query("json", description="Output format from registered serializers"),
    key: Optional[str] = Query(None, description="For multi-file formats, the specific file key")
):
    """
    Download generated file for a completed job.

    Args:
        job_id: Job identifier
        format: Output format (from registered serializers)
        key: For multi-file formats, the specific file key

    Returns:
        File download response
    """
    try:
        job = await jobs.get_job(job_id)
        format_lower = format.lower().strip()

        return await _download_format(job, format_lower, key)

    except JobNotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except DatabaseException as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _download_format(job, format: str, key: Optional[str] = None) -> FileResponse:
    """Download output file for a job.

    Args:
        job: Job object with output_paths
        format: Output format name
        key: For multi-file formats, the specific file key

    Returns:
        FileResponse for download
    """
    output_paths = job.output_paths or {}

    if format not in output_paths:
        available = list(output_paths.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Format '{format}' not available. Available: {available}"
        )

    path_info = output_paths[format]

    # Handle single-file format
    if isinstance(path_info, str):
        file_path = Path(path_info)
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Output file for format '{format}' not found on disk"
            )
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type=_get_media_type(format)
        )

    # Handle multi-file format
    if isinstance(path_info, dict):
        if key is None:
            # Return first file if no key specified
            if not path_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"No files available for format '{format}'"
                )
            key = next(iter(path_info.keys()))

        if key not in path_info:
            available = list(path_info.keys())
            raise HTTPException(
                status_code=404,
                detail=f"File key '{key}' not found for format '{format}'. Available: {available}"
            )

        file_path = Path(path_info[key])
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Output file '{key}' for format '{format}' not found on disk"
            )
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type=_get_media_type(format)
        )

    raise HTTPException(
        status_code=500,
        detail=f"Invalid path info type for format '{format}'"
    )


def _get_media_type(format: str) -> str:
    """Get media type for a format.

    Args:
        format: Output format name

    Returns:
        MIME type string
    """
    media_types = {
        "json": "application/json",
        "xml": "application/xml",
        "csv": "text/csv",
        "txt": "text/plain",
    }
    return media_types.get(format.lower(), "application/octet-stream")