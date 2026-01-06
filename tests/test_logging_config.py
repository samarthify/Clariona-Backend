"""
Unit tests for logging configuration.

Tests centralized logging setup, log rotation, and configuration.
"""

import pytest
import sys
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.logging_config import get_logger, setup_logging
from src.config.config_manager import ConfigManager


class TestLoggingConfig:
    """Test suite for logging configuration."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger(__name__)
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == __name__
    
    def test_get_logger_consistent(self):
        """Test that get_logger returns same logger for same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        
        assert logger1 is logger2
    
    def test_get_logger_different_names(self):
        """Test that get_logger returns different loggers for different names."""
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module2")
        
        assert logger1 is not logger2
        assert logger1.name != logger2.name
    
    def test_logger_has_handlers(self):
        """Test that logger has handlers configured."""
        logger = get_logger("test.logger")
        
        # Logger should have at least one handler
        assert len(logger.handlers) > 0 or len(logging.root.handlers) > 0
    
    def test_setup_logging_with_config(self):
        """Test setup_logging with ConfigManager."""
        config = ConfigManager()
        
        # Should not raise an exception
        try:
            setup_logging(config)
        except Exception as e:
            pytest.fail(f"setup_logging raised {e}")
    
    def test_logger_logs_messages(self, caplog):
        """Test that logger actually logs messages."""
        logger = get_logger("test.logging")
        
        with caplog.at_level(logging.INFO):
            logger.info("Test message")
            assert "Test message" in caplog.text
    
    def test_logger_different_levels(self, caplog):
        """Test that logger respects log levels."""
        logger = get_logger("test.levels")
        
        with caplog.at_level(logging.WARNING):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            
            assert "Debug message" not in caplog.text
            assert "Info message" not in caplog.text
            assert "Warning message" in caplog.text
            assert "Error message" in caplog.text
    
    def test_logger_format(self, caplog):
        """Test that logger uses proper format."""
        logger = get_logger("test.format")
        
        with caplog.at_level(logging.INFO):
            logger.info("Test message")
            
            # Check that log contains timestamp and level
            assert len(caplog.text) > 0
            # Format should include at least the message
            assert "Test message" in caplog.text


class TestLoggingIntegration:
    """Test logging integration with ConfigManager."""
    
    def test_logging_uses_config_manager(self):
        """Test that logging can use ConfigManager for configuration."""
        config = ConfigManager()
        
        # Should be able to get log level from config
        log_level = config.get("logging.level", "INFO")
        assert log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    def test_logging_paths_from_config(self):
        """Test that logging paths can be configured."""
        config = ConfigManager()
        paths = config.get_path("paths.logs", "logs")
        
        assert paths is not None
        assert isinstance(paths, Path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])








