"""Custom exceptions for the web application."""

from typing import Optional, Dict, Any


class BaseAppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class JobNotFoundException(BaseAppException):
    """Raised when a job is not found."""
    pass


class JobStateException(BaseAppException):
    """Raised when a job state transition is invalid."""
    pass


class DatabaseException(BaseAppException):
    """Raised when database operations fail."""
    pass


class ValidationException(BaseAppException):
    """Raised when validation fails."""
    pass


class ProcessingException(BaseAppException):
    """Raised when PDF processing fails."""
    pass