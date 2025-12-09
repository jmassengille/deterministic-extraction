"""Storage-specific exceptions."""

from typing import Optional


class StorageException(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


class FileValidationError(StorageException):
    """Raised when file validation fails."""
    pass


class DiskSpaceError(StorageException):
    """Raised when insufficient disk space."""
    pass


class FileOperationError(StorageException):
    """Raised when file operation fails."""
    pass


class PDFValidationError(FileValidationError):
    """Raised when PDF validation fails."""
    pass