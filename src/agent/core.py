# Standard library imports
import os
import sys
import json
import time
import glob
import re
import uuid
import logging
import subprocess
import threading
import queue
import asyncio
import multiprocessing
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Optional
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# Enable UTF-8 mode on Windows to support emoji characters in logs
if sys.platform == 'win32':
    try:
        # For Python 3.7+, enable UTF-8 mode
        if hasattr(sys, 'set_int_max_str_digits'):
            os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass

# Third-party imports
import pandas as pd
import numpy as np
import requests
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import or_

# Local imports - config
from src.config.path_manager import PathManager
from src.config.config_manager import ConfigManager
from src.config.logging_config import setup_logging, get_logger

# Local imports - exceptions
# Add src to path for imports (needed for exceptions module)
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))
from exceptions import NetworkError, FileError, CollectionError

# Local imports - utils
from src.utils.mail_config import NOTIFY_ON_ANALYSIS
from src.utils.notification_service import send_analysis_report, send_processing_notification, send_collection_notification
from src.utils.deduplication_service import DeduplicationService
from src.utils.common import parse_datetime, safe_int, safe_float

# Local imports - processing
from src.processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
# from src.processing.data_processor import DataProcessor
from src.processing.topic_classifier import TopicClassifier
from src.processing.issue_detection_engine import IssueDetectionEngine
from src.processing.emotion_analyzer import EmotionAnalyzer

# Local imports - API models
from src.api.models import TargetIndividualConfiguration, EmailConfiguration
from src.api.models import MentionTopic, TopicIssue, IssueMention # Needed for type hinting/data saving helpers
import src.api.models as models  # Added for location classification update

# Initialize PathManager at module level for logging setup
_path_manager = PathManager()

# Configure logging
# Configure handlers with UTF-8 encoding to support emoji characters
handlers = []

# StreamHandler with UTF-8 encoding for console
try:
    stream_handler = logging.StreamHandler()
    stream_handler.setStream(sys.stderr)
    # Set encoding to UTF-8 for Windows console
    if hasattr(stream_handler.stream, 'reconfigure'):
        stream_handler.stream.reconfigure(encoding='utf-8')
    handlers.append(stream_handler)
except Exception as e:
    # Fallback to default handler
    handlers.append(logging.StreamHandler())
    print(f"Warning: Could not configure UTF-8 encoding for console: {e}")

# FileHandler with UTF-8 encoding
try:
    # Use PathManager for log file path
    log_file_path = _path_manager.logs_agent
    # Ensure logs directory exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(log_file_path), encoding='utf-8')
    handlers.append(file_handler)
except Exception as e:
    print(f"Warning: Could not create logs directory: {e}")

# Use centralized logging configuration if available
try:
    from src.config.logging_config import setup_logging, get_logger
    setup_logging(config_manager=ConfigManager(), path_manager=_path_manager)
    logger = get_logger('agent.core')
except ImportError:
    # Fallback to basic config if logging_config not available
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    logger = logging.getLogger('agent.core')

# Create dedicated logger for automatic scheduling with separate log file
def setup_auto_schedule_logger():
    """Setup dedicated logger for automatic scheduling with detailed timestamps."""
    auto_schedule_logger = logging.getLogger('AutoSchedule')
    auto_schedule_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    auto_schedule_logger.handlers = []
    
    # Create formatter with detailed timestamp
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler for automatic scheduling logs
    try:
        # Use PathManager for log file path
        log_file_path = _path_manager.logs_scheduling
        # Ensure logs directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        auto_schedule_file_handler = logging.FileHandler(
            str(log_file_path), 
            encoding='utf-8'
        )
        auto_schedule_file_handler.setLevel(logging.INFO)
        auto_schedule_file_handler.setFormatter(formatter)
        auto_schedule_logger.addHandler(auto_schedule_file_handler)
        auto_schedule_logger.propagate = False  # Don't propagate to root logger
    except Exception as e:
        logger.error(f"Failed to setup automatic scheduling logger: {e}")
    
    return auto_schedule_logger

# Initialize automatic scheduling logger (still used by run_single_cycle_parallel for logging)
auto_schedule_logger = setup_auto_schedule_logger()

# Define API endpoint URL (Best practice: move to config or env var)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000") # Default for local dev
# DATA_UPDATE_ENDPOINT removed - /data/update endpoint removed


def convert_uuid_to_str(obj):
    """Convert UUID fields in the object to strings."""
    if isinstance(obj, dict):
        return {key: convert_uuid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_uuid_to_str(item) for item in obj]
    elif isinstance(obj, UUID):
        return str(obj)  # Convert UUID to string
    return obj

