"""Storage management routes."""

import os
import shutil
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage.config import StorageConfig
from ..dependencies import JobServiceDep

router = APIRouter(prefix="/storage", tags=["storage"])


class StorageStats(BaseModel):
    """Storage statistics response."""
    total_space: int
    used_space: int
    available_space: int
    pdf_count: int
    pdf_size: int
    msf_count: int
    msf_size: int
    temp_files_count: int
    temp_files_size: int


class CleanupResponse(BaseModel):
    """Cleanup operation response."""
    deleted_pdfs: int
    deleted_msfs: int
    deleted_temp: int
    space_freed: int
    message: str


def get_directory_size(path: Path) -> int:
    """Calculate total size of directory."""
    total = 0
    if path.exists():
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    return total


def count_files_by_extension(path: Path, extension: str) -> tuple[int, int]:
    """Count files and total size by extension."""
    count = 0
    size = 0
    if path.exists():
        for item in path.rglob(f'*{extension}'):
            if item.is_file():
                count += 1
                size += item.stat().st_size
    return count, size


@router.get("/stats", response_model=StorageStats)
async def get_storage_stats() -> StorageStats:
    """Get storage usage statistics."""
    storage_path = Path(StorageConfig.STORAGE_ROOT)

    # Get disk usage
    stat = shutil.disk_usage(storage_path)

    # Count PDFs and MSFs
    pdf_count, pdf_size = count_files_by_extension(storage_path, '.pdf')
    msf_count, msf_size = count_files_by_extension(storage_path, '.msf')

    # Count temp files
    temp_path = Path(StorageConfig.TEMP_DIR)
    temp_count = 0
    temp_size = 0
    if temp_path.exists():
        for item in temp_path.rglob('*'):
            if item.is_file():
                temp_count += 1
                temp_size += item.stat().st_size

    return StorageStats(
        total_space=stat.total,
        used_space=stat.used,
        available_space=stat.free,
        pdf_count=pdf_count,
        pdf_size=pdf_size,
        msf_count=msf_count,
        msf_size=msf_size,
        temp_files_count=temp_count,
        temp_files_size=temp_size
    )


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_storage(
    jobs: JobServiceDep,
    delete_completed_pdfs: bool = True,
    delete_old_msfs: bool = False,
    msf_retention_days: int = 7,
    clear_temp: bool = True
) -> CleanupResponse:
    """
    Clean up storage by removing unnecessary files.

    Args:
        delete_completed_pdfs: Remove PDFs for completed jobs
        delete_old_msfs: Remove MSF files older than retention period
        msf_retention_days: Days to retain MSF files
        clear_temp: Clear temporary files
    """
    deleted_pdfs = 0
    deleted_msfs = 0
    deleted_temp = 0
    space_freed = 0

    try:
        # Clean PDFs for completed jobs
        if delete_completed_pdfs:
            completed_jobs = await jobs.get_completed_jobs()
            for job in completed_jobs:
                if job.pdf_path and Path(job.pdf_path).exists():
                    file_size = Path(job.pdf_path).stat().st_size
                    Path(job.pdf_path).unlink()
                    deleted_pdfs += 1
                    space_freed += file_size

        # Clean old MSF files
        if delete_old_msfs:
            cutoff_date = datetime.now() - timedelta(days=msf_retention_days)
            storage_path = Path(StorageConfig.STORAGE_ROOT)

            for msf_file in storage_path.rglob('*.msf'):
                if msf_file.stat().st_mtime < cutoff_date.timestamp():
                    file_size = msf_file.stat().st_size
                    msf_file.unlink()
                    deleted_msfs += 1
                    space_freed += file_size

        # Clear temp directory
        if clear_temp:
            temp_path = Path(StorageConfig.TEMP_DIR)
            if temp_path.exists():
                for item in temp_path.iterdir():
                    if item.is_file():
                        file_size = item.stat().st_size
                        item.unlink()
                        deleted_temp += 1
                        space_freed += file_size
                    elif item.is_dir():
                        dir_size = get_directory_size(item)
                        shutil.rmtree(item)
                        deleted_temp += 1
                        space_freed += dir_size

        return CleanupResponse(
            deleted_pdfs=deleted_pdfs,
            deleted_msfs=deleted_msfs,
            deleted_temp=deleted_temp,
            space_freed=space_freed,
            message=f"Cleanup completed. Freed {space_freed / (1024*1024):.2f} MB"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.delete("/jobs/bulk")
async def bulk_delete_jobs(
    job_ids: List[str],
    jobs: JobServiceDep
) -> Dict[str, Any]:
    """Delete multiple jobs and their associated files."""
    deleted_count = 0
    failed_ids = []
    space_freed = 0

    for job_id in job_ids:
        try:
            job = await jobs.get_job(job_id)

            # Delete PDF if exists
            if job.pdf_path and Path(job.pdf_path).exists():
                space_freed += Path(job.pdf_path).stat().st_size
                Path(job.pdf_path).unlink()

            # Delete MSF if exists
            if job.msf_path and Path(job.msf_path).exists():
                space_freed += Path(job.msf_path).stat().st_size
                Path(job.msf_path).unlink()

            # Delete job record
            await jobs.delete_job(job_id)
            deleted_count += 1

        except Exception as e:
            failed_ids.append(job_id)

    return {
        "deleted": deleted_count,
        "failed": failed_ids,
        "space_freed": space_freed,
        "message": f"Deleted {deleted_count} jobs, freed {space_freed / (1024*1024):.2f} MB"
    }