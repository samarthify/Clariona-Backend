"""
Centralized logging configuration for the Clariona Backend.

Provides consistent logging setup across all modules with configurable
log levels, formats, and handlers.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

# Try to import ConfigManager (may not be available during import)
try:
    from config.config_manager import ConfigManager
    from src.config.path_manager import PathManager
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


def get_log_level(level_name: str) -> int:
    """
    Convert log level name to logging constant.
    
    Args:
        level_name: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Logging level constant
    """
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    return level_map.get(level_name.upper(), logging.INFO)


def setup_logging(
    config_manager: Optional["ConfigManager"] = None,
    path_manager: Optional["PathManager"] = None,
    default_level: str = 'INFO',
    log_to_file: bool = True,
    log_to_console: bool = True
) -> None:
    """
    Setup centralized logging configuration.
    
    Args:
        config_manager: Optional ConfigManager instance (if None, uses defaults)
        path_manager: Optional PathManager instance (if None, creates new)
        default_level: Default log level if not in config
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
    """
    # Get log level from config or use default
    log_level = default_level
    if config_manager:
        log_level = config_manager.get('logging.level', default_level)
    
    # Get log format from config or use default
    if config_manager:
        log_format = config_manager.get(
            'logging.format',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        date_format = config_manager.get('logging.date_format', None)
    else:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        date_format = None
    
    # Create formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level(log_level))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []
    
    # Setup console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(get_log_level(log_level))
        console_handler.setFormatter(formatter)
        
        # Try to configure UTF-8 encoding for Windows
        if sys.platform == 'win32':
            try:
                if hasattr(console_handler.stream, 'reconfigure'):
                    console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        root_logger.addHandler(console_handler)
    
    # Setup file handler with rotation
    if log_to_file:
        try:
            # Get path manager
            if not path_manager:
                if CONFIG_AVAILABLE:
                    path_manager = PathManager()
                else:
                    # Fallback to default path
                    log_file_path = Path('logs') / 'backend.log'
                    log_file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_handler = RotatingFileHandler(
                        str(log_file_path),
                        maxBytes=10 * 1024 * 1024,  # 10MB
                        backupCount=5,
                        encoding='utf-8'
                    )
                    file_handler.setLevel(get_log_level(log_level))
                    file_handler.setFormatter(formatter)
                    root_logger.addHandler(file_handler)
                    return
            
            # Get log file path from config or path manager
            if config_manager:
                log_file_path_str = config_manager.get('logging.file_path', None)
                if log_file_path_str:
                    log_file_path = Path(log_file_path_str)
                else:
                    log_file_path = path_manager.logs / 'backend.log'
            else:
                log_file_path = path_manager.logs / 'backend.log'
            
            # Get rotation settings from config
            if config_manager:
                max_bytes = config_manager.get_int('logging.max_bytes', 10 * 1024 * 1024)  # 10MB default
                backup_count = config_manager.get_int('logging.backup_count', 5)
            else:
                max_bytes = 10 * 1024 * 1024  # 10MB
                backup_count = 5
            
            # Ensure log directory exists
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create rotating file handler
            file_handler = RotatingFileHandler(
                str(log_file_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(get_log_level(log_level))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
        except Exception as e:
            # Fallback: log error but don't fail
            print(f"Warning: Could not setup file logging: {e}")

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with standardized naming.
    
    Logger names should follow the pattern: module_name or ClassName
    This function ensures consistent naming across the codebase.
    
    Args:
        name: Logger name (typically __name__ or class name)
    
    Returns:
        Logger instance
    """
    # Normalize logger name (remove 'src.' prefix if present)
    if name.startswith('src.'):
        name = name[4:]
    
    return logging.getLogger(name)


def setup_module_logger(
    module_name: str,
    log_file: Optional[Path] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Setup a dedicated logger for a specific module with optional separate log file.
    
    Args:
        module_name: Name of the module/logger
        log_file: Optional separate log file path
        level: Optional log level (overrides root level)
    
    Returns:
        Logger instance
    """
    logger = get_logger(module_name)
    
    # Set level if provided
    if level:
        logger.setLevel(get_log_level(level))
    
    # Add file handler if log file specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            if level:
                file_handler.setLevel(get_log_level(level))
            else:
                file_handler.setLevel(logging.INFO)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.propagate = False  # Don't propagate to root logger
        except Exception as e:
            print(f"Warning: Could not setup file handler for {module_name}: {e}")
    
    return logger










