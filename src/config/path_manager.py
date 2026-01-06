"""
Centralized path management.

Provides easy access to commonly used paths throughout the application.
All paths are resolved relative to the project base path.
"""

from pathlib import Path
from typing import Optional
from .config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)


class PathManager:
    """
    Centralized path management.
    
    Provides properties for commonly used paths, all resolved relative
    to the project base path from ConfigManager.
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize PathManager.
        
        Args:
            config_manager: ConfigManager instance. If None, creates a new one.
        """
        if config_manager is None:
            config_manager = ConfigManager()
        
        self.config = config_manager
        self.base_path = config_manager.base_path
        
        logger.debug(f"PathManager initialized. Base path: {self.base_path}")
    
    @property
    def data_raw(self) -> Path:
        """Path to raw data directory."""
        path = self.config.get_path("paths.data_raw", "data/raw")
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def data_processed(self) -> Path:
        """Path to processed data directory."""
        path = self.config.get_path("paths.data_processed", "data/processed")
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def logs(self) -> Path:
        """Path to logs directory."""
        path = self.config.get_path("paths.logs", "logs")
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def logs_agent(self) -> Path:
        """Path to agent log file."""
        return self.config.get_path("paths.logs_agent", "logs/agent.log")
    
    @property
    def logs_scheduling(self) -> Path:
        """Path to automatic scheduling log file."""
        return self.config.get_path("paths.logs_scheduling", "logs/automatic_scheduling.log")
    
    @property
    def logs_collectors(self) -> Path:
        """Path to collectors logs directory."""
        path = self.config.get_path("paths.logs_collectors", "logs/collectors")
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def logs_openai(self) -> Path:
        """Path to OpenAI calls log file."""
        return self.config.get_path("paths.logs_openai", "logs/openai_calls.csv")
    
    @property
    def config_dir(self) -> Path:
        """Path to config directory."""
        return self.config.config_dir
    
    @property
    def config_agent(self) -> Path:
        """Path to agent config file."""
        return self.config.get_path("paths.config_agent", "config/agent_config.json")
    
    @property
    def config_topic_embeddings(self) -> Path:
        """Path to topic embeddings config file."""
        return self.config.get_path("paths.config_topic_embeddings", "config/topic_embeddings.json")
    
    def get_log_file(self, name: str, subdirectory: Optional[str] = None) -> Path:
        """
        Get path to a log file.
        
        Args:
            name: Log file name (e.g., "my_log.log")
            subdirectory: Optional subdirectory within logs (e.g., "collectors")
        
        Returns:
            Path to the log file
        """
        if subdirectory:
            log_dir = self.logs / subdirectory
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir / name
        return self.logs / name
    
    def get_collector_log_dir(self, collector_name: str) -> Path:
        """
        Get log directory for a specific collector.
        
        Args:
            collector_name: Name of the collector
        
        Returns:
            Path to collector's log directory
        """
        log_dir = self.logs_collectors / collector_name
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    def ensure_exists(self, path: Path) -> Path:
        """
        Ensure a directory path exists (create if needed).
        
        Args:
            path: Path to ensure exists
        
        Returns:
            The path (for chaining)
        """
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_config_file(self, filename: str) -> Path:
        """
        Get path to a config file in the config directory.
        
        Args:
            filename: Config file name (e.g., "target_configs.json")
        
        Returns:
            Path to the config file
        """
        return self.config_dir / filename