class SentimentAnalysisAgent:
    """Core agent responsible for data collection, processing, analysis, and scheduling."""

    def __init__(self, db_factory: sessionmaker, config_path=None):
        """
        Initialize the agent.

        Args:
            db_factory (sessionmaker): SQLAlchemy session factory.
            config_path (str): Path to the agent's configuration file. If None, uses PathManager default.
        """
        self.db_factory = db_factory
        # Initialize PathManager for centralized path management
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path  # For backward compatibility
        
        # Initialize ConfigManager for centralized configuration
        self.config_manager = ConfigManager()
        
        # Use PathManager for default config path if not provided
        if config_path is None:
            config_path = str(self.path_manager.config_agent)
        self.config_path = Path(config_path)
        from src.utils.deduplication_service import DeduplicationService
        self.deduplication_service = DeduplicationService()
        logger.debug(f"SentimentAnalysisAgent.__init__ started. db_factory: {db_factory}, config_path: {config_path}")
        self.config = self.load_config() # Load config from file (excluding target)
        self.status = "idle"
        self.last_run_times = {"collect": None, "process": None, "cleanup": None}
        self.data_history = {
            "collected": [], 
            "processed": [], 
            "sentiment_trends": [], 
            "events": [], 
            "data_quality_metrics": [],
            "system_health": []
        }
        
        # Legacy parallel processing configuration removed - not used by AnalysisWorker
        # Legacy scheduler configuration removed - not used by AnalysisWorker
        # Legacy task status tracking removed - not used by AnalysisWorker
        
        
        # Keep reference to sentiment analyzer for backward compatibility
        self.sentiment_analyzer = PresidentialSentimentAnalyzer()
        
        # --- Restore Critical Components (Topic, Issue, Emotion) ---
        # These were previously hidden in DataProcessor. We now init them directly.
        # Initialize lazily or with error handling to avoid startup crashes if models missing.
        
        try:
            logger.debug("Initializing EmotionAnalyzer...")
            self.emotion_analyzer = EmotionAnalyzer()
        except Exception as e:
            logger.warning(f"Failed to initialize EmotionAnalyzer: {e}")
            self.emotion_analyzer = None

        try:
            logger.debug("Initializing TopicClassifier...")
            self.topic_classifier = TopicClassifier()
        except Exception as e:
            logger.warning(f"Failed to initialize TopicClassifier: {e}")
            self.topic_classifier = None

        try:
            logger.debug("Initializing IssueDetectionEngine...")
            self.issue_detection_engine = IssueDetectionEngine()
        except Exception as e:
            logger.warning(f"Failed to initialize IssueDetectionEngine: {e}")
            self.issue_detection_engine = None
            
        # -------------------------------------------------------------
        
        # Initialize enhanced location classifier
        self.location_classifier = self._init_location_classifier()
        
        # Legacy configuration logging removed
        
        logger.debug("Agent initialization complete")
        
    # Scheduler methods removed - scheduler not used (we use run_cycles.sh instead)
    # Removed: start_automatic_scheduling, stop_automatic_scheduling, get_scheduler_status,
    #          _run_scheduler_loop, _get_active_users, _is_user_auto_scheduling_enabled,
    #          _should_run_collection, _run_automatic_collection_tracked
    
    def _run_automatic_collection(self, user_id: str):
        """Run automatic collection for a specific user (used by /agent/test-cycle-no-auth endpoint)."""
        logger.info(f"Starting collection cycle for user {user_id}")
        # Use parallel processing
        self.run_single_cycle_parallel(user_id)
        logger.info(f"Completed collection cycle for user {user_id}")

        logger.info(f"Agent initialized. Config loaded from {self.config_path}. Base path: {self.base_path}")
        logger.info(f"Database session factory provided: {db_factory}")
        logger.debug(f"SentimentAnalysisAgent.__init__ finished. Initial config: {self.config}")

    def _parse_date_string(self, date_str):
        """Parse date string to datetime object using shared utility function, return None if invalid"""
        # Use shared parse_datetime utility function from common.py
        return parse_datetime(date_str)
    
    def _validate_and_clean_location(self, location):
        """
        Validate and clean location data during ingestion.
        Filters out generic/non-location values and normalizes valid locations.
        
        Args:
            location: Raw location string from data source
            
        Returns:
            Cleaned location string or None if invalid/generic
        """
        if not location or pd.isna(location):
            return None
        
        # Convert to string and strip whitespace
        location = str(location).strip()
        
        if not location or location.lower() in ('none', 'null', 'nan', ''):
            return None
        
        location_lower = location.lower()
        
        # List of generic/non-location values to exclude
        generic_locations = [
            'unknown', 'wherever you are', 'earth', 'mars', 'world',
            'global', 'worldwide', 'everywhere', 'somewhere', 'nowhere',
            'africa', 'europe', 'asia', 'america', 'united states',
            'united kingdom', 'canada', 'australia', 'planet earth',
            'the world', 'around the world', 'anywhere', 'nowhere',
            'hidden', 'secret', 'private', 'n/a', 'na', 'none'
        ]
        
        # Check if location is a generic/non-location value
        for generic in generic_locations:
            if location_lower == generic or location_lower.startswith(generic + ',') or location_lower.endswith(',' + generic):
                return None
        
        # Check for URLs, IP addresses, or other non-location patterns
        # URLs
        if location_lower.startswith('http://') or location_lower.startswith('https://') or location_lower.startswith('www.'):
            return None
        
        # IP addresses (basic check)
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', location):
            return None
        
        # Email addresses
        if '@' in location and '.' in location:
            return None
        
        # Clean up common formatting issues
        # Remove extra whitespace
        location = ' '.join(location.split())
        
        # Remove trailing commas and periods
        location = location.rstrip(',.')
        
        # Normalize common variations
        # "Nigeria" variations
        if location_lower in ('nigeria', 'nigeria '):
            return 'Nigeria'
        
        # Return cleaned location
        return location if location else None

    def load_config(self) -> Dict[str, Any]:
        """Load agent configuration using ConfigManager, excluding the 'target' key."""
        logger.debug(f"load_config: Loading config using ConfigManager")
        
        # Agent-specific default config (keys not in ConfigManager defaults)
        agent_defaults = {
            "collection_interval_minutes": 60,
            "processing_interval_minutes": 120,
            "data_retention_days": 30,
            "sentiment_model": "default",
            "analysis_level": "medium",
            "sources": {"twitter": True, "news": True, "blogs": False},
            "keywords": ["important person"], # General keywords, not target specific
            "adaptive_scheduling": True,
            "auto_optimization": True,
            "rate_limits": {"twitter": 100, "news": 50},
            "openai_logging": {
                "enabled": False,
                "log_path": str(self.path_manager.logs_openai),
                "max_chars": 2000,
                "redact_prompts": False
            },
            "auto_scheduling": {
                "enabled": False,
                "enabled_user_ids": [],
                "cycle_interval_minutes": 60
            }
            # 'target' key is intentionally omitted - fetched from DB
        }
        
        # Get config from ConfigManager (already loads agent_config.json)
        # ConfigManager merges agent_config.json into top-level config
        config_manager_config = self.config_manager._config.copy()
        
        # Remove 'target' key if it exists (shouldn't be in config anymore, but safety check)
        config_manager_config.pop('target', None)
        
        # Merge agent defaults with ConfigManager config
        # Agent defaults take precedence for missing keys, but ConfigManager values override
        merged_config = agent_defaults.copy()
        merged_config.update(config_manager_config)
        
        # Ensure parallel_processing is accessible (ConfigManager maps it to processing.parallel)
        # For backward compatibility, also add it at top level if processing.parallel exists
        if 'processing' in config_manager_config and 'parallel' in config_manager_config['processing']:
            merged_config['parallel_processing'] = config_manager_config['processing']['parallel']
        
        logger.debug(f"load_config: Loaded config using ConfigManager with {len(merged_config)} top-level keys")
        return merged_config

    def _get_latest_target_config(self, db: Session, user_id: str) -> Optional[TargetIndividualConfiguration]:
        """Fetches the latest target config model object from DB for a specific user."""
        if not user_id:
            logger.warning("_get_latest_target_config: No user_id provided.")
            return None
        try:
            # Convert string user_id to UUID if needed
            from uuid import UUID
            if isinstance(user_id, str):
                user_id_uuid = UUID(user_id)
            else:
                user_id_uuid = user_id
            
            # Query for the specific user's configuration
            latest_config = db.query(TargetIndividualConfiguration)\
                              .filter(TargetIndividualConfiguration.user_id == user_id_uuid)\
                              .order_by(TargetIndividualConfiguration.created_at.desc())\
                              .first()
            logger.debug(f"_get_latest_target_config: Found config for user {user_id}: {latest_config}")
            return latest_config
        except Exception as e:
            logger.error(f"Error getting target config for user {user_id}: {e}", exc_info=True)
            return None

    def _get_email_config_for_user(self, db: Session, user_id: str) -> Optional[EmailConfiguration]:
        """Fetches the latest email config model object from DB for a specific user."""
        if not user_id:
            logger.warning("_get_email_config_for_user: No user_id provided.")
            return None
        try:
            latest_config = db.query(EmailConfiguration)\
                              .filter(EmailConfiguration.user_id == user_id)\
                              .order_by(EmailConfiguration.created_at.desc())\
                              .first()
            logger.debug(f"_get_email_config_for_user: Found config for user {user_id}: {latest_config}")
            return latest_config
        except Exception as e:
            logger.error(f"Error getting email config for user {user_id}: {e}", exc_info=True)
            return None

    def collect_data_parallel(self, user_id: str):
        """Collect data by running multiple collectors in parallel for a specific user."""
        if not user_id:
            logger.error("collect_data_parallel: Called without a user_id. Aborting.")
            return False
        
        logger.info(f"Starting parallel data collection cycle for user {user_id}...")
        self.status = "collecting"
        
        try:
            # Get target config from DB
            with self.db_factory() as db:
                logger.debug("collect_data_parallel: Fetching target config from database...")
                target_config = self._get_latest_target_config(db, user_id)
                
                if not target_config:
                    logger.error(f"No target configuration found for user {user_id}. Please configure target first.")
                    return False
                
                target_name = target_config.individual_name
                query_variations = target_config.query_variations
                
                if not query_variations:
                    logger.warning(f"User {user_id} has no query variations configured. Using only target name.")
                    query_variations = []
                
                logger.info(f"Using target: {target_name} with {len(query_variations)} query variations")
            
            # Prepare query list: [target_name, query1, query2, ...]
            target_and_variations = [target_name] + query_variations
            queries_json = json.dumps(target_and_variations)
            logger.debug(f"Passing queries as JSON: {queries_json}")

            # Get enabled collectors for parallel execution
            enabled_collectors = self._get_enabled_collectors_for_target(target_name)
            if not enabled_collectors:
                logger.warning(f"No enabled collectors found for target: {target_name}")
                return False
            
            actual_collector_workers = min(self.max_collector_workers, len(enabled_collectors))
            logger.info(f"Running {len(enabled_collectors)} collectors in parallel with {self.max_collector_workers} workers (actual: {actual_collector_workers})")
            auto_schedule_logger.info(f"[PHASE 1: COLLECTION] Collectors: {len(enabled_collectors)} | Max Workers: {self.max_collector_workers} | Actual Workers: {actual_collector_workers}")
            
            # Execute collectors in parallel
            collection_results = self._run_collectors_parallel(enabled_collectors, queries_json, user_id)
            
            # Check results
            successful_collectors = sum(1 for success in collection_results.values() if success)
            total_collectors = len(collection_results)
            
            logger.info(f"Parallel collection completed: {successful_collectors}/{total_collectors} collectors succeeded")
            
            collection_success = successful_collectors > 0  # At least one collector must succeed
                
        except Exception as e:
            logger.error(f"Error during parallel data collection: {e}", exc_info=True)
            collection_success = False
        
        finally:
            self.status = "idle"
        
        return collection_success

    def _map_collector_to_source_type(self, collector_name: str) -> str:
        """Map collector module name to source type for collection tracker."""
        mapping = {
            'collect_twitter_apify': 'twitter',
            'collect_news_apify': 'news',
            'collect_news_from_api': 'news',
            'collect_facebook_apify': 'facebook',
            'collect_instagram_apify': 'instagram',
            'collect_tiktok_apify': 'tiktok',
            'collect_reddit_apify': 'reddit',
            'collect_youtube_api': 'youtube',
            'collect_radio_hybrid': 'radio',  # Using radio_hybrid, not radio_apify
            'collect_rss_nigerian_qatar_indian': 'rss',
        }
        return mapping.get(collector_name, collector_name.replace('collect_', '').replace('_apify', '').replace('_hybrid', '').replace('_from_api', ''))
    
    def _get_enabled_collectors_for_target(self, target_name: str) -> List[str]:
        """Get list of enabled collectors for a specific target."""
        try:
            # Import target config manager
            from src.collectors.target_config_manager import TargetConfigManager
            config_manager = TargetConfigManager()
            
            # Get target configuration from name
            target_config = config_manager.get_target_by_name(target_name)
            if not target_config:
                logger.warning(f"Target '{target_name}' not found in configuration")
                return []
            
            # Find target_id by matching the config
            target_id = None
            for tid, tconfig in config_manager.targets.items():
                if tconfig == target_config:
                    target_id = tid
                    break
            
            if not target_id:
                logger.warning(f"Could not find target ID for {target_name}")
                return []
            
            # Get enabled collectors for this target
            enabled_collectors = config_manager.get_enabled_collectors(target_id)
            logger.info(f"Enabled collectors for {target_name}: {enabled_collectors}")
            
            return enabled_collectors
            
        except Exception as e:
            logger.error(f"Error getting enabled collectors for target {target_name}: {e}")
            return []
    
    def _run_collectors_parallel(self, collectors: List[str], queries_json: str, user_id: str) -> Dict[str, bool]:
        """Run multiple collectors in parallel using ThreadPoolExecutor with incremental date ranges."""
        results = {}
        
        # Import collection tracker
        from src.utils.collection_tracker import get_collection_tracker
        tracker = get_collection_tracker()
        
        # Create logs/collectors directory if it doesn't exist
        collector_logs_dir = self.path_manager.logs_collectors
        
        # Create separate log file for each collector in its own subfolder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        collector_log_files = {}
        
        for collector_name in collectors:
            # Sanitize collector name for folder and filename (remove 'collect_' prefix if present)
            safe_name = collector_name.replace('collect_', '').replace('_', '-')
            
            # Create subdirectory for this collector
            collector_subdir = collector_logs_dir / safe_name
            collector_subdir.mkdir(parents=True, exist_ok=True)
            
            # Create log file in the collector's subdirectory
            log_file = collector_subdir / f"{safe_name}_{timestamp}.log"
            collector_log_files[collector_name] = log_file
            logger.info(f"📝 {collector_name} output will be written to: {log_file}")
        
        # Get incremental date ranges for all collectors
        date_ranges = {}
        for collector_name in collectors:
            # Map collector_name to source type for tracker
            source_type = self._map_collector_to_source_type(collector_name)
            date_range = tracker.get_incremental_date_range(user_id, source_type)
            date_ranges[collector_name] = date_range
            logger.info(f"📅 {collector_name}: {date_range['since_date_iso']} to {date_range['until_date_iso']}")
        
        def run_single_collector(collector_name: str) -> bool:
            """Run a single collector and return success status."""
            try:
                logger.info(f"Starting collector: {collector_name}")
                
                # Prepare environment
                env = os.environ.copy()
                env['COLLECTOR_USER_ID'] = str(user_id)
                env['COLLECTOR_TYPE'] = collector_name
                env['APIFY_TIMEOUT_SECONDS'] = str(self.apify_timeout)
                env['APIFY_WAIT_SECONDS'] = str(self.apify_wait)

                # Construct command for specific collector
                command = [
                    sys.executable, "-m", f"src.collectors.{collector_name}", 
                    "--queries", queries_json
                ]
                
                # Add incremental date range if available
                # Skip date arguments for collectors that don't support them
                collectors_without_date_support = ['collect_rss_nigerian_qatar_indian', 'collect_rss']
                
                date_range = date_ranges.get(collector_name, {})
                if 'since_date' in date_range and 'until_date' in date_range:
                    if collector_name not in collectors_without_date_support:
                        # Use appropriate date format based on collector type
                        if 'news' in collector_name:
                            # News uses ISO format
                            command.extend(["--since", date_range['since_date_iso']])
                            command.extend(["--until", date_range['until_date_iso']])
                        else:
                            # Twitter and others use underscore format
                            command.extend(["--since", date_range['since_date']])
                            command.extend(["--until", date_range['until_date']])
                        logger.info(f"🔄 Using incremental dates for {collector_name}")
                    else:
                        logger.info(f"ℹ️  Skipping date arguments for {collector_name} (not supported)")
                
                logger.debug(f"Executing {collector_name}: {' '.join(command)}")
                
                # Get individual log file for this collector
                collector_log_file = collector_log_files.get(collector_name)
                if not collector_log_file:
                    # Fallback to default name if not found
                    safe_name = collector_name.replace('collect_', '').replace('_', '-')
                    collector_subdir = collector_logs_dir / safe_name
                    collector_subdir.mkdir(parents=True, exist_ok=True)
                    collector_log_file = collector_subdir / f"{safe_name}_{timestamp}.log"
                
                # Open individual log file in append mode and redirect stdout/stderr to it
                with open(collector_log_file, 'a', encoding='utf-8') as log_fp:
                    # Write header for this collector
                    log_fp.write(f"{'='*80}\n")
                    log_fp.write(f"COLLECTOR: {collector_name}\n")
                    log_fp.write(f"STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    log_fp.write(f"USER_ID: {user_id}\n")
                    log_fp.write(f"QUERIES: {queries_json}\n")
                    if 'since_date' in date_range and 'until_date' in date_range:
                        log_fp.write(f"DATE_RANGE: {date_range.get('since_date_iso', date_range.get('since_date'))} to {date_range.get('until_date_iso', date_range.get('until_date'))}\n")
                    log_fp.write(f"{'='*80}\n\n")
                    log_fp.flush()

                    try:
                        process = subprocess.run(
                            command,
                            stdout=log_fp,
                            stderr=subprocess.STDOUT,  # Merge stderr into stdout
                            text=True,
                            check=False,
                            cwd=self.base_path,
                            env=env,
                            timeout=self.collector_timeout  # NEW: Enforce timeout
                        )
                    except subprocess.TimeoutExpired as e:
                        # Collector exceeded timeout - log and mark as failed
                        logger.error(
                            f"⏱️ TIMEOUT: {collector_name} exceeded {self.collector_timeout}s timeout. "
                            f"Terminating subprocess..."
                        )

                        # Write timeout marker to log file
                        log_fp.write(f"\n{'='*80}\n")
                        log_fp.write(f"TIMEOUT: Collector exceeded {self.collector_timeout}s limit\n")
                        log_fp.write(f"TERMINATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        log_fp.write(f"{'='*80}\n\n")
                        log_fp.flush()

                        # Update collection tracker on timeout
                        source_type = self._map_collector_to_source_type(collector_name)
                        tracker.update_collection_time(
                            user_id=user_id,
                            source=source_type,
                            timestamp=datetime.utcnow(),
                            records_collected=0,
                            status='timeout'
                        )

                        return False  # Indicate failure
                
                # Write completion footer to log file
                with open(collector_log_file, 'a', encoding='utf-8') as log_fp:
                    log_fp.write(f"\n{'='*80}\n")
                    if process.returncode == 0:
                        log_fp.write(f"COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        log_fp.write(f"STATUS: SUCCESS (return code: {process.returncode})\n")
                    else:
                        log_fp.write(f"COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        log_fp.write(f"STATUS: FAILED (return code: {process.returncode})\n")
                    log_fp.write(f"{'='*80}\n\n")
                    log_fp.flush()
                
                if process.returncode == 0:
                    logger.info(f"✅ {collector_name} completed successfully")
                    
                    # Update collection tracker on success
                    source_type = self._map_collector_to_source_type(collector_name)
                    tracker.update_collection_time(
                        user_id=user_id,
                        source=source_type,
                        timestamp=datetime.utcnow(),
                        records_collected=0,  # TODO: Parse from collector output
                        status='success'
                    )
                    logger.debug(f"📝 Updated collection tracker for {source_type}")
                    
                    return True
                else:
                    logger.error(f"❌ {collector_name} failed with return code: {process.returncode}")
                    
                    # Update collection tracker on failure
                    source_type = self._map_collector_to_source_type(collector_name)
                    tracker.update_collection_time(
                        user_id=user_id,
                        source=source_type,
                        timestamp=datetime.utcnow(),
                        records_collected=0,
                        status='failed'
                    )
                    
                    # Read and log the last few lines of the collector's log file on error
                    try:
                        collector_log_file = collector_log_files.get(collector_name)
                        if not collector_log_file:
                            safe_name = collector_name.replace('collect_', '').replace('_', '-')
                            collector_subdir = collector_logs_dir / safe_name
                            collector_subdir.mkdir(parents=True, exist_ok=True)
                            collector_log_file = collector_subdir / f"{safe_name}_{timestamp}.log"
                        
                        with open(collector_log_file, 'r', encoding='utf-8') as log_fp:
                            lines = log_fp.readlines()
                            if lines:
                                # Show last 20 lines from the collector's log file
                                last_lines = lines[-20:] if len(lines) > 20 else lines
                                if last_lines:
                                    logger.error(f"Last lines from {collector_name} log ({collector_log_file.name}):")
                                    for line in last_lines:
                                        logger.error(f"  {line.rstrip()}")
                    except Exception as e:
                        logger.error(f"Could not read collector log: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"💥 {collector_name} failed with exception: {e}")
                return False
        
        # Execute collectors in parallel
        with ThreadPoolExecutor(max_workers=self.max_collector_workers) as executor:
            # Submit all collector tasks
            future_to_collector = {
                executor.submit(run_single_collector, collector): collector 
                for collector in collectors
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_collector):
                collector = future_to_collector[future]
                try:
                    results[collector] = future.result()
                except Exception as e:
                    logger.error(f"Exception in {collector}: {e}")
                    results[collector] = False
        
        return results

    # --- Command Execution ---
    # update_config needs to change as 'target' is no longer managed here
    def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a command on the agent."""
        params = params or {}
        logger.info(f"Executing command: {command} with params: {params}")
        try:
            if command == "start":
                self.start()
                return {"success": True, "message": "Agent started"}
            elif command == "stop":
                self.stop()
                return {"success": True, "message": "Agent stopped"}
            elif command == "status":
                return {"success": True, "data": self.get_status()}
            # Update config - remove target handling
            elif command == "update_config":
                # Remove 'target' from params if present, as it's handled by API/DB now
                params.pop('target', None) 
                if not params:
                     return {"success": False, "message": "No valid configuration parameters provided for update."}
                self.config.update(params)
                self._save_config() # Save the updated config (without target)
                # Maybe re-initialize parts of the agent if needed based on config change?
                logger.info(f"Agent configuration updated (excluding target): {params}")
                return {"success": True, "message": "Agent configuration updated successfully (target is managed separately via API)."}
            elif command == "get_config":
                 # Return current config (which no longer includes target)
                 return {"success": True, "data": self.config}
            elif command == "run_collection":
                # --- Requires user_id now ---
                if 'user_id' not in params:
                    return {"success": False, "message": "run_collection command requires 'user_id' parameter."}
                # You might want to ensure this runs in a separate thread or async
                self._run_task(lambda: self.collect_data_parallel(params['user_id']), f"collect_cmd_{params['user_id']}") 
                return {"success": True, "message": f"Collection task triggered for user {params['user_id']}."}
            elif command == "run_processing":
                # --- Requires user_id now ---
                if 'user_id' not in params:
                    return {"success": False, "message": "run_processing command requires 'user_id' parameter."}
                # Similar thread/async consideration for processing
                self._run_task(lambda: self.run_single_cycle_parallel(params['user_id']), f"process_cmd_{params['user_id']}") 
                return {"success": True, "message": f"Processing task triggered for user {params['user_id']}."}
            elif command == "update_locations":
                # --- Requires user_id now ---
                if 'user_id' not in params:
                    return {"success": False, "message": "update_locations command requires 'user_id' parameter."}
                # If batch_size not provided, None will use config default
                batch_size = params.get('batch_size', None)
                self._run_task(lambda: self.update_location_classifications(params['user_id'], batch_size), f"location_update_cmd_{params['user_id']}") 
                return {"success": True, "message": f"Location classification update triggered for user {params['user_id']} with batch size {batch_size or 'config default'}."}
            # Add other commands as needed
            else:
                return {"success": False, "message": f"Unknown command: {command}"}
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def _save_config(self):
        """Save the current agent configuration (excluding target) to the JSON file."""
        try:
            # Ensure target is not accidentally saved
            config_to_save = self.config.copy()
            config_to_save.pop('target', None) 
            with open(self.config_path, 'w') as f:
                json.dump(config_to_save, f, indent=4, default=str)
            logger.info(f"Agent configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}", exc_info=True)

    # --- Placeholder methods for agent lifecycle and tasks ---
    def start(self):
        # Logic to start the agent's main loop/scheduler
        logger.debug("start: Entering method.")
        logger.info("Agent starting... (Scheduler disabled)") # Modified log message
        # self.stop_event.clear() 
        # # Example: Start scheduler thread if using 'schedule' library
        # self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        # logger.debug("start: Starting scheduler thread.")
        # self.scheduler_thread.start()
        logger.debug("start: Finished method (No scheduler started).")

    def stop(self):
        # Logic to gracefully stop the agent
        logger.debug("stop: Entering method.")
        logger.info("Agent stopping... (Scheduler disabled)") # Modified log message
        # self.stop_event.set()
        # # Example: Wait for threads to join
        # if self.scheduler_thread:
        #     self.scheduler_thread.join()
        # logger.debug("stop: Stop event set.")
        pass # Add actual stop logic if needed (e.g., closing resources)
        logger.debug("stop: Finished method.")

    def _check_and_release_stuck_lock(self, task_name: str) -> bool:
        """
        Check if the current lock is stuck (exceeded max age) and force-release it.

        Args:
            task_name: Name of the task trying to acquire the lock

        Returns:
            True if lock was force-released, False if no action taken
        """
        if not self.task_status['is_busy']:
            return False  # No lock to check

        if not self.task_status.get('lock_time'):
            # Lock exists but no timestamp (legacy state) - force release
            logger.warning(f"Found lock without timestamp for task '{self.task_status['current_task']}'. Force-releasing.")
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None
            return True

        # Calculate lock age
        lock_time = datetime.fromisoformat(self.task_status['lock_time'])
        lock_age = (datetime.now() - lock_time).total_seconds()

        if lock_age > self.lock_max_age:
            # Lock is stuck - force release
            logger.error(
                f"🚨 FORCE-RELEASING STUCK LOCK! "
                f"Task '{self.task_status['current_task']}' has been locked for {lock_age:.1f}s "
                f"(max: {self.lock_max_age}s). Requested by: '{task_name}'"
            )

            # Record the stuck lock in last_run for debugging
            stuck_task = self.task_status['current_task']
            self.task_status['last_run'][f"{stuck_task}_FORCE_RELEASED"] = {
                'time': lock_time.isoformat(),
                'success': False,
                'duration': lock_age,
                'error': f'Lock exceeded max age ({self.lock_max_age}s) and was force-released'
            }

            # Release the lock
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None

            return True

        # Lock is valid
        logger.debug(f"Lock age: {lock_age:.1f}s (max: {self.lock_max_age}s) - valid")
        return False

    def _check_and_release_stuck_lock(self, task_name: str) -> bool:
        try:
            # Read CSVs individually and parse dates afterwards
            all_data_list = []
            potential_date_columns = ['published_date', 'date', 'published_at', 'timestamp'] # Possible date column names across all formats
            
            logger.info(f"Reading and processing {len(all_raw_files)} raw files...")
            for f in all_raw_files:
                try:
                    # Read without initial date parsing
                    df = pd.read_csv(f, on_bad_lines='warn')
                    logger.debug(f"Read {len(df)} rows from {f.name}. Columns: {list(df.columns)}")
                    
                    # Identify and parse existing date columns for this specific file
                    dates_to_parse_in_this_df = [col for col in potential_date_columns if col in df.columns]
                    if dates_to_parse_in_this_df:
                        logger.debug(f"Attempting to parse date columns {dates_to_parse_in_this_df} in {f.name} using custom parser.")
                        for date_col in dates_to_parse_in_this_df:
                            # Apply custom parser
                            df[date_col] = df[date_col].apply(self.data_processor.parse_date)
                            # Check how many dates failed parsing (optional) - result will be None
                            parse_failures = df[date_col].isnull().sum() # Count None values
                            original_count = len(df[date_col])
                            # We need a baseline of non-null before parsing to calculate actual failures
                            # This is tricky as the input could be mixed types. Let's just log null count.
                            if parse_failures > 0:
                                 logger.debug(f"Column '{date_col}' in {f.name} has {parse_failures}/{original_count} null/unparsed values after custom parsing.")
                    else:
                         logger.debug(f"No standard date columns found in {f.name}")
                         
                    all_data_list.append(df)
                    
                except pd.errors.EmptyDataError:
                     logger.warning(f"Raw file {f.name} is empty. Skipping.")
                except Exception as e_read:
                    logger.warning(f"Could not read or process file {f.name}: {e_read}. Skipping file.")
            
            if not all_data_list:
                 logger.error("No valid raw data could be aggregated from any files.")
                 return False
                 
            # Concatenate all processed dataframes
            all_data = pd.concat(all_data_list, ignore_index=True)
            logger.info(f"Successfully aggregated {len(all_data)} records from {len(all_data_list)} non-empty files.")

        except Exception as e:
            logger.error(f"Error aggregating raw data: {e}", exc_info=True)
            return False # Indicate failure

        # --- Data Cleaning & Preprocessing ---
        initial_count = len(all_data)
        # Define potential identifier columns for deduplication
        # Use 'url' or 'text' + 'timestamp'/'published_date' as potential keys
        dedup_subset = []
        if 'url' in all_data.columns:
             dedup_subset.append('url')
        elif 'text' in all_data.columns:
             dedup_subset.append('text')
             # Try to find a reliable timestamp column for deduplication
             if 'published_date' in all_data.columns:
                 dedup_subset.append('published_date')
             elif 'timestamp' in all_data.columns:
                 dedup_subset.append('timestamp')
             elif 'date' in all_data.columns:
                 dedup_subset.append('date')
        
        if dedup_subset:
             try:
                # Ensure subset columns actually exist before dropping
                valid_dedup_subset = [col for col in dedup_subset if col in all_data.columns]
                if valid_dedup_subset:
                     all_data.drop_duplicates(subset=valid_dedup_subset, inplace=True, keep='first')
                     cleaned_count = len(all_data)
                     logger.info(f"Removed {initial_count - cleaned_count} duplicate records based on {valid_dedup_subset}.")
                else:
                     logger.warning(f"Could not perform deduplication, subset columns {dedup_subset} not found after aggregation.")
                     cleaned_count = initial_count
             except KeyError:
                 # This shouldn't happen with the check above, but keep for safety
                 logger.warning(f"KeyError during deduplication using {valid_dedup_subset}. Columns might not exist after aggregation.")
                 cleaned_count = initial_count # Assume no duplicates removed
        else:
             logger.warning("Could not determine suitable columns for deduplication (e.g., 'url' or 'text' + timestamp).")
             cleaned_count = initial_count
        # ... other cleaning steps ...

        # --- Sentiment Analysis ---
        try:
            logger.info("Performing presidential sentiment analysis...")
            target_individual_name_for_analysis = "the President" # Default presidential perspective
            with self.db_factory() as db_session: # Changed variable name for clarity
                target_config = self._get_latest_target_config(db_session, user_id)
                if target_config and target_config.individual_name:
                    target_individual_name_for_analysis = target_config.individual_name
                    logger.info(f"Presidential sentiment analysis will use perspective of: {target_individual_name_for_analysis}")
                    # Update the presidential analyzer with the target individual name
                    self.sentiment_analyzer.president_name = target_individual_name_for_analysis
                else:
                    logger.warning(f"No specific target individual found for user {user_id} or name is empty. Using default presidential perspective for sentiment analysis.")

            if 'text' in all_data.columns:
                 if hasattr(self, 'sentiment_analyzer') and self.sentiment_analyzer is not None:
                     sentiment_results = all_data['text'].apply(
                        lambda x: self.sentiment_analyzer.analyze(x) if isinstance(x, str) and pd.notna(x) else {
                            'sentiment_label': 'neutral', 
                            'sentiment_score': 0.0, 
                            'sentiment_justification': None,
                            'issue_label': 'Unlabeled Content',
                            'issue_slug': 'unlabeled-content',
                            'issue_confidence': 0.0,
                            'issue_keywords': [],
                            'ministry_hint': None,
                            'embedding': [0.0] * 1536
                        }
                     )
                     # Assign all fields from the results
                     all_data['sentiment_label'] = sentiment_results.apply(lambda res: res['sentiment_label'])
                     all_data['sentiment_score'] = sentiment_results.apply(lambda res: res['sentiment_score'])
                     all_data['sentiment_justification'] = sentiment_results.apply(lambda res: res['sentiment_justification'])
                     all_data['issue_label'] = sentiment_results.apply(lambda res: res.get('issue_label', 'Unlabeled Content'))
                     all_data['issue_slug'] = sentiment_results.apply(lambda res: res.get('issue_slug', 'unlabeled-content'))
                     all_data['issue_confidence'] = sentiment_results.apply(lambda res: res.get('issue_confidence', 0.0))
                     all_data['issue_keywords'] = sentiment_results.apply(lambda res: json.dumps(res.get('issue_keywords', [])))
                     all_data['ministry_hint'] = sentiment_results.apply(lambda res: res.get('ministry_hint', None))
                     all_data['embedding'] = sentiment_results.apply(lambda res: json.dumps(res.get('embedding', [0.0] * 1536)))
                     logger.info("Sentiment analysis completed.")
                     processed_df = all_data
                 else:
                     logger.error("Sentiment analyzer is not initialized. Skipping sentiment analysis.")
                     # Decide if processing should continue without sentiment - for now, let's stop.
                     return False
            else:
                 logger.error("Column 'text' not found for sentiment analysis.")
                 # Decide if processing should continue without sentiment - for now, let's stop.
                 return False
        except Exception as e:
            logger.error(f"Error during sentiment analysis: {e}", exc_info=True)
            return False

        # --- Enhanced Location Classification ---
        try:
            logger.info("Performing enhanced location classification...")
            if 'text' in all_data.columns and self.location_classifier:
                # Apply location classification to each row with metadata
                location_results = []
                for idx, row in all_data.iterrows():
                    text = row.get('text', '')
                    platform = row.get('platform', '')
                    source = row.get('source', '')
                    user_location = row.get('user_location', '')
                    user_name = row.get('user_name', '')
                    user_handle = row.get('user_handle', '')
                    
                    location_label, location_confidence = self.location_classifier.classify(
                        text, platform, source, user_location, user_name, user_handle
                    )
                    location_results.append((location_label, location_confidence))
                
                # Assign location results to DataFrame
                all_data['location_label'] = [res[0] for res in location_results]
                all_data['location_confidence'] = [res[1] for res in location_results]
                logger.info("Enhanced location classification completed.")
                
                # Update processed_df reference
                processed_df = all_data
            else:
                logger.warning("Location classifier not available or text column missing. Skipping enhanced location classification.")
                all_data['location_label'] = None
                all_data['location_confidence'] = None
                processed_df = all_data
        except Exception as e:
            logger.error(f"Error during enhanced location classification: {e}", exc_info=True)
            all_data['location_label'] = None
            all_data['location_confidence'] = None
            processed_df = all_data

        # --- Prepare Data for API (Ensure user_id is included) ---
        if processed_df.empty:
             logger.warning("Processed data is empty after cleaning/analysis. Nothing to send to API.")
             # Clean up raw files? Let's do it here as well.
             logger.info("Cleaning up raw data files as processed data is empty...")
             for f in all_raw_files:
                 try: os.remove(f)
                 except Exception: pass
             return True # Processing technically succeeded, just no output

        try:
            logger.info(f"Preparing {len(processed_df)} records for API update...")
            processed_df_copy = processed_df.copy()

            # **Rename identifier column to 'id' for the API payload**
            if 'original_id' in processed_df_copy.columns:
                processed_df_copy.rename(columns={'original_id': 'id'}, inplace=True)
                logger.info("Renamed DataFrame column 'original_id' to 'id' for API.")
            elif 'post_id' in processed_df_copy.columns and 'id' not in processed_df_copy.columns:
                processed_df_copy.rename(columns={'post_id': 'id'}, inplace=True)
                logger.info("Renamed DataFrame column 'post_id' to 'id' for API as 'original_id' was missing.")
            elif 'id' not in processed_df_copy.columns:
                 logger.warning("Column 'id', 'original_id', or 'post_id' not found in processed data. API might require an 'id'.")
                 # Optionally add an 'id' column with None if strictly required by API
                 # processed_df_copy['id'] = None

            # **Ensure 'id' column is string type**
            if 'id' in processed_df_copy.columns:
                 logger.debug(f"Converting 'id' column to string type. Original dtype: {processed_df_copy['id'].dtype}")
                 # Use astype(str) which handles numbers; None/NaN becomes 'None'/'nan' string
                 processed_df_copy['id'] = processed_df_copy['id'].astype(str)
                 # Replace 'nan' string resulting from NaN conversion with None if necessary 
                 # (Depends if API allows 'nan' string or requires actual null/None)
                 # processed_df_copy['id'] = processed_df_copy['id'].replace('nan', None)
                 logger.debug(f"Converted 'id' column to string type. New dtype: {processed_df_copy['id'].dtype}")
            else:
                 logger.warning("Could not convert 'id' to string as column doesn't exist.")

            # **Convert ALL specified datetime columns to ISO format string**
            datetime_cols = ['published_date', 'date', 'published_at', 'timestamp'] # Match DataRecord fields + legacy timestamp
            for col in datetime_cols:
                if col in processed_df_copy.columns:
                    # Ensure column is actually datetime type (it should be if parsing worked)
                    if pd.api.types.is_datetime64_any_dtype(processed_df_copy[col]):
                         logger.debug(f"Processing datetime column '{col}'.")
                         # Remove timezone info if present (API/DB expects naive)
                         if hasattr(processed_df_copy[col].dt, 'tz') and processed_df_copy[col].dt.tz is not None:
                            processed_df_copy[col] = processed_df_copy[col].dt.tz_localize(None)
                            logger.debug(f"Made column '{col}' timezone-naive.")
                            
                         # Convert valid datetimes to ISO format, leave NaT/None as None
                         processed_df_copy[col] = processed_df_copy[col].apply(
                            lambda x: x.isoformat(timespec='seconds') if pd.notna(x) else None
                         )
                         logger.debug(f"Converted column '{col}' to ISO format string for API.")
                    else:
                         # If the column exists but isn't datetime, it might be strings that failed parsing earlier
                         # We'll nullify them to avoid sending bad data to the API
                         logger.warning(f"Column '{col}' exists but is not datetime type ({processed_df_copy[col].dtype}). Nullifying values for API.")
                         processed_df_copy[col] = None 
                else:
                     logger.debug(f"Expected datetime column '{col}' not found in DataFrame. Skipping conversion.")

            # **Convert NaNs/NaTs to None for JSON compatibility (handles all columns)**
            # This is crucial for numeric/boolean columns that might have NaNs
            processed_df_copy = processed_df_copy.where(pd.notnull(processed_df_copy), None)
            logger.debug("Converted NaN/NaT values to None using .where().")

            # **Additionally, replace np.inf, -np.inf, and potentially explicit np.nan with None**
            # This covers cases .where might miss or if NaN representation is unusual
            processed_df_copy = processed_df_copy.replace([np.inf, -np.inf, np.nan], None)
            logger.debug("Replaced np.inf, -np.inf, and np.nan with None using .replace().")

            # Select only columns that match the DataRecord model fields to avoid sending extra data
            # Get fields from the DataRecord model (requires importing it or defining the list)
            # For simplicity, define the list here based on service.py DataRecord
            expected_api_fields = [
                'title', 'description', 'content', 'url', 'published_date', 'source',
                'source_url', 'query', 'language', 'platform', 'date', 'text',
                'file_source', 'id', 'alert_id', 'published_at', 'source_type',
                'country', 'favorite', 'tone', 'source_name', 'parent_url', 'parent_id',
                'children', 'direct_reach', 'cumulative_reach', 'domain_reach', 'tags',
                'score', 'alert_name', 'type', 'post_id', 'retweets', 'likes',
                'user_location', 'comments', 'user_name', 'user_handle', 'user_avatar',
                'sentiment_label', 'sentiment_score', 'sentiment_justification',
                'location_label', 'location_confidence'
            ]
            
            # Filter DataFrame columns to only include expected fields
            columns_to_send = [col for col in expected_api_fields if col in processed_df_copy.columns]
            processed_df_for_api = processed_df_copy[columns_to_send]
            logger.info(f"Filtered DataFrame to include {len(columns_to_send)} columns matching API model.")

            # Convert the filtered DataFrame to list of dicts
            data_list = processed_df_for_api.to_dict(orient='records')
            # --- Add user_id to the payload --- 
            payload = {
                "user_id": user_id, 
                "data": convert_uuid_to_str(data_list)
            }
            # ----------------------------------

            # --- DEBUGGING: Log first few records of the payload (KEEP THIS) ---
            try:
                 log_sample_size = min(3, len(data_list))
                 if log_sample_size > 0:
                     logger.debug(f"Sample of first {log_sample_size} records being sent to API:")
                     for i in range(log_sample_size):
                         # Use json.dumps for cleaner representation of None vs NaN etc.
                         # This will now include sentiment_justification if present in data_list[i]
                         logger.debug(f"Record {i+1}: {json.dumps(data_list[i], indent=2, default=str)}")
                 else:
                     logger.debug("Payload contains no records.")
            except Exception as log_e:
                 logger.error(f"Error logging payload sample: {log_e}")
            # --- END DEBUGGING ---

        except Exception as e:
            logger.error(f"Error preparing data for API: {e}", exc_info=True)
            return False

        # --- Send Data to API ---
        api_call_successful = False # Flag to track success
        api_message = "Unknown API status"
        try:
            # Get HTTP request timeout from config
            try:
                config_manager = ConfigManager()
                http_timeout = config_manager.get_int("processing.timeouts.http_request_timeout", 120)
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for HTTP timeout, using default 120s: {e}")
                http_timeout = 120
            
            logger.info(f"Sending {len(data_list)} records to API endpoint: {DATA_UPDATE_ENDPOINT}")
            # response = requests.post(DATA_UPDATE_ENDPOINT, json=payload, timeout=120) 
            response = requests.post(DATA_UPDATE_ENDPOINT, json=convert_uuid_to_str(payload), timeout=http_timeout)
            # response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Check HTTP status code first
            if 200 <= response.status_code < 300:
                 try:
                     api_response_json = response.json()
                     api_message = api_response_json.get('message', f"OK (Status {response.status_code})")
                     # Explicit check for success key, defaulting to True if status is OK and key missing
                     # Treat as failure ONLY if 'success' is explicitly false
                     api_call_successful = api_response_json.get('success', True) 
                     if api_call_successful:
                          logger.info(f"API update successful: {api_message}")
                     else:
                          # API returned 2xx but 'success: false' in body
                          logger.error(f"API returned success status ({response.status_code}) but indicated failure in response body: {api_message}")
                          
                 except json.JSONDecodeError:
                      # Successful status code but couldn't parse JSON response
                      logger.warning(f"API returned success status ({response.status_code}) but response body was not valid JSON. Treating as success based on status code.")
                      api_message = f"OK (Status {response.status_code}, Non-JSON response)"
                      api_call_successful = True # Assume success based on HTTP status
            else:
                 # Handle non-2xx status codes
                 logger.error(f"API request failed with status code {response.status_code}.")
                 try:
                     error_detail = response.json()
                     # Use .get with a default for message key
                     api_message = error_detail.get('message', f"Error (Status {response.status_code}, JSON body present but no message)")
                     logger.error(f"API Error Response Body: {json.dumps(error_detail, indent=2)}")
                 except json.JSONDecodeError:
                     api_message = f"Error (Status {response.status_code}, Non-JSON response)"
                     logger.error(f"API Error Response Body (non-JSON): {response.text}")
                 api_call_successful = False # Explicitly false

            # --- Post-processing based on api_call_successful (Use DB Config for specific user) --- 
            if api_call_successful:
                # Clean up raw files only on success
                logger.info("Cleaning up raw data files...")
                for f in all_raw_files:
                    try:
                        os.remove(f)
                    except Exception as e_rm:
                        logger.warning(f"Could not remove raw file {f}: {e_rm}")
                logger.info("Raw data files cleaned up.")

                # Post-Processing Notifications (Using DB Config for specific user)
                logger.info(f"Data processing finished successfully for user {user_id}. Processed {len(processed_df)} records.") 
                try:
                    # Check DB config for processing notifications
                    recipients = []
                    notify_processing_enabled = False
                    with self.db_factory() as db:
                        # --- Fetch email config specifically for this user_id ---
                        latest_email_config = self._get_email_config_for_user(db, user_id)
                        # ---------------------------------------------------------
                        if latest_email_config:
                             logger.debug(f"[DB Email Config - Processing Check for user {user_id}] Found config ID: {latest_email_config.id}")
                             logger.debug(f"[DB Email Config - Processing Check for user {user_id}] Enabled: {latest_email_config.enabled}")
                             logger.debug(f"[DB Email Config - Processing Check for user {user_id}] Notify on Processing: {latest_email_config.notify_on_processing}")
                             logger.debug(f"[DB Email Config - Processing Check for user {user_id}] Recipients: {latest_email_config.recipients}")
                        else:
                             logger.debug(f"[DB Email Config - Processing Check for user {user_id}] No config found.")

                        if latest_email_config and latest_email_config.enabled:
                            if latest_email_config.notify_on_processing:
                                notify_processing_enabled = True
                                if latest_email_config.recipients:
                                    recipients = latest_email_config.recipients
                                else:
                                    logger.warning(f"Processing notifications enabled for user {user_id}, but no recipients configured.")
                            else:
                                logger.info(f"Processing notifications are disabled for user {user_id} (notify_on_processing=False).")
                        elif not latest_email_config:
                             logger.warning(f"No email configuration found in the database for user {user_id} processing notification check.")

                    # Send notification if enabled and recipients exist
                    if notify_processing_enabled and recipients:
                        logger.info(f"Attempting to send processing completion email for user {user_id} to DB recipients: {recipients}")
                        try:
                            # Define processing_data for the notification function
                            processing_data = {
                                "status": "success",
                                "processed_count": len(processed_df),
                                "raw_file_count": len(all_raw_files),
                                "timestamp": datetime.now().isoformat()
                            }
                            # Assuming send_processing_notification exists and accepts db_factory
                            send_processing_notification(processing_data, recipients, self.db_factory)
                            logger.info("Processing completion email triggered successfully.")
                        except Exception as e:
                            logger.error(f"Error triggering processing completion email: {str(e)}", exc_info=True)

                except Exception as e:
                    logger.error(f"Error checking DB or sending processing notification: {str(e)}", exc_info=True)
            else: # API call failed 
                 logger.error(f"Data processing failed for user {user_id}. API Status: {api_message}")
                 # Optionally send a failure notification here if desired
                 # Save data locally on failure
                 timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                 failed_api_path = processed_data_path / f'failed_api_update_{timestamp_str}.csv'
                 try:
                     # Save the data *before* it was converted to dict list
                     processed_df.to_csv(failed_api_path, index=False)
                     logger.info(f"Saved data locally due to API failure: {failed_api_path}")
                 except Exception as e_save:
                     logger.error(f"Failed to save backup data locally: {e_save}")
            
            return api_call_successful # Return the determined success status

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send data to API: {e}")
            # Log the specific error if possible
            if e.response is not None:
                 try:
                     error_detail = e.response.json()
                     logger.error(f"API Error Response Body: {json.dumps(error_detail, indent=2)}")
                 except json.JSONDecodeError:
                     logger.error(f"API Error Response Body (non-JSON): {e.response.text}")
            # Decide how to handle failure: Maybe save locally as backup?
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            failed_api_path = processed_data_path / f'failed_api_update_{timestamp_str}.csv'
            try:
                # Save the data *before* it was converted to dict list
                processed_df.to_csv(failed_api_path, index=False)
                logger.info(f"Saved data locally due to API failure: {failed_api_path}")
            except Exception as e_save:
                logger.error(f"Failed to save backup data locally: {e_save}")
            return False # Indicate failure
        except Exception as e:
             logger.error(f"An unexpected error occurred after preparing data: {e}", exc_info=True)
             return False

    def _check_and_release_stuck_lock(self, task_name: str) -> bool:
        """
        Check if the current lock is stuck (exceeded max age) and force-release it.

        Args:
            task_name: Name of the task trying to acquire the lock

        Returns:
            True if lock was force-released, False if no action taken
        """
        if not self.task_status['is_busy']:
            return False  # No lock to check

        if not self.task_status.get('lock_time'):
            # Lock exists but no timestamp (legacy state) - force release
            logger.warning(f"Found lock without timestamp for task '{self.task_status['current_task']}'. Force-releasing.")
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None
            return True

        # Calculate lock age
        lock_time = datetime.fromisoformat(self.task_status['lock_time'])
        lock_age = (datetime.now() - lock_time).total_seconds()

        if lock_age > self.lock_max_age:
            # Lock is stuck - force release
            logger.error(
                f"🚨 FORCE-RELEASING STUCK LOCK! "
                f"Task '{self.task_status['current_task']}' has been locked for {lock_age:.1f}s "
                f"(max: {self.lock_max_age}s). Requested by: '{task_name}'"
            )

            # Record the stuck lock in last_run for debugging
            stuck_task = self.task_status['current_task']
            self.task_status['last_run'][f"{stuck_task}_FORCE_RELEASED"] = {
                'time': lock_time.isoformat(),
                'success': False,
                'duration': lock_age,
                'error': f'Lock exceeded max age ({self.lock_max_age}s) and was force-released'
            }

            # Release the lock
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None

            return True

        # Lock is valid
        logger.debug(f"Lock age: {lock_age:.1f}s (max: {self.lock_max_age}s) - valid")
        return False

    def _run_task(self, task_func: Callable, task_name: str) -> bool:
        """Runs a given task function, updates status, and handles basic timing/errors."""
        logger.debug(f"_run_task: Preparing to run task '{task_name}'. Current busy status: {self.task_status['is_busy']}")

        # Check for stuck locks before rejecting the task
        if self.task_status['is_busy']:
            # Try to auto-unlock if stuck
            was_released = self._check_and_release_stuck_lock(task_name)

            if was_released:
                logger.warning(f"Stuck lock was released. Proceeding with task '{task_name}'.")
            else:
                # Lock is valid and active
                lock_age = None
                if self.task_status.get('lock_time'):
                    lock_time = datetime.fromisoformat(self.task_status['lock_time'])
                    lock_age = (datetime.now() - lock_time).total_seconds()

                logger.warning(
                    f"Agent is already busy with task: {self.task_status['current_task']} "
                    f"(locked for {lock_age:.1f}s). Cannot start '{task_name}'."
                )
                return False # Indicate task did not run
            
        logger.debug(f"_run_task: Starting task '{task_name}'...")
        self.task_status['is_busy'] = True
        self.task_status['current_task'] = task_name
        start_time = datetime.now()
        self.task_status['lock_time'] = start_time.isoformat()  # NEW: Track lock time
        
        # Record task start in last_run immediately (prevents scheduler from re-scheduling)
        self.task_status['last_run'][task_name] = {
            'time': start_time.isoformat(),
            'success': None,  # Will be updated in finally block
            'duration': 0,
            'error': None,
            'status': 'running'  # Indicates task is currently running
        }
        
        logger.debug(f"Lock acquired at {self.task_status['lock_time']} for task '{task_name}'")
        success = False 
        error_info = None

        try:
            # Assuming tasks are synchronous for now
            # If async tasks are needed, inspect.iscoroutinefunction and event loop logic would be required here
            result = task_func() 
            # We assume the task function returns True on success, False or raises Exception on failure
            if isinstance(result, bool):
                success = result
            else:
                 # If task doesn't return boolean, assume success if no exception occurred
                 success = True 
                 logger.debug(f"Task '{task_name}' completed but did not return explicit boolean status.")

        except Exception as e:
            logger.error(f"Error during task '{task_name}': {e}", exc_info=True)
            success = False
            error_info = str(e)

        finally:
            duration = (datetime.now() - start_time).total_seconds()
            self.task_status['last_run'][task_name] = {
                'time': start_time.isoformat(),
                'success': success,
                'duration': duration,
                'error': error_info
            }
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None  # NEW: Clear lock time
            logger.info(f"Finished task: {task_name}. Success: {success}. Duration: {duration:.2f}s.")
            logger.debug(f"Lock released for task '{task_name}' after {duration:.2f}s")
            
        logger.debug(f"_run_task: Task '{task_name}' finished with status: {success}")
        return success # Return the success status of the task

    def run_single_cycle_parallel(self, user_id: str, use_existing_data: bool = False, skip_collection_only: bool = False):
        """
        Runs a single collection and processing cycle for a specific user with parallel processing.
        
        Args:
            user_id: User ID to process
            use_existing_data: If True, skips data collection, loading, and deduplication phases,
                             and uses existing embeddings/sentiment from database (skips OpenAI calls when both exist)
            skip_collection_only: If True, skips collection/loading/deduplication but processes ALL existing records
                                in database normally (with OpenAI calls for missing embeddings/sentiment)
        """
        if not user_id:
            logger.error("run_single_cycle_parallel: Called without user_id. Aborting.")
            return

        try:
            collection_duration = 0.0
            load_duration = 0.0
            dedup_duration = 0.0
            collection_start = datetime.now()
            
            if use_existing_data:
                # Skip collection, loading, and deduplication - use existing data in database
                logger.info(f"Using existing data mode: Skipping collection, loading, and deduplication for user {user_id}")
                auto_schedule_logger.info(f"[PHASE 1-3: SKIPPED] User: {user_id} | Mode: Use Existing Data | Skipping: Collection, Loading, Deduplication")
                collect_success = True
                load_success = True
                dedup_success = True
            elif skip_collection_only:
                # Skip collection, loading, and deduplication - but process ALL existing records normally
                logger.info(f"Skip collection mode: Skipping collection, loading, and deduplication for user {user_id}. Will process ALL existing records normally.")
                auto_schedule_logger.info(f"[PHASE 1-3: SKIPPED] User: {user_id} | Mode: Skip Collection Only | Skipping: Collection, Loading, Deduplication | Will process all existing records with OpenAI calls")
                collect_success = True
                load_success = True
                dedup_success = True
            if skip_collection_only:
                # Streaming Mode: Collection/Loading done by background service.
                # We just verify if deduplication/cleanup is needed, though DataIngestor handles most of it.
                logger.info(f"Streaming Mode: Skipping batch collection/loading for user {user_id}. Proceeding to analysis.")
                auto_schedule_logger.info(f"[PHASE 1-2: SKIPPED] User: {user_id} | Mode: Streaming | Background service handles ingestion")
                collect_success = True
                load_success = True
                
                # 3. Quick Deduplication (Safety Check)
                # Ideally DataIngestor handles this, but a quick sweep before analysis doesn't hurt
                dedup_start = datetime.now()
                # logger.info(f"Running safety deduplication for user {user_id}...")
                # dedup_success = self._run_task(lambda: self._run_deduplication(user_id), f'dedup_{user_id}')
                dedup_success = True # Skip explicit dedup for now, rely on strict constraints
            else:
                # LEGACY BATCH MODE (Deprecated but kept for manual runs if needed)
                # 1. Parallel Data Collection
                collection_start = datetime.now()
                logger.info(f"Starting parallel data collection for user {user_id}...")
                collect_success = self._run_task(lambda: self.collect_data_parallel(user_id), f'collect_user_{user_id}')
                
                if collect_success:
                    # 2. Load raw data
                    load_start = datetime.now()
                    load_success = self._run_task(lambda: self._push_raw_data_to_db(user_id), f'load_raw_{user_id}')
                    if load_success:
                        # 3. Deduplication
                        dedup_success = self._run_task(lambda: self._run_deduplication(user_id), f'dedup_{user_id}')
                    else:
                        dedup_success = False
                else:
                    load_success = False
                    dedup_success = False

            
            if dedup_success:
                    # 4. Parallel sentiment analysis (configurable batch size)
                    sentiment_start = datetime.now()
                    logger.info(f"Starting parallel sentiment analysis for user {user_id}...")
                    auto_schedule_logger.info(f"[PHASE 4: SENTIMENT ANALYSIS START] User: {user_id} | Timestamp: {sentiment_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    auto_schedule_logger.info(f"[PHASE 4: SENTIMENT] Max Workers: {self.max_sentiment_workers} | Batch Size: {self.sentiment_batch_size}")
                    sentiment_success = self._run_task(
                        lambda: self._run_sentiment_batch_update_parallel(user_id, use_existing_data=use_existing_data, skip_collection_only=skip_collection_only), 
                        f'sentiment_batch_{user_id}'
                    )
                    sentiment_end = datetime.now()
                    sentiment_duration = (sentiment_end - sentiment_start).total_seconds()
                    if sentiment_success:
                        auto_schedule_logger.info(f"[PHASE 4: SENTIMENT ANALYSIS END] User: {user_id} | Timestamp: {sentiment_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {sentiment_duration:.2f}s | Max Workers: {self.max_sentiment_workers} | Status: SUCCESS")
                    else:
                        auto_schedule_logger.error(f"[PHASE 4: SENTIMENT ANALYSIS END] User: {user_id} | Timestamp: {sentiment_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {sentiment_duration:.2f}s | Max Workers: {self.max_sentiment_workers} | Status: FAILED")
                    
                    # 5. Parallel location classification (configurable batch size)
                    location_start = datetime.now()
                    logger.info(f"Starting parallel location updates for user {user_id}...")
                    auto_schedule_logger.info(f"[PHASE 5: LOCATION CLASSIFICATION START] User: {user_id} | Timestamp: {location_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    auto_schedule_logger.info(f"[PHASE 5: LOCATION] Max Workers: {self.max_location_workers} | Batch Size: {self.location_batch_size}")
                    location_success = self._run_task(
                        lambda: self._run_location_batch_update_parallel(user_id), 
                        f'location_batch_{user_id}'
                    )
                    location_end = datetime.now()
                    location_duration = (location_end - location_start).total_seconds()
                    if location_success:
                        auto_schedule_logger.info(f"[PHASE 5: LOCATION CLASSIFICATION END] User: {user_id} | Timestamp: {location_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {location_duration:.2f}s | Max Workers: {self.max_location_workers} | Status: SUCCESS")
                    else:
                        auto_schedule_logger.error(f"[PHASE 5: LOCATION CLASSIFICATION END] User: {user_id} | Timestamp: {location_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {location_duration:.2f}s | Max Workers: {self.max_location_workers} | Status: FAILED")
                    
                    if location_success:
                        # 6. Issue Detection (clustering-based)
                        issue_start = datetime.now()
                        logger.info(f"Starting issue detection for user {user_id}...")
                        auto_schedule_logger.info(f"[PHASE 6: ISSUE DETECTION START] User: {user_id} | Timestamp: {issue_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                        issue_success = self._run_task(
                            lambda: self._run_issue_detection(user_id, recalculate_existing=use_existing_data), 
                            f'issue_detection_{user_id}'
                        )
                        issue_end = datetime.now()
                        issue_duration = (issue_end - issue_start).total_seconds()
                        if issue_success:
                            auto_schedule_logger.info(f"[PHASE 6: ISSUE DETECTION END] User: {user_id} | Timestamp: {issue_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {issue_duration:.2f}s | Status: SUCCESS")
                            
                            # 7. Aggregation (Week 5)
                            agg_start = datetime.now()
                            logger.info(f"Starting aggregation for user {user_id}...")
                            auto_schedule_logger.info(f"[PHASE 7: AGGREGATION START] User: {user_id} | Timestamp: {agg_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                            agg_success = self._run_task(
                                lambda: self._run_aggregation(user_id),
                                f'aggregation_{user_id}'
                            )
                            agg_end = datetime.now()
                            agg_duration = (agg_end - agg_start).total_seconds()
                            
                            if agg_success:
                                auto_schedule_logger.info(f"[PHASE 7: AGGREGATION END] User: {user_id} | Timestamp: {agg_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {agg_duration:.2f}s | Status: SUCCESS")
                            else:
                                auto_schedule_logger.error(f"[PHASE 7: AGGREGATION END] User: {user_id} | Timestamp: {agg_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {agg_duration:.2f}s | Status: FAILED")
                                
                        else:
                            auto_schedule_logger.error(f"[PHASE 6: ISSUE DETECTION END] User: {user_id} | Timestamp: {issue_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {issue_duration:.2f}s | Status: FAILED")
                            agg_duration = 0.0 # Didn't run
                    else:
                        issue_success = False
                        issue_duration = 0.0
                        agg_duration = 0.0
                        issue_end = location_end
                    
                    logger.info(f"Parallel cycle completed for user {user_id}: Collection ✅, Deduplication ✅, Sentiment ✅, Location ✅, Issue Detection ✅, Aggregation ✅")
                    total_duration = (datetime.now() - collection_start).total_seconds()
                    auto_schedule_logger.info(f"[CYCLE SUMMARY] User: {user_id} | Total Duration: {total_duration:.2f}s | Collection: {collection_duration:.2f}s | Loading: {load_duration:.2f}s | Dedup: {dedup_duration:.2f}s | Sentiment: {sentiment_duration:.2f}s | Location: {location_duration:.2f}s | Issue Detection: {issue_duration:.2f}s | Aggregation: {agg_duration:.2f}s")
            else:
                logger.warning(f"Deduplication failed for user {user_id}, skipping analysis steps")
                auto_schedule_logger.warning(f"[CYCLE ABORTED] User: {user_id} | Reason: Deduplication failed")

        except Exception as e:
            logger.error(f"Unexpected error during run_single_cycle_parallel for user {user_id}: {e}", exc_info=True)
            auto_schedule_logger.error(f"[CYCLE EXCEPTION] User: {user_id} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Error: {str(e)}")
        finally:
            # Ensure busy status is reset
            pass

    # --- Modified: Old scheduled run - Adapt or remove later --- 
    def _init_location_classifier(self):
        """Initialize the enhanced location classifier with country patterns."""
        try:
            # Simplified country definitions for faster processing
            country_patterns = {
                'Nigeria': {
                    'keywords': ['nigeria', 'nigerian', 'naija', 'lagos', 'abuja', 'kano', 'ibadan', 
                               'port harcourt', 'tinubu', 'buhari', 'apc', 'pdp', 'nigerian government'],
                    'sources': ['punch', 'guardian nigeria', 'vanguard', 'thisday', 'daily trust',
                              'leadership', 'tribune', 'premium times', 'sahara reporters'],
                    'domains': ['punchng.com', 'guardian.ng', 'vanguardngr.com', 'thisdaylive.com']
                },
                'US': {
                    'keywords': ['america', 'american', 'washington', 'new york', 'california', 'texas', 'usa', 
                               'united states', 'white house', 'congress', 'nfl', 'nba'],
                    'sources': ['cnn', 'fox news', 'nbc', 'abc', 'cbs', 'usa today', 'new york times',
                              'washington post', 'wall street journal'],
                    'domains': ['cnn.com', 'foxnews.com', 'nbcnews.com', 'usatoday.com', 'nytimes.com']
                },
                'UK': {
                    'keywords': ['britain', 'british', 'london', 'manchester', 'liverpool', 'uk', 'united kingdom',
                               'england', 'scotland', 'wales', 'bbc', 'nhs', 'parliament'],
                    'sources': ['bbc', 'guardian', 'telegraph', 'independent', 'daily mail', 'mirror'],
                    'domains': ['bbc.co.uk', 'theguardian.com', 'telegraph.co.uk', 'dailymail.co.uk']
                },
                'Qatar': {
                    'keywords': ['qatar', 'doha', 'qatari', 'al thani', 'emir', 'lusail', 'al wakrah',
                               'gulf', 'middle east', 'arabian'],
                    'sources': ['al jazeera', 'gulf times', 'peninsula', 'qatar tribune'],
                    'domains': ['aljazeera.com', 'gulf-times.com', 'thepeninsulaqatar.com']
                },
                'India': {
                    'keywords': ['india', 'indian', 'bharat', 'hindustan', 'mumbai', 'delhi', 'bangalore',
                               'hyderabad', 'chennai', 'kolkata', 'bollywood', 'cricket', 'modi'],
                    'sources': ['times of india', 'the hindu', 'hindustan times', 'indian express', 'ndtv'],
                    'domains': ['timesofindia.indiatimes.com', 'thehindu.com', 'hindustantimes.com']
                }
            }
            
            # Create a simple location classifier object
            class SimpleLocationClassifier:
                def __init__(self, patterns):
                    self.country_patterns = patterns
                
                def classify(self, text, platform=None, source=None, user_location=None, user_name=None, user_handle=None):
                    """Classify location based on text and metadata."""
                    if not text or pd.isna(text):
                        return None, None
                    
                    text = str(text).lower()
                    platform = str(platform or '').lower()
                    source = str(source or '').lower()
                    user_location = str(user_location or '').lower()
                    user_name = str(user_name or '').lower()
                    user_handle = str(user_handle or '').lower()
                    
                    # Initialize country scores
                    country_scores = {country: 0.0 for country in self.country_patterns.keys()}
                    
                    # 1. Source/Platform Analysis (highest weight)
                    for country, patterns in self.country_patterns.items():
                        # Check source names
                        for source_name in patterns['sources']:
                            if source_name in source or source_name in platform:
                                country_scores[country] += 5.0
                        
                        # Check domains
                        for domain_name in patterns['domains']:
                            if domain_name in user_location:
                                country_scores[country] += 5.0
                    
                    # 2. Text Content Analysis
                    for country, patterns in self.country_patterns.items():
                        for keyword in patterns['keywords']:
                            if keyword in text:
                                country_scores[country] += 1.0
                    
                    # 3. User Location Analysis
                    if user_location:
                        for country, patterns in self.country_patterns.items():
                            if country.lower() in user_location:
                                country_scores[country] += 3.0
                            for keyword in patterns['keywords']:
                                if keyword in user_location:
                                    country_scores[country] += 2.0
                    
                    # 4. Username/Handle Analysis
                    for name in [user_name, user_handle]:
                        if name:
                            for country, patterns in self.country_patterns.items():
                                for keyword in patterns['keywords'][:5]:  # Use first 5 keywords
                                    if keyword in name:
                                        country_scores[country] += 2.0
                    
                    # Determine the country with the highest score
                    max_score = max(country_scores.values())
                    if max_score >= 2.0:  # Minimum threshold
                        # Get the country with the highest score
                        for country, score in country_scores.items():
                            if score == max_score:
                                confidence = min(1.0, score / 10.0)  # Normalize confidence
                                return country.lower(), confidence
                    
                    return None, None
            
            return SimpleLocationClassifier(country_patterns)
            
        except Exception as e:
            logger.error(f"Failed to initialize location classifier: {e}")
            return None

    def update_location_classifications(self, user_id: str, batch_size: int = None) -> Dict[str, Any]:
        """
        Update location classifications for existing records in the database.
        This is similar to the batch location classification script functionality.
        
        Args:
            user_id (str): The user ID to process records for
            batch_size (int): Number of records to process in each batch. If None, uses config value.
            
        Returns:
            Dict containing update statistics
        """
        # Get batch_size from config if not provided
        if batch_size is None:
            try:
                config_manager = ConfigManager()
                batch_size = config_manager.get_int("processing.parallel.location_batch_size", 300)
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for batch_size, using default 300: {e}")
                batch_size = 300
        if not self.location_classifier:
            logger.error("Location classifier not initialized. Cannot update classifications.")
            return {"error": "Location classifier not initialized"}
        
        logger.info(f"Starting location classification update for user {user_id}...")
        
        try:
            with self.db_factory() as db:
                # Get total count of records for this user
                total_records = db.query(models.SentimentData).filter(
                    models.SentimentData.user_id == user_id
                ).count()
                
                if total_records == 0:
                    logger.warning(f"No records found for user {user_id}")
                    return {"message": "No records found for user", "total_records": 0}
                
                logger.info(f"Found {total_records} records to process for user {user_id}")
                
                # Calculate number of batches
                num_batches = (total_records + batch_size - 1) // batch_size
                logger.info(f"Processing in {num_batches} batches of {batch_size}")
                
                overall_stats = {
                    'user_id': user_id,
                    'total_records': total_records,
                    'total_updated': 0,
                    'total_unchanged': 0,
                    'country_changes': {},
                    'confidence_scores': [],
                    'batches_processed': 0
                }
                
                for batch_num in range(num_batches):
                    offset = batch_num * batch_size
                    
                    logger.info(f"Processing batch {batch_num + 1}/{num_batches} (offset: {offset})")
                    
                    # Get batch of records
                    records = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id
                    ).offset(offset).limit(batch_size).all()
                    
                    batch_stats = {
                        'processed': 0,
                        'updated': 0,
                        'unchanged': 0,
                        'country_changes': {},
                        'confidence_scores': []
                    }
                    
                    for record in records:
                        try:
                            # Get existing data for classification
                            text = record.text or ''
                            platform = record.platform or ''
                            source = record.source or ''
                            user_location = record.user_location or ''
                            user_name = record.user_name or ''
                            user_handle = record.user_handle or ''
                            
                            # Detect new country classification
                            new_country, confidence = self.location_classifier.classify(
                                text, platform, source, user_location, user_name, user_handle
                            )
                            
                            # Track confidence
                            batch_stats['confidence_scores'].append(confidence or 0.0)
                            
                            # Check if country classification changed
                            old_country = record.country.lower() if record.country else 'unknown'
                            if new_country and new_country != old_country:
                                record.country = new_country.title()
                                batch_stats['updated'] += 1
                                
                                # Track changes
                                change_key = f"{old_country} -> {new_country}"
                                batch_stats['country_changes'][change_key] = batch_stats['country_changes'].get(change_key, 0) + 1
                            else:
                                batch_stats['unchanged'] += 1
                            
                            batch_stats['processed'] += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing record {record.entry_id}: {e}")
                            continue
                    
                    # Update overall stats
                    overall_stats['total_updated'] += batch_stats['updated']
                    overall_stats['total_unchanged'] += batch_stats['unchanged']
                    overall_stats['all_confidence_scores'] = overall_stats.get('all_confidence_scores', []) + batch_stats['confidence_scores']
                    overall_stats['batches_processed'] += 1
                    
                    # Merge country changes
                    for change, count in batch_stats['country_changes'].items():
                        overall_stats['country_changes'][change] = overall_stats['country_changes'].get(change, 0) + count
                    
                    # Commit after each batch
                    db.commit()
                    logger.info(f"Batch {batch_num + 1} completed: {batch_stats['updated']} updated, {batch_stats['unchanged']} unchanged")
                    
                    # Show some examples of changes
                    if batch_stats['country_changes']:
                        logger.info(f"Batch {batch_num + 1} changes: {dict(list(batch_stats['country_changes'].items())[:3])}")
                
                # Calculate final stats
                overall_stats['total_unchanged'] = total_records - overall_stats['total_updated']
                if overall_stats['all_confidence_scores']:
                    overall_stats['average_confidence'] = sum(overall_stats['all_confidence_scores']) / len(overall_stats['all_confidence_scores'])
                    overall_stats['high_confidence_count'] = sum(1 for score in overall_stats['all_confidence_scores'] if score >= 0.7)
                    overall_stats['medium_confidence_count'] = sum(1 for score in overall_stats['all_confidence_scores'] if 0.4 <= score < 0.7)
                    overall_stats['low_confidence_count'] = sum(1 for score in overall_stats['all_confidence_scores'] if score < 0.4)
                else:
                    overall_stats['average_confidence'] = 0.0
                    overall_stats['high_confidence_count'] = 0
                    overall_stats['medium_confidence_count'] = 0
                    overall_stats['low_confidence_count'] = 0
                
                logger.info("Location classification update completed successfully!")
                return overall_stats
                
        except Exception as e:
            logger.error(f"Error during location classification update: {e}", exc_info=True)
            return {'error': str(e)}
    def _run_aggregation(self, user_id: str) -> Dict[str, Any]:
        """
        Run sentiment aggregation pipeline (Week 5).
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with aggregation stats
        """
        logger.info(f"Running aggregation pipeline for user {user_id}...")
        
        if not self.data_processor or not self.data_processor.aggregation_service:
            logger.warning("Aggregation service not available, skipping aggregation")
            return {'status': 'skipped', 'reason': 'service_unavailable'}
        
        try:
            # Run aggregation for 24h window
            results_24h = self.data_processor.run_aggregation_pipeline(
                time_window='24h',
                include_trends=True,
                include_normalization=True
            )
            
            # Run aggregation for 1h window (for rapid updates)
            results_1h = self.data_processor.run_aggregation_pipeline(
                time_window='1h',
                include_trends=False, # Trends need more data points
                include_normalization=False
            )
            
            # Combine stats
            stats = {
                '24h_topics': len(results_24h.get('aggregations', {})),
                '1h_topics': len(results_1h.get('aggregations', {})),
                'trends_calculated': len(results_24h.get('trends', {})),
                'status': 'success'
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error running aggregation pipeline: {e}", exc_info=True)
            return {'status': 'failed', 'error': str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status and task information."""
        return {
            "status": self.status,
            "task_status": self.task_status,
            "last_run_times": self.last_run_times,
            "config_summary": {
                "collection_interval": self.config.get("collection_interval_minutes"),
                "processing_interval": self.config.get("processing_interval_minutes"),
                "data_retention_days": self.config.get("data_retention_days"),
                "sources_enabled": self.config.get("sources", {}),
                "adaptive_scheduling": self.config.get("adaptive_scheduling", False),
                "auto_optimization": self.config.get("auto_optimization", False)
            },
            "data_history_summary": {
                "sentiment_trends_count": len(self.data_history.get("sentiment_trends", [])),
                "system_health_count": len(self.data_history.get("system_health", [])),
                "data_quality_metrics_count": len(self.data_history.get("data_quality_metrics", []))
            },
            "timestamp": datetime.now().isoformat()
        }

    def _push_raw_data_to_db(self, user_id: str):
        """Push raw collected data to database without processing"""
        try:
            logger.info(f"🔍 DEBUG: Starting _push_raw_data_to_db for user {user_id}")
            
            raw_data_path = self.path_manager.data_raw
            logger.info(f"🔍 DEBUG: Raw data path: {raw_data_path}")
            logger.info(f"🔍 DEBUG: Path exists: {raw_data_path.exists()}")
            
            if not raw_data_path.exists():
                logger.warning("No raw data directory found")
                return True
            
            # Get all raw CSV files
            raw_files = list(raw_data_path.glob('*.csv'))
            logger.info(f"🔍 DEBUG: Found {len(raw_files)} CSV files: {[f.name for f in raw_files]}")
            
            if not raw_files:
                logger.info("No raw data files found to push to DB")
                return True
            
            total_records = 0
            all_records = []
            
            # First, collect all records from all files
            for file_path in raw_files:
                try:
                    logger.info(f"Reading raw file: {file_path.name}")
                    
                    # Read CSV without any processing
                    df = pd.read_csv(file_path, on_bad_lines='warn')
                    logger.info(f"Read {len(df)} rows from {file_path.name}")
                    
                    # Convert to records and add user_id
                    for _, row in df.iterrows():
                        record_data = row.to_dict()
                        record_data['user_id'] = user_id
                        
                        # Clean up pandas NaN values - convert to None
                        for key, value in record_data.items():
                            if pd.isna(value):
                                record_data[key] = None
                        
                        # Ensure required fields exist
                        if 'text' not in record_data or not record_data.get('text'):
                            record_data['text'] = record_data.get('content', record_data.get('description', ''))
                        
                        # Clean numeric fields - convert any text values to None for numeric fields
                        numeric_fields = ['score', 'sentiment_score', 'location_confidence', 'issue_confidence',
                                         'alert_id', 'children', 'direct_reach', 'cumulative_reach', 'domain_reach',
                                         'retweets', 'likes', 'comments']
                        for field in numeric_fields:
                            if field in record_data:
                                if field in ['score', 'sentiment_score', 'location_confidence', 'issue_confidence']:
                                    record_data[field] = safe_float(record_data[field])
                                else:
                                    record_data[field] = safe_int(record_data[field])
                        
                        all_records.append(record_data)
                    
                    total_records += len(df)
                    
                except Exception as e:
                    logger.error(f"Error reading file {file_path.name}: {e}")
                    continue
            
            # Store all records for deduplication later
            self._temp_raw_records = all_records
            
            logger.info(f"🔍 DEBUG: Stored {len(all_records)} records in _temp_raw_records")
            logger.info(f"Raw data collection completed: {total_records} total records collected from {len(raw_files)} files")
            return True
            
        except Exception as e:
            logger.error(f"Error during raw data collection: {e}", exc_info=True)
            return False

    def _run_deduplication(self, user_id: str):
        """Run deduplication on collected raw data before processing"""
        try:
            logger.info(f"🔍 DEBUG: Starting _run_deduplication for user {user_id}")
            logger.info(f"🔍 DEBUG: Has _temp_raw_records: {hasattr(self, '_temp_raw_records')}")
            if hasattr(self, '_temp_raw_records'):
                logger.info(f"🔍 DEBUG: _temp_raw_records length: {len(self._temp_raw_records) if self._temp_raw_records else 'None'}")
            
            if not hasattr(self, '_temp_raw_records') or not self._temp_raw_records:
                logger.info("No raw records to deduplicate")
                # Set empty stats for logging
                self._dedup_stats = {'total': 0, 'unique': 0, 'duplicates': 0}
                return True
            
            logger.info(f"Starting deduplication for user {user_id} with {len(self._temp_raw_records)} records")
            
            with self.db_factory() as db:
                # Run deduplication
                dedup_results = self.deduplication_service.deduplicate_new_data(
                    self._temp_raw_records, db, user_id
                )
                
                # Store deduplication stats for logging
                self._dedup_stats = dedup_results.get('stats', {})
                
                # Log deduplication summary
                summary = self.deduplication_service.get_deduplication_summary(dedup_results)
                logger.info(f"Deduplication results:\n{summary}")
                
                # Store unique records for database insertion
                self._unique_records = dedup_results['unique_records']
                
                # Insert unique records into database using bulk insert
                if self._unique_records:
                    logger.info(f"Inserting {len(self._unique_records)} unique records into database")
                    
                    # Prepare data for bulk insert
                    bulk_data = []
                    current_timestamp = datetime.utcnow()
                    
                    for record_data in self._unique_records:
                        try:
                            # Handle JSON fields properly
                            issue_keywords_val = record_data.get('issue_keywords')
                            if issue_keywords_val and not isinstance(issue_keywords_val, (list, dict)):
                                try:
                                    issue_keywords_val = json.loads(issue_keywords_val) if issue_keywords_val else None
                                except:
                                    issue_keywords_val = None
                            
                            # Map CSV columns to database columns
                            # Note: CSV has 'location' but DB has 'user_location'
                            # CSV has 'username' but DB has 'user_name'
                            user_location_val = record_data.get('user_location') or record_data.get('location', '')
                            # Validate and clean location data
                            user_location_val = self._validate_and_clean_location(user_location_val)
                            
                            user_name_val = record_data.get('user_name') or record_data.get('username', '')
                            user_display_val = record_data.get('user_display_name', '')
                            if user_display_val and not user_name_val:
                                user_name_val = user_display_val
                            
                            # Build the mapping dictionary
                            db_mapping = {
                                'run_timestamp': current_timestamp,
                                'user_id': user_id,
                                'platform': record_data.get('platform', ''),
                                'text': record_data.get('text', ''),
                                'content': record_data.get('content', ''),
                                'title': record_data.get('title', ''),
                                'description': record_data.get('description', ''),
                                'url': record_data.get('url', ''),
                                'published_date': self._parse_date_string(record_data.get('published_date')),
                                'source': record_data.get('source', ''),
                                'source_url': record_data.get('source_url', ''),
                                'query': record_data.get('query', ''),
                                'language': record_data.get('language', ''),
                                'date': self._parse_date_string(record_data.get('date')),
                                'file_source': record_data.get('file_source', ''),
                                'original_id': record_data.get('id', ''),
                                'alert_id': safe_int(record_data.get('alert_id')),
                                'published_at': self._parse_date_string(record_data.get('published_at')),
                                'source_type': record_data.get('source_type', ''),
                                'country': record_data.get('country', ''),
                                'favorite': record_data.get('favorite'),
                                'tone': record_data.get('tone', ''),
                                'source_name': record_data.get('source_name', ''),
                                'parent_url': record_data.get('parent_url', ''),
                                'parent_id': record_data.get('parent_id', ''),
                                'children': safe_int(record_data.get('children')),
                                'direct_reach': safe_int(record_data.get('direct_reach')),
                                'cumulative_reach': safe_int(record_data.get('cumulative_reach')),
                                'domain_reach': safe_int(record_data.get('domain_reach')),
                                'tags': record_data.get('tags', ''),
                                'score': safe_float(record_data.get('score')),
                                'alert_name': record_data.get('alert_name', ''),
                                'type': record_data.get('type', ''),
                                'post_id': record_data.get('post_id', ''),
                                'retweets': safe_int(record_data.get('retweets')),
                                'likes': safe_int(record_data.get('likes')),
                                'user_location': user_location_val,
                                'comments': safe_int(record_data.get('comments')),
                                'user_name': user_name_val,
                                'user_handle': record_data.get('user_handle', ''),
                                'user_avatar': record_data.get('user_avatar', ''),
                                'sentiment_label': record_data.get('sentiment_label'),
                                'sentiment_score': safe_float(record_data.get('sentiment_score')),
                                'sentiment_justification': record_data.get('sentiment_justification'),
                                'location_label': record_data.get('location_label'),
                                'location_confidence': safe_float(record_data.get('location_confidence')),
                                'issue_label': record_data.get('issue_label'),
                                'issue_slug': record_data.get('issue_slug'),
                                'issue_confidence': safe_float(record_data.get('issue_confidence')),
                                'issue_keywords': issue_keywords_val,
                                'ministry_hint': record_data.get('ministry_hint')
                            }
                            
                            bulk_data.append(db_mapping)
                            
                        except Exception as e:
                            logger.error(f"Error preparing record for bulk insert: {e}")
                            logger.error(f"Record URL: {record_data.get('url', 'N/A')}")
                            logger.error(f"Record platform: {record_data.get('platform', 'N/A')}")
                            continue
                    
                    # Use bulk_insert_mappings for better performance and explicit column mapping
                    if bulk_data:
                        db.bulk_insert_mappings(models.SentimentData, bulk_data)
                        db.commit()
                        logger.info(f"Successfully inserted {len(bulk_data)} unique records into database")
                else:
                    logger.info("No unique records to insert after deduplication")
                
                # Clean up raw CSV files after successful processing
                raw_data_path = self.path_manager.data_raw
                if raw_data_path.exists():
                    raw_files = list(raw_data_path.glob('*.csv'))
                    if raw_files:
                        logger.info(f"Cleaning up {len(raw_files)} raw CSV files after successful processing")
                        for file_path in raw_files:
                            try:
                                file_path.unlink()
                                logger.debug(f"Deleted raw file: {file_path.name}")
                            except Exception as e:
                                logger.warning(f"Failed to delete raw file {file_path.name}: {e}")
                        logger.info("Raw file cleanup completed")
                
                # Clean up temporary data
                if hasattr(self, '_temp_raw_records'):
                    delattr(self, '_temp_raw_records')
                
                # Store deduplication results for logging
                self._last_dedup_results = dedup_results
                
                return True
                
        except Exception as e:
            logger.error(f"Error during deduplication: {e}", exc_info=True)
            return False

    def _run_sentiment_batch_update_parallel(self, user_id: str, use_existing_data: bool = False, skip_collection_only: bool = False):
        """
        Run sentiment analysis in parallel batches for newly inserted unique records or existing unanalyzed records.
        
        Args:
            user_id: User ID to process records for
            use_existing_data: If True, uses existing embeddings and sentiment from database, skipping OpenAI calls when both exist
            skip_collection_only: If True, processes ALL existing records for the user (calls OpenAI for missing embeddings/sentiment)
        """
        try:
            logger.info(f"Starting parallel batch sentiment analysis for user {user_id} (use_existing_data={use_existing_data}, skip_collection_only={skip_collection_only})")
            
            # Convert string user_id to UUID if needed
            from uuid import UUID
            if isinstance(user_id, str):
                user_id_uuid = UUID(user_id)
            else:
                user_id_uuid = user_id
            
            # Get the database records that need sentiment analysis
            with self.db_factory() as db:
                # If we have unique records from deduplication, filter to just those
                if hasattr(self, '_unique_records') and self._unique_records and not use_existing_data and not skip_collection_only:
                    logger.info(f"Using unique records from deduplication for sentiment analysis")
                    # Query for the records that were just inserted (they won't have sentiment analysis yet)
                    unique_texts = []
                    for record in self._unique_records:
                        text_content = record.get('text') or record.get('content') or record.get('title') or record.get('description')
                        if text_content:
                            unique_texts.append(text_content)
                    
                    if not unique_texts:
                        logger.info("No text content found in unique records, skipping sentiment analysis")
                        return True
                    
                    # Query database for the records that were just inserted
                    records_to_update = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id_uuid,
                        models.SentimentData.sentiment_label.is_(None),  # Records without sentiment analysis
                        models.SentimentData.text.in_(unique_texts)  # Only the newly inserted records
                    ).all()
                elif skip_collection_only:
                    # Process ALL existing records for the user (will call OpenAI for missing embeddings/sentiment)
                    logger.info(f"Skip collection mode: Processing ALL existing records for user {user_id} (will call OpenAI for missing embeddings/sentiment)")
                    max_records = self.config_manager.get_int("processing.limits.max_records_per_batch", 5000)
                    
                    # Query for ALL records for this user (regardless of whether they have embeddings/sentiment)
                    records_to_update = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id_uuid
                    ).limit(max_records).all()
                    
                    logger.info(f"Found {len(records_to_update)} total records for user {user_id} (will process normally with OpenAI calls)")
                elif use_existing_data:
                    # Process ONLY records that have BOTH embedding and sentiment (skip OpenAI entirely)
                    logger.info(f"Processing records with existing embeddings AND sentiment for user {user_id}")
                    max_records = self.config_manager.get_int("processing.limits.max_records_per_batch", 5000)
                    
                    # Debug: Check total records for this user
                    total_records = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id_uuid
                    ).count()
                    logger.info(f"DEBUG: Total records for user {user_id}: {total_records}")
                    
                    # Debug: Check records with sentiment
                    records_with_sentiment = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id_uuid,
                        models.SentimentData.sentiment_label.isnot(None)
                    ).count()
                    logger.info(f"DEBUG: Records with sentiment_label: {records_with_sentiment}")
                    
                    # Debug: Check records with embeddings
                    records_with_embeddings = db.query(models.SentimentEmbedding).join(
                        models.SentimentData,
                        models.SentimentEmbedding.entry_id == models.SentimentData.entry_id
                    ).filter(
                        models.SentimentData.user_id == user_id_uuid,
                        models.SentimentEmbedding.embedding.isnot(None)
                    ).count()
                    logger.info(f"DEBUG: Records with embeddings: {records_with_embeddings}")
                    
                    # Debug: Check a sample record to see user_id format
                    sample = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id_uuid
                    ).first()
                    if sample:
                        logger.info(f"DEBUG: Sample record user_id type: {type(sample.user_id)}, value: {sample.user_id}")
                    else:
                        logger.warning(f"DEBUG: No records found for user_id_uuid: {user_id_uuid} (type: {type(user_id_uuid)})")
                        
                        # Check if records exist with NULL user_id or different user_ids
                        total_all_records = db.query(models.SentimentData).count()
                        records_with_null_user = db.query(models.SentimentData).filter(
                            models.SentimentData.user_id.is_(None)
                        ).count()
                        
                        # Get distinct user_ids
                        distinct_user_ids = db.query(models.SentimentData.user_id).distinct().limit(10).all()
                        logger.info(f"DEBUG: Total records in DB: {total_all_records}")
                        logger.info(f"DEBUG: Records with NULL user_id: {records_with_null_user}")
                        logger.info(f"DEBUG: Sample user_ids in DB: {[str(uid[0]) if uid[0] else 'NULL' for uid in distinct_user_ids]}")
                        
                        # Try querying without user_id filter to see if records exist
                        if records_with_null_user > 0:
                            logger.warning(f"DEBUG: Found {records_with_null_user} records with NULL user_id - these might be the records we need!")
                            # Try querying records with NULL user_id that have both embedding and sentiment
                            records_null_user = db.query(models.SentimentData).join(
                                models.SentimentEmbedding,
                                models.SentimentData.entry_id == models.SentimentEmbedding.entry_id
                            ).filter(
                                models.SentimentData.user_id.is_(None),
                                models.SentimentData.sentiment_label.isnot(None),
                                models.SentimentEmbedding.embedding.isnot(None)
                            ).limit(10).all()
                            logger.info(f"DEBUG: Records with NULL user_id + embedding + sentiment: {len(records_null_user)}")
                    
                    # Query for records that have both embedding and sentiment
                    records_to_update = db.query(models.SentimentData).join(
                        models.SentimentEmbedding,
                        models.SentimentData.entry_id == models.SentimentEmbedding.entry_id
                    ).filter(
                        models.SentimentData.user_id == user_id_uuid,
                        models.SentimentData.sentiment_label.isnot(None),
                        models.SentimentEmbedding.embedding.isnot(None)
                    ).limit(max_records).all()
                    
                    logger.info(f"Found {len(records_to_update)} records with both embedding and sentiment (will skip OpenAI calls)")
                else:
                    # No deduplication records, query for all unanalyzed records for this user
                    logger.info(f"No deduplication records, querying database for all unanalyzed records")
                    max_records = self.config_manager.get_int("processing.limits.max_records_per_batch", 500)
                    records_to_update = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id,
                        models.SentimentData.sentiment_label.is_(None)  # Records without sentiment analysis
                    ).limit(max_records).all()  # Process up to max_records_per_batch records at a time
                
                if not records_to_update:
                    logger.info(f"No records found for sentiment analysis for user {user_id}")
                    return True
                
                logger.info(f"Found {len(records_to_update)} records for parallel sentiment analysis")
                
                # Process in parallel batches
                batch_size = self.sentiment_batch_size
                processed_count = 0
                
                # Split records into batches for parallel processing
                batches = []
                for i in range(0, len(records_to_update), batch_size):
                    batch = records_to_update[i:i + batch_size]
                    batches.append(batch)
                
                actual_sentiment_workers = min(self.max_sentiment_workers, len(batches))
                logger.info(f"Processing {len(batches)} sentiment batches in parallel with {self.max_sentiment_workers} workers (actual: {actual_sentiment_workers})")
                mode_str = "Skip Collection" if skip_collection_only else ("Use Existing" if use_existing_data else "Normal")
                auto_schedule_logger.info(f"[PHASE 4: SENTIMENT] Batches: {len(batches)} | Max Workers: {self.max_sentiment_workers} | Actual Workers: {actual_sentiment_workers} | Records: {len(records_to_update)} | Mode: {mode_str}")
                
                # Process batches in parallel
                batch_results = self._process_sentiment_batches_parallel(batches, user_id, use_existing_data=use_existing_data, skip_collection_only=skip_collection_only)
                
                # Count successful processing
                processed_count = sum(batch_results.values())
                
                logger.info(f"Parallel sentiment analysis completed: {processed_count}/{len(records_to_update)} records processed")
                
                return processed_count > 0
                
        except Exception as e:
            logger.error(f"Error during parallel sentiment batch update: {e}", exc_info=True)
            return False
    
    def _process_sentiment_batches_parallel(self, batches: List[List], user_id: str, use_existing_data: bool = False, skip_collection_only: bool = False) -> Dict[int, int]:
        """
        Process sentiment analysis batches in parallel using ThreadPoolExecutor.
        
        Args:
            batches: List of record batches to process
            user_id: User ID
            use_existing_data: If True, uses existing embeddings and sentiment from database, skipping OpenAI calls when both exist
            skip_collection_only: If True, processes ALL records normally (with OpenAI calls for missing embeddings/sentiment)
        """
        results = {}
        
        def process_single_batch(batch_data: tuple) -> int:
            """Process a single batch of records and return count of processed records."""
            batch_idx, batch = batch_data
            processed_in_batch = 0
            skipped_with_existing = 0
            
            try:
                logger.info(f"Processing sentiment batch {batch_idx + 1}/{len(batches)} ({len(batch)} records)")
                
                # Create a new database session for this thread
                with self.db_factory() as db:
                    # Prepare batch data
                    records_list = []
                    texts_list = []
                    source_types_list = []
                    records_needing_analysis = []  # Records that need OpenAI calls
                    records_with_existing_data = []  # Records with existing embeddings/sentiment
                    
                    for record in batch:
                        # CRITICAL FIX: Merge record into this thread's session
                        record = db.merge(record)
                        records_list.append(record)
                        
                        text_content = record.text or record.content or record.title or record.description
                        if not text_content:
                            continue
                        
                        # Check if we should use existing data (skip_collection_only processes normally)
                        if use_existing_data and not skip_collection_only:
                            # Check for existing embedding and sentiment
                            existing_embedding = db.query(models.SentimentEmbedding).filter(
                                models.SentimentEmbedding.entry_id == record.entry_id
                            ).first()
                            
                            has_sentiment = record.sentiment_label is not None
                            has_embedding = existing_embedding is not None and existing_embedding.embedding is not None
                            has_emotion = record.emotion_label is not None
                            has_topics = False  # Check if topics exist in mention_topics table
                            try:
                                from api.models import MentionTopic
                                topic_count = db.query(MentionTopic).filter(
                                    MentionTopic.mention_id == record.entry_id
                                ).count()
                                has_topics = topic_count > 0
                            except:
                                pass
                            
                            # When use_existing_data=True, we only process records with BOTH embedding and sentiment
                            # Skip records that already have everything (emotion + topics)
                            if has_sentiment and has_embedding and has_emotion and has_topics:
                                # All fields exist, skip processing entirely
                                records_with_existing_data.append((record, existing_embedding))
                                skipped_with_existing += 1
                                continue
                            
                            # Has embedding and sentiment, but missing emotion/topics - process to fill those
                            # We'll use existing embedding/sentiment and skip OpenAI
                            if has_sentiment and has_embedding:
                                # Add to list for processing without OpenAI
                                records_needing_analysis.append((record, existing_embedding))
                                continue
                        
                        # For skip_collection_only mode: Check if embedding is zero vector and treat as missing
                        if skip_collection_only:
                            existing_embedding = db.query(models.SentimentEmbedding).filter(
                                models.SentimentEmbedding.entry_id == record.entry_id
                            ).first()
                            
                            # Check if embedding exists and is valid (not zero vector)
                            has_valid_embedding = False
                            if existing_embedding and existing_embedding.embedding is not None:
                                try:
                                    import numpy as np
                                    embedding_data = None
                                    if isinstance(existing_embedding.embedding, str):
                                        embedding_data = json.loads(existing_embedding.embedding)
                                    else:
                                        embedding_data = existing_embedding.embedding
                                    
                                    if embedding_data and len(embedding_data) == 1536:
                                        embedding_array = np.array(embedding_data, dtype=np.float64)
                                        embedding_norm = np.linalg.norm(embedding_array)
                                        # Consider zero vector as invalid (needs regeneration)
                                        has_valid_embedding = embedding_norm > 1e-10
                                        if not has_valid_embedding:
                                            logger.debug(f"Record {record.entry_id} has zero vector embedding - will regenerate via OpenAI")
                                except Exception as e:
                                    logger.debug(f"Error checking embedding for record {record.entry_id}: {e}")
                            
                            # If record has valid embedding AND sentiment, we can skip OpenAI for sentiment/embedding
                            # but still need to process emotion/topics if missing
                            has_sentiment = record.sentiment_label is not None
                            has_emotion = record.emotion_label is not None
                            has_topics = False
                            try:
                                from api.models import MentionTopic
                                topic_count = db.query(MentionTopic).filter(
                                    MentionTopic.mention_id == record.entry_id
                                ).count()
                                has_topics = topic_count > 0
                            except:
                                pass
                            
                            # If has valid embedding AND sentiment AND emotion AND topics, skip entirely
                            if has_valid_embedding and has_sentiment and has_emotion and has_topics:
                                records_with_existing_data.append((record, existing_embedding))
                                skipped_with_existing += 1
                                continue
                            
                            # If has valid embedding AND sentiment but missing emotion/topics, process locally
                            if has_valid_embedding and has_sentiment and (not has_emotion or not has_topics):
                                records_needing_analysis.append((record, existing_embedding))
                                continue
                            
                            # Otherwise, process via OpenAI (missing embedding, zero vector, or missing sentiment)
                            # This includes records with zero vectors - they will be regenerated
                        
                        # If we reach here and use_existing_data=True (and not skip_collection_only), skip this record
                        # (it doesn't have both embedding and sentiment)
                        if use_existing_data and not skip_collection_only:
                            continue
                        
                        # Need to call OpenAI for this record (normal mode or skip_collection_only mode)
                        # This includes records with zero vectors in skip_collection_only mode
                        texts_list.append(text_content)
                        source_types_list.append(record.source_type)
                        records_needing_analysis.append(record)
                    
                    # Process records with existing data (all fields already populated - skip entirely)
                    for record, existing_embedding in records_with_existing_data:
                        try:
                            # Record already has all fields populated:
                            # - sentiment_label, sentiment_score, sentiment_justification
                            # - emotion_label, emotion_score, emotion_distribution
                            # - embedding (in sentiment_embeddings table)
                            # - topics (in mention_topics table)
                            # - influence_weight, confidence_weight
                            # No processing needed - just count as processed
                            processed_in_batch += 1
                        except Exception as e:
                            logger.warning(f"Error processing existing data for record {record.entry_id}: {e}")
                    
                    # Process records that have embedding/sentiment but need emotion/topics (no OpenAI)
                    # Only do this if use_existing_data=True AND skip_collection_only=False
                    if use_existing_data and not skip_collection_only and records_needing_analysis:
                        # These records have embedding and sentiment, but need emotion/topics filled in
                        # We'll use existing data and only call emotion detection (HuggingFace) and topic classification
                        logger.info(f"Processing {len(records_needing_analysis)} records with existing embedding/sentiment (filling emotion/topics without OpenAI)")
                        
                        for record_data in records_needing_analysis:
                            try:
                                # Handle tuple format (record, embedding) or just record
                                if isinstance(record_data, tuple):
                                    record, existing_embedding_obj = record_data
                                else:
                                    record = record_data
                                    existing_embedding_obj = db.query(models.SentimentEmbedding).filter(
                                        models.SentimentEmbedding.entry_id == record.entry_id
                                    ).first()
                                
                                text_content = record.text or record.content or record.title or record.description
                                if not text_content:
                                    continue
                                
                                # Get existing embedding
                                embedding_data = None
                                if existing_embedding_obj and existing_embedding_obj.embedding:
                                    if isinstance(existing_embedding_obj.embedding, str):
                                        embedding_data = json.loads(existing_embedding_obj.embedding)
                                    else:
                                        embedding_data = existing_embedding_obj.embedding
                                
                                # Validate embedding - check if it's a zero vector
                                if embedding_data:
                                    import numpy as np
                                    embedding_array = np.array(embedding_data, dtype=np.float64)
                                    embedding_norm = np.linalg.norm(embedding_array)
                                    if embedding_norm == 0 or embedding_norm < 1e-10:
                                        logger.debug(f"Record {record.entry_id} has zero vector embedding, skipping embedding-based topic classification")
                                        embedding_data = None  # Skip embedding-based classification for zero vectors
                                    elif len(embedding_data) != 1536:
                                        logger.debug(f"Record {record.entry_id} has invalid embedding length {len(embedding_data)}, expected 1536")
                                        embedding_data = None
                                
                                # Use existing sentiment (already in record - don't overwrite)
                                # sentiment_label, sentiment_score, sentiment_justification already set
                                
                                # Only fill in missing fields: emotion and topics
                                # Emotion detection uses HuggingFace (no OpenAI)
                                from src.processing.emotion_analyzer import EmotionAnalyzer
                                emotion_analyzer = EmotionAnalyzer()
                                emotion_result = emotion_analyzer.analyze_emotion(text_content)
                                
                                # Update emotion fields if missing
                                if not record.emotion_label:
                                    record.emotion_label = emotion_result.get('emotion_label', 'neutral')
                                if record.emotion_score is None:
                                    record.emotion_score = emotion_result.get('emotion_score', 0.5)
                                if not record.emotion_distribution and emotion_result.get('emotion_distribution'):
                                    record.emotion_distribution = json.dumps(emotion_result['emotion_distribution'])
                                
                                # Topic classification (uses embedding if available and valid, no OpenAI)
                                # If embedding is zero vector or invalid, topic classifier will use text-only mode
                                topic_result = self.data_processor.topic_classifier.classify(
                                    text_content, 
                                    embedding_data if embedding_data and len(embedding_data) == 1536 else None
                                )
                                
                                # Store topics in mention_topics table
                                if topic_result:
                                    try:
                                        self.data_processor._store_topics_in_database(
                                            db, 
                                            record.entry_id, 
                                            topic_result
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to store topics for record {record.entry_id}: {e}")
                                
                                # Set default weights if missing
                                if record.influence_weight is None:
                                    record.influence_weight = 1.0
                                if record.confidence_weight is None:
                                    record.confidence_weight = 0.5
                                
                                processed_in_batch += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing record with existing data: {e}")
                                continue
                    
                    # Process records that need OpenAI analysis (normal mode or skip_collection_only mode)
                    # Skip if use_existing_data=True (which processes records locally without OpenAI)
                    if texts_list and (skip_collection_only or not use_existing_data):
                        # Batch process all texts at once
                        try:
                            analysis_results = self.data_processor.batch_get_sentiment(
                                texts_list, 
                                source_types_list, 
                                max_workers=min(self.max_sentiment_workers, len(texts_list))
                            )
                            
                            # Update all records with batch results
                            # Note: In use_existing_data mode, records_needing_analysis contains tuples (record, embedding)
                            # In normal mode, it contains just records
                            for i, record_data in enumerate(records_needing_analysis):
                                if i < len(analysis_results):
                                    try:
                                        # Handle tuple format (record, embedding) or just record
                                        if isinstance(record_data, tuple):
                                            record = record_data[0]  # Skip - already processed above
                                            continue
                                        
                                        record = record_data
                                        analysis_result = analysis_results[i]
                                        
                                        # Update record with presidential sentiment analysis
                                        record.sentiment_label = analysis_result['sentiment_label']
                                        record.sentiment_score = analysis_result['sentiment_score']
                                        record.sentiment_justification = analysis_result['sentiment_justification']
                                        
                                        # Week 3: Store emotion detection results
                                        record.emotion_label = analysis_result.get('emotion_label')
                                        record.emotion_score = analysis_result.get('emotion_score')
                                        if analysis_result.get('emotion_distribution'):
                                            record.emotion_distribution = json.dumps(analysis_result['emotion_distribution'])
                                        
                                        # Week 3: Store weight calculations
                                        record.influence_weight = analysis_result.get('influence_weight', 1.0)
                                        record.confidence_weight = analysis_result.get('confidence_weight')
                                        
                                        # Update record with governance classification (two-phase: ministry + issue)
                                        record.issue_label = analysis_result.get('issue_label')
                                        record.issue_slug = analysis_result.get('issue_slug')
                                        record.issue_confidence = analysis_result.get('issue_confidence')
                                        record.issue_keywords = json.dumps(analysis_result.get('issue_keywords', []))
                                        record.ministry_hint = analysis_result.get('ministry_hint')
                                        
                                        # Week 2: Store topics in mention_topics table
                                        topics = analysis_result.get('topics', [])
                                        if topics:
                                            try:
                                                self.data_processor._store_topics_in_database(
                                                    db, 
                                                    record.entry_id, 
                                                    topics
                                                )
                                            except Exception as e:
                                                logger.warning(f"Failed to store topics for record {record.entry_id}: {e}")
                                        
                                        # Store embedding in separate table
                                        embedding_data = analysis_result.get('embedding', [])
                                        if embedding_data and len(embedding_data) == 1536:  # Validate embedding
                                            try:
                                                # Check if embedding already exists for this record
                                                existing_embedding = db.query(models.SentimentEmbedding).filter(
                                                    models.SentimentEmbedding.entry_id == record.entry_id
                                                ).first()
                                                
                                                if existing_embedding:
                                                    # Update existing embedding
                                                    existing_embedding.embedding = json.dumps(embedding_data)
                                                    existing_embedding.embedding_model = 'text-embedding-3-small'
                                                else:
                                                    # Create new embedding record
                                                    new_embedding = models.SentimentEmbedding(
                                                        entry_id=record.entry_id,
                                                        embedding=json.dumps(embedding_data),
                                                        embedding_model='text-embedding-3-small'
                                                    )
                                                    db.add(new_embedding)
                                            except Exception as e:
                                                logger.warning(f"Failed to store embedding for record {record.entry_id}: {e}")
                                        
                                        processed_in_batch += 1
                                        
                                    except Exception as e:
                                        logger.error(f"Error processing record {record.entry_id}: {e}")
                                        continue
                        except Exception as e:
                            logger.error(f"Error in batch sentiment processing: {e}")
                            # Fallback to sequential processing
                            for record in records_list:
                                try:
                                    text_content = record.text or record.content or record.title or record.description
                                    if text_content:
                                        analysis_result = self.data_processor.get_sentiment(text_content, record.source_type)
                                        
                                        record.sentiment_label = analysis_result['sentiment_label']
                                        record.sentiment_score = analysis_result['sentiment_score']
                                        record.sentiment_justification = analysis_result['sentiment_justification']
                                        
                                        # Week 3: Store emotion detection results (fallback path)
                                        record.emotion_label = analysis_result.get('emotion_label')
                                        record.emotion_score = analysis_result.get('emotion_score')
                                        if analysis_result.get('emotion_distribution'):
                                            record.emotion_distribution = json.dumps(analysis_result['emotion_distribution'])
                                        
                                        # Week 3: Store weight calculations (fallback path)
                                        record.influence_weight = analysis_result.get('influence_weight', 1.0)
                                        record.confidence_weight = analysis_result.get('confidence_weight')
                                        
                                        record.issue_label = analysis_result.get('issue_label')
                                        record.issue_slug = analysis_result.get('issue_slug')
                                        record.issue_confidence = analysis_result.get('issue_confidence')
                                        record.issue_keywords = json.dumps(analysis_result.get('issue_keywords', []))
                                        record.ministry_hint = analysis_result.get('ministry_hint')
                                        
                                        # Week 2: Store topics in mention_topics table (fallback path)
                                        topics = analysis_result.get('topics', [])
                                        if topics:
                                            try:
                                                self.data_processor._store_topics_in_database(
                                                    db, 
                                                    record.entry_id, 
                                                    topics
                                                )
                                            except Exception as e:
                                                logger.warning(f"Failed to store topics for record {record.entry_id}: {e}")
                                        
                                        processed_in_batch += 1
                                except Exception as e2:
                                    logger.error(f"Error in fallback processing for record {record.entry_id}: {e2}")
                                    continue
                    
                    # Commit changes for this batch
                    db.commit()
                    if use_existing_data and skipped_with_existing > 0:
                        logger.info(f"✅ Committed sentiment batch {batch_idx + 1}/{len(batches)} ({processed_in_batch} records processed, {skipped_with_existing} skipped with existing data)")
                    else:
                        logger.info(f"✅ Committed sentiment batch {batch_idx + 1}/{len(batches)} ({processed_in_batch} records)")
                
            except Exception as e:
                logger.error(f"Error processing sentiment batch {batch_idx + 1}: {e}")
            
            return processed_in_batch
        
        # Execute batches in parallel
        with ThreadPoolExecutor(max_workers=self.max_sentiment_workers) as executor:
            # Submit all batch tasks
            future_to_batch = {
                executor.submit(process_single_batch, (idx, batch)): idx 
                for idx, batch in enumerate(batches)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    results[batch_idx] = future.result()
                except Exception as e:
                    logger.error(f"Exception in sentiment batch {batch_idx}: {e}")
                    results[batch_idx] = 0
        
        return results

    def _run_location_batch_update_parallel(self, user_id: str):
        """Run location classification in parallel batches for newly inserted unique records or existing unanalyzed records"""
        try:
            logger.info(f"Starting parallel batch location updates for user {user_id}")
            
            with self.db_factory() as db:
                # If we have unique records from deduplication, filter to just those
                if hasattr(self, '_unique_records') and self._unique_records:
                    logger.info(f"Using unique records from deduplication for location updates")
                    # Query for the records that were just inserted (they won't have location data yet)
                    unique_texts = []
                    for record in self._unique_records:
                        text_content = record.get('text') or record.get('content') or record.get('title') or record.get('description')
                        if text_content:
                            unique_texts.append(text_content)
                    
                    if not unique_texts:
                        logger.info("No text content found in unique records, skipping location updates")
                        return True
                    
                    # Query database for the newly inserted records that need location updates
                    records_needing_location = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id,
                        models.SentimentData.text.in_(unique_texts),  # Only the newly inserted records
                        or_(
                            models.SentimentData.location_label.is_(None),
                            models.SentimentData.location_confidence < 0.7
                        )
                    ).all()
                else:
                    # No deduplication records, query for all unanalyzed records for this user
                    logger.info(f"No deduplication records, querying database for all records needing location updates")
                    max_records = self.config_manager.get_int("processing.limits.max_records_per_batch", 500)
                    records_needing_location = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id,
                        or_(
                            models.SentimentData.location_label.is_(None),
                            models.SentimentData.location_confidence < 0.7
                        )
                    ).limit(max_records).all()  # Process up to max_records_per_batch records at a time
                
                if not records_needing_location:
                    logger.info(f"No newly inserted records need location updates for user {user_id}")
                    return True
                
                logger.info(f"Found {len(records_needing_location)} newly inserted records for parallel location updates")
                
                # Process in parallel batches
                batch_size = self.location_batch_size
                
                # Split records into batches for parallel processing
                batches = []
                for i in range(0, len(records_needing_location), batch_size):
                    batch = records_needing_location[i:i + batch_size]
                    batches.append(batch)
                
                actual_location_workers = min(self.max_location_workers, len(batches))
                logger.info(f"Processing {len(batches)} location batches in parallel with {self.max_location_workers} workers (actual: {actual_location_workers})")
                auto_schedule_logger.info(f"[PHASE 5: LOCATION] Batches: {len(batches)} | Max Workers: {self.max_location_workers} | Actual Workers: {actual_location_workers} | Records: {len(records_needing_location)}")
                
                # Process batches in parallel
                batch_results = self._process_location_batches_parallel(batches, user_id)
                
                # Count successful processing
                updated_count = sum(batch_results.values())
                
                logger.info(f"Parallel location updates completed: {updated_count}/{len(records_needing_location)} records updated")
                
                return updated_count > 0
                
        except Exception as e:
            logger.error(f"Error during parallel location batch update: {e}", exc_info=True)
            return False
    
    def _run_issue_detection(self, user_id: str, recalculate_existing: bool = False) -> bool:
        """
        Run issue detection for all topics (Phase 6).
        
        This method detects issues by clustering mentions that have been classified with topics.
        Issues are created in the topic_issues table and linked to mentions via issue_mentions.
        
        Args:
            user_id: User ID for logging purposes
            recalculate_existing: If True, also recalculates metrics for all existing issues
            
        Returns:
            bool: True if issue detection completed successfully, False otherwise
        """
        try:
            logger.info(f"Starting issue detection for user {user_id}...")
            
            # Detect issues for all topics
            # This will process all mentions that have topics assigned and cluster them into issues
            all_issues = self.data_processor.detect_issues_for_all_topics()
            
            # Count total issues created/updated
            total_issues = sum(len(issues) for issues in all_issues.values())
            
            logger.info(f"Issue detection completed for user {user_id}: {total_issues} issues detected across {len(all_issues)} topics")
            
            # Log summary per topic
            for topic_key, issues in all_issues.items():
                if issues:
                    logger.debug(f"Topic {topic_key}: {len(issues)} issues detected")
            
            # Recalculate all existing issues if requested (for processing existing data)
            if recalculate_existing:
                logger.info(f"Recalculating metrics for all existing issues...")
                if self.data_processor.issue_detection_engine:
                    recalculated_count = self.data_processor.issue_detection_engine.recalculate_all_issues()
                    logger.info(f"Recalculated metrics for {recalculated_count} existing issues")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during issue detection for user {user_id}: {e}", exc_info=True)
            return False

    def _process_location_batches_parallel(self, batches: List[List], user_id: str) -> Dict[int, int]:
        """Process location classification batches in parallel using ThreadPoolExecutor."""
        results = {}
        
        def process_single_location_batch(batch_data: tuple) -> int:
            """Process a single batch of records for location classification and return count of updated records."""
            batch_idx, batch = batch_data
            updated_in_batch = 0
            
            try:
                logger.info(f"Processing location batch {batch_idx + 1}/{len(batches)} ({len(batch)} records)")
                
                # Create a new database session for this thread
                with self.db_factory() as db:
                    for record in batch:
                        try:
                            text = record.text or record.content or record.title or ""
                            platform = record.platform or ""
                            source = record.source or ""
                            user_location = record.user_location or ""
                            user_name = record.user_name or ""
                            user_handle = record.user_handle or ""
                            
                            # Perform location classification
                            location_label, confidence = self.location_classifier.classify(
                                text, platform, source, user_location, user_name, user_handle
                            )
                            
                            # Update record with location data
                            record.location_label = location_label
                            record.location_confidence = confidence
                            updated_in_batch += 1
                            
                        except Exception as e:
                            logger.error(f"Error updating location for record {record.entry_id}: {e}")
                            continue
                    
                    # Commit changes for this batch
                    db.commit()
                    logger.info(f"✅ Committed location batch {batch_idx + 1}/{len(batches)} ({updated_in_batch} records)")
                
            except Exception as e:
                logger.error(f"Error processing location batch {batch_idx + 1}: {e}")
            
            return updated_in_batch
        
        # Execute batches in parallel
        with ThreadPoolExecutor(max_workers=self.max_location_workers) as executor:
            # Submit all batch tasks
            future_to_batch = {
                executor.submit(process_single_location_batch, (idx, batch)): idx 
                for idx, batch in enumerate(batches)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    results[batch_idx] = future.result()
                except Exception as e:
                    logger.error(f"Exception in location batch {batch_idx}: {e}")
                    results[batch_idx] = 0
        
        return results

def parse_delay_to_seconds(delay_str: str) -> Optional[int]:
    """Parses a delay string (e.g., '10min', '30sec', 'now') into seconds."""
    delay_str = delay_str.strip().lower()
    
    if not delay_str:
        return None # Skip initial run if blank
        
    if delay_str == 'now':
        return 0
        
    # Updated regex to include hour units (h, hr, hour)
    match = re.match(r'^(\d+)\s*(min|sec|s|m|h|hr|hour)?$', delay_str)
    if not match:
        logger.warning(f"Invalid delay format: '{delay_str}'. Skipping initial run.")
        return None
        
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit in ['min', 'm']:
        return value * 60
    elif unit in ['sec', 's', None]: # Default to seconds if no unit
        return value
    elif unit in ['h', 'hr', 'hour']: # Added hour support
        return value * 3600
    else:
        # This case should technically not be reached with the updated regex, but kept for safety
        logger.warning(f"Unknown time unit in delay: '{unit}'. Skipping initial run.")
        return None

if __name__ == "__main__":
    print("--- EXECUTING src.agent.core as main script (v2) ---") # DEBUG
    logger.info("--- src.agent.core __main__ block started (v2) ---") # DEBUG
    # --- Configure root logger for INFO level ---
    logging.basicConfig(
        level=logging.INFO, # Set level to INFO
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # -----------------------------------------------
    logger.info("Root logger configured for INFO level.") # Add info log

    # Need to initialize DB connection when running directly
    logger.debug("Attempting database initialization...") # Add debug log
    try:
        from src.api.database import SessionLocal, engine # Import SessionLocal and engine
        # Optional: Test connection or create tables if needed
        # from src.api.models import Base
        # Base.metadata.create_all(bind=engine) 
        logger.info("Database connection initialized for standalone agent run.")
    except ImportError as e:
        logger.error(f"Failed to import database components: {e}. Ensure API structure is correct.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        sys.exit(1)
    logger.debug("Database initialization successful.") # Add debug log

    # Pass the db_factory (SessionLocal) to the agent constructor
    logger.debug("Initializing SentimentAnalysisAgent...") # Add debug log
    try:
        agent = SentimentAnalysisAgent(db_factory=SessionLocal)
        logger.info("Agent initialized successfully.")
    except Exception as agent_init_e:
        logger.error(f"CRITICAL ERROR during SentimentAnalysisAgent initialization: {agent_init_e}", exc_info=True)
        sys.exit(1)

    logger.info("Initial data collection and processing skipped. Agent ready for API triggers.")
    logger.info("Agent script finished initialization. Main loop is deprecated and not started. Ready for API triggers.")
