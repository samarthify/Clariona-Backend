"""
Unit tests for custom exception classes.

Tests exception hierarchy, message formatting, and error details.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exceptions import (
    BackendError,
    ConfigError,
    PathError,
    CollectionError,
    ProcessingError,
    AnalysisError,
    DatabaseError,
    APIError,
    ValidationError,
    RateLimitError,
    OpenAIError,
    NetworkError,
    FileError,
    LockError
)


class TestBackendError:
    """Test suite for BackendError base class."""
    
    def test_backend_error_initialization(self):
        """Test BackendError initialization."""
        error = BackendError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}
    
    def test_backend_error_with_details(self):
        """Test BackendError with details dictionary."""
        details = {"key1": "value1", "key2": 42}
        error = BackendError("Test error", details=details)
        
        assert error.message == "Test error"
        assert error.details == details
        assert "key1=value1" in str(error) or "key2=42" in str(error)
    
    def test_backend_error_inheritance(self):
        """Test that BackendError can be caught as Exception."""
        error = BackendError("Test error")
        
        # Should be catchable as Exception
        try:
            raise error
        except Exception as e:
            assert isinstance(e, BackendError)
            assert str(e) == "Test error"


class TestConfigError:
    """Test suite for ConfigError."""
    
    def test_config_error_initialization(self):
        """Test ConfigError initialization."""
        error = ConfigError("Configuration error")
        
        assert isinstance(error, BackendError)
        assert error.message == "Configuration error"
        assert str(error) == "Configuration error"
    
    def test_config_error_with_details(self):
        """Test ConfigError with details."""
        details = {"config_key": "invalid.key", "reason": "not found"}
        error = ConfigError("Config error", details=details)
        
        assert error.details == details


class TestPathError:
    """Test suite for PathError."""
    
    def test_path_error_initialization(self):
        """Test PathError initialization."""
        error = PathError("Path error")
        
        assert isinstance(error, BackendError)
        assert error.message == "Path error"
    
    def test_path_error_with_details(self):
        """Test PathError with path details."""
        details = {"path": "/invalid/path", "operation": "read"}
        error = PathError("Path not found", details=details)
        
        assert error.details["path"] == "/invalid/path"


class TestCollectionError:
    """Test suite for CollectionError."""
    
    def test_collection_error_initialization(self):
        """Test CollectionError initialization."""
        error = CollectionError("Collection failed")
        
        assert isinstance(error, BackendError)
        assert error.message == "Collection failed"


class TestProcessingError:
    """Test suite for ProcessingError."""
    
    def test_processing_error_initialization(self):
        """Test ProcessingError initialization."""
        error = ProcessingError("Processing failed")
        
        assert isinstance(error, BackendError)
        assert error.message == "Processing failed"


class TestAnalysisError:
    """Test suite for AnalysisError."""
    
    def test_analysis_error_initialization(self):
        """Test AnalysisError initialization."""
        error = AnalysisError("Analysis failed")
        
        assert isinstance(error, ProcessingError)
        assert isinstance(error, BackendError)
        assert error.message == "Analysis failed"


class TestDatabaseError:
    """Test suite for DatabaseError."""
    
    def test_database_error_initialization(self):
        """Test DatabaseError initialization."""
        error = DatabaseError("Database error")
        
        assert isinstance(error, BackendError)
        assert error.message == "Database error"


class TestAPIError:
    """Test suite for APIError."""
    
    def test_api_error_initialization(self):
        """Test APIError initialization."""
        error = APIError("API error")
        
        assert isinstance(error, BackendError)
        assert error.message == "API error"


class TestValidationError:
    """Test suite for ValidationError."""
    
    def test_validation_error_initialization(self):
        """Test ValidationError initialization."""
        error = ValidationError("Validation failed")
        
        assert isinstance(error, BackendError)
        assert error.message == "Validation failed"


class TestRateLimitError:
    """Test suite for RateLimitError."""
    
    def test_rate_limit_error_initialization(self):
        """Test RateLimitError initialization."""
        error = RateLimitError("Rate limit exceeded")
        
        assert isinstance(error, BackendError)
        assert error.message == "Rate limit exceeded"
        assert hasattr(error, 'retry_after')
    
    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError("Rate limit exceeded", retry_after=60.0)
        
        assert error.retry_after == 60.0
    
    def test_rate_limit_error_with_details(self):
        """Test RateLimitError with details."""
        details = {"limit": 100, "current": 101}
        error = RateLimitError("Rate limit exceeded", retry_after=60.0, details=details)
        
        assert error.retry_after == 60.0
        assert error.details == details


class TestOpenAIError:
    """Test suite for OpenAIError."""
    
    def test_openai_error_initialization(self):
        """Test OpenAIError initialization."""
        error = OpenAIError("OpenAI API error")
        
        assert isinstance(error, BackendError)
        assert error.message == "OpenAI API error"


class TestNetworkError:
    """Test suite for NetworkError."""
    
    def test_network_error_initialization(self):
        """Test NetworkError initialization."""
        error = NetworkError("Network error")
        
        assert isinstance(error, BackendError)
        assert error.message == "Network error"


class TestFileError:
    """Test suite for FileError."""
    
    def test_file_error_initialization(self):
        """Test FileError initialization."""
        error = FileError("File error")
        
        assert isinstance(error, BackendError)
        assert error.message == "File error"


class TestLockError:
    """Test suite for LockError."""
    
    def test_lock_error_initialization(self):
        """Test LockError initialization."""
        error = LockError("Lock error")
        
        assert isinstance(error, BackendError)
        assert error.message == "Lock error"


class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance."""
    
    def test_all_exceptions_inherit_from_backend_error(self):
        """Test that all custom exceptions inherit from BackendError."""
        exceptions = [
            ConfigError,
            PathError,
            CollectionError,
            ProcessingError,
            AnalysisError,
            DatabaseError,
            APIError,
            ValidationError,
            RateLimitError,
            OpenAIError,
            NetworkError,
            FileError,
            LockError
        ]
        
        for exc_class in exceptions:
            error = exc_class("Test")
            assert isinstance(error, BackendError)
            assert isinstance(error, Exception)
    
    def test_analysis_error_inherits_from_processing_error(self):
        """Test that AnalysisError inherits from ProcessingError."""
        error = AnalysisError("Test")
        assert isinstance(error, ProcessingError)
        assert isinstance(error, BackendError)
    
    def test_exception_catching(self):
        """Test that exceptions can be caught by base class."""
        try:
            raise ConfigError("Config error")
        except BackendError as e:
            assert isinstance(e, ConfigError)
            assert str(e) == "Config error"
        
        try:
            raise AnalysisError("Analysis error")
        except ProcessingError as e:
            assert isinstance(e, AnalysisError)
        except BackendError as e:
            assert isinstance(e, AnalysisError)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])








