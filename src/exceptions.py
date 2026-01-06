"""
Custom exception classes for the Clariona Backend.

All exceptions inherit from BackendError to allow catching all backend-specific
exceptions while still allowing specific exception handling.
"""

from typing import Optional


class BackendError(Exception):
    """
    Base exception for all backend-specific errors.
    
    All custom exceptions should inherit from this class to allow
    catching all backend errors with a single exception type.
    """
    def __init__(self, message: str, details: Optional[dict] = None):
        """
        Initialize backend error.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigError(BackendError):
    """Raised when configuration errors occur."""
    pass


class PathError(BackendError):
    """Raised when path-related errors occur."""
    pass


class CollectionError(BackendError):
    """Raised when data collection errors occur."""
    pass


class ProcessingError(BackendError):
    """Raised when data processing errors occur."""
    pass


class AnalysisError(ProcessingError):
    """Raised when analysis-specific errors occur (sentiment, governance, etc.)."""
    pass


class DatabaseError(BackendError):
    """Raised when database operation errors occur."""
    pass


class APIError(BackendError):
    """Raised when API-related errors occur."""
    pass


class ValidationError(BackendError):
    """Raised when data validation errors occur."""
    pass


class RateLimitError(BackendError):
    """Raised when rate limit errors occur (wraps external rate limit errors)."""
    def __init__(self, message: str, retry_after: Optional[float] = None, details: Optional[dict] = None):
        """
        Initialize rate limit error.
        
        Args:
            message: Human-readable error message
            retry_after: Optional seconds to wait before retrying
            details: Optional dictionary with additional error details
        """
        super().__init__(message, details)
        self.retry_after = retry_after


class OpenAIError(BackendError):
    """Raised when OpenAI API errors occur."""
    pass


class NetworkError(BackendError):
    """Raised when network-related errors occur."""
    pass


class FileError(BackendError):
    """Raised when file operation errors occur."""
    pass


class LockError(BackendError):
    """Raised when lock-related errors occur (e.g., stuck locks)."""
    pass


