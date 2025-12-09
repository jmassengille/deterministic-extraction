"""Dependency injection for FastAPI routes."""

from typing import Annotated

from fastapi import Depends

from .jobs.service import JobService
from .storage.service import StorageService
from .services.progress_manager import ProgressManager
from .services.worker import WorkerManager

# Singleton service instances
_job_service = None
_storage_service = None
_progress_manager = None


def get_job_service() -> JobService:
    """Get JobService singleton instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


def get_storage_service() -> StorageService:
    """Get StorageService singleton instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


def get_progress_manager() -> ProgressManager:
    """Get ProgressManager singleton instance."""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager


def get_worker_manager() -> WorkerManager:
    """Get WorkerManager instance from main module."""
    from .main import worker_manager
    if worker_manager is None:
        raise RuntimeError("WorkerManager not initialized")
    return worker_manager


# Dependency annotations for type hints
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
ProgressManagerDep = Annotated[ProgressManager, Depends(get_progress_manager)]
WorkerManagerDep = Annotated[WorkerManager, Depends(get_worker_manager)]