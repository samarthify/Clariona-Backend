import os
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Callable, Optional
import json
from pathlib import Path
import subprocess
import sys

# Enable UTF-8 mode on Windows to support emoji characters in logs
if sys.platform == 'win32':
    try:
        # For Python 3.7+, enable UTF-8 mode
        if hasattr(sys, 'set_int_max_str_digits'):
            os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass
import glob
import threading
import queue
import asyncio
import re
import requests
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
from src.utils.mail_config import NOTIFY_ON_ANALYSIS
from src.utils.notification_service import send_analysis_report, send_processing_notification, send_collection_notification
from src.processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
from src.processing.data_processor import DataProcessor
from uuid import UUID
# Add necessary DB imports
from sqlalchemy.orm import sessionmaker, Session 
from src.api.models import TargetIndividualConfiguration, EmailConfiguration
import src.api.models as models # Added for location classification update
from sqlalchemy import or_
# Add deduplication service import
from src.utils.deduplication_service import DeduplicationService

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
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler('logs/agent.log', encoding='utf-8')
    handlers.append(file_handler)
except Exception as e:
    print(f"Warning: Could not create logs directory: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger('AgentCore')

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
        os.makedirs('logs', exist_ok=True)
        auto_schedule_file_handler = logging.FileHandler(
            'logs/automatic_scheduling.log', 
            encoding='utf-8'
        )
        auto_schedule_file_handler.setLevel(logging.INFO)
        auto_schedule_file_handler.setFormatter(formatter)
        auto_schedule_logger.addHandler(auto_schedule_file_handler)
        auto_schedule_logger.propagate = False  # Don't propagate to root logger
    except Exception as e:
        logger.error(f"Failed to setup automatic scheduling logger: {e}")
    
    return auto_schedule_logger

# Initialize automatic scheduling logger
auto_schedule_logger = setup_auto_schedule_logger()

# Define API endpoint URL (Best practice: move to config or env var)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000") # Default for local dev
DATA_UPDATE_ENDPOINT = f"{API_BASE_URL}/data/update"


def convert_uuid_to_str(obj):
    """Convert UUID fields in the object to strings."""
    if isinstance(obj, dict):
        return {key: convert_uuid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_uuid_to_str(item) for item in obj]
    elif isinstance(obj, UUID):
        return str(obj)  # Convert UUID to string
    return obj

def safe_float(value):
    """Safely convert a value to float, returning None if conversion fails."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ('none', 'null', 'nan', ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None

def safe_int(value):
    """Safely convert a value to int, returning None if conversion fails."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ('none', 'null', 'nan', ''):
            return None
        try:
            return int(float(value))  # Convert via float to handle "1.0" strings
        except (ValueError, TypeError):
            return None
    return None


class SentimentAnalysisAgent:
    """Core agent responsible for data collection, processing, analysis, and scheduling."""

    def __init__(self, db_factory: sessionmaker, config_path="config/agent_config.json"):
        """
        Initialize the agent.

        Args:
            db_factory (sessionmaker): SQLAlchemy session factory.
            config_path (str): Path to the agent's configuration file.
        """
        self.db_factory = db_factory
        self.config_path = Path(config_path)
        self.base_path = Path(__file__).parent.parent.parent  # Project root directory
        from utils.deduplication_service import DeduplicationService
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
        
        # Parallel processing configuration
        parallel_config = self.config.get('parallel_processing', {})
        self.max_collector_workers = parallel_config.get('max_collector_workers', 3)
        self.max_sentiment_workers = parallel_config.get('max_sentiment_workers', 4)
        self.max_location_workers = parallel_config.get('max_location_workers', 2)
        self.sentiment_batch_size = parallel_config.get('sentiment_batch_size', 50)
        self.location_batch_size = parallel_config.get('location_batch_size', 100)
        self.collector_timeout = parallel_config.get('collector_timeout_seconds', 1000)  # NEW: Default 180s
        self.batch_timeout = parallel_config.get('batch_timeout_seconds', None)  # No timeout by default
        self.apify_timeout = parallel_config.get('apify_timeout_seconds', 180)  # NEW: Apify actor timeout
        self.apify_wait = parallel_config.get('apify_wait_seconds', 180)  # NEW: Apify wait timeout
        self.lock_max_age = parallel_config.get('lock_max_age_seconds', 300)  # NEW: Auto-unlock threshold
        self.parallel_enabled = parallel_config.get('enabled', True)

        # OpenAI logging configuration
        self.openai_logging_config = self.config.get('openai_logging', {})
        self.enable_openai_logging = self.openai_logging_config.get('enabled', False)

        logger.info(f"Timeout Configuration: collector={self.collector_timeout}s, apify={self.apify_timeout}s, lock_max_age={self.lock_max_age}s")
        
        # Automatic scheduling configuration
        auto_scheduling_config = self.config.get('auto_scheduling', {})
        self.auto_scheduling_enabled = auto_scheduling_config.get('enabled', False)
        
        # Enabled user IDs whitelist - only these users will run automatic scheduling
        self.enabled_user_ids = auto_scheduling_config.get('enabled_user_ids', [])
        if self.enabled_user_ids:
            logger.info(f"Auto-scheduling enabled for {len(self.enabled_user_ids)} whitelisted user(s): {self.enabled_user_ids}")
        else:
            logger.info("Auto-scheduling enabled for ALL users (no whitelist specified)")
        
        # Use cycle_interval_minutes from auto_scheduling if available, otherwise fall back to root collection_interval_minutes
        self.cycle_interval_minutes = auto_scheduling_config.get('cycle_interval_minutes', 
                                                                  self.config.get('collection_interval_minutes', 60))
        self.collection_interval_minutes = self.cycle_interval_minutes  # Keep for backward compatibility
        
        # Continuous mode: if true, cycles run continuously without waiting for interval
        self.continuous_mode = auto_scheduling_config.get('continuous_mode', False)
        # Stop after a single batch of cycles if enabled
        self.stop_after_first_cycle = auto_scheduling_config.get('stop_after_first_cycle', False)
        
        # Max consecutive cycles: 0 means unlimited, >0 means limit consecutive cycles
        self.max_consecutive_cycles = auto_scheduling_config.get('max_consecutive_cycles', 0)
        
        self.processing_interval_minutes = self.config.get('processing_interval_minutes', 120)
        self.cleanup_interval_hours = self.config.get('cleanup_interval_hours', 24)
        
        # Background job management
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.active_users = set()  # Track users with active schedules
        
        # Track consecutive cycles per user for max_consecutive_cycles limit
        self.user_consecutive_cycles = {}  # {user_id: count}
        
        # Task status tracking
        self.task_status = {
            'is_busy': False,
            'current_task': None,
            'lock_time': None,           # NEW: Track when lock was acquired
            'last_run': {},
            'suggestions': []
        }
        self.active_collection_threads = {}  # NEW: Track running collection threads
        
        # Initialize processor with dual-analyzer system
        # DataProcessor now includes both PresidentialSentimentAnalyzer + GovernanceAnalyzer (two-phase)
        logger.debug("Initializing DataProcessor with dual-analyzer system...")
        self.data_processor = DataProcessor()
        
        # Keep reference to sentiment analyzer for backward compatibility
        self.sentiment_analyzer = PresidentialSentimentAnalyzer()
        
        # Initialize enhanced location classifier
        self.location_classifier = self._init_location_classifier()
        
        # Log useful configuration information
        logger.info("=" * 60)
        logger.info("Agent Configuration Summary")
        logger.info("=" * 60)
        logger.info(f"Parallel Processing: {'ENABLED' if self.parallel_enabled else 'DISABLED'}")
        if self.parallel_enabled:
            logger.info(f"Worker Configuration:")
            logger.info(f"  - Collector Workers: {self.max_collector_workers}")
            logger.info(f"  - Sentiment Workers: {self.max_sentiment_workers}")
            logger.info(f"  - Location Workers: {self.max_location_workers}")
            logger.info(f"  - Total Max Workers: {self.max_collector_workers + self.max_sentiment_workers + self.max_location_workers}")
            logger.info(f"Batch Sizes:")
            logger.info(f"  - Sentiment Batch: {self.sentiment_batch_size} records")
            logger.info(f"  - Location Batch: {self.location_batch_size} records")
            if self.collector_timeout:
                logger.info(f"  - Collector Timeout: {self.collector_timeout}s")
            if self.batch_timeout:
                logger.info(f"  - Batch Timeout: {self.batch_timeout}s")
        logger.info(f"Auto Scheduling: {'ENABLED' if self.auto_scheduling_enabled else 'DISABLED'}")
        if self.auto_scheduling_enabled:
            logger.info(f"  - Cycle Interval: {self.cycle_interval_minutes} minutes")
            logger.info(f"  - Continuous Mode: {self.continuous_mode}")
            logger.info(f"  - Max Consecutive Cycles: {self.max_consecutive_cycles if self.max_consecutive_cycles > 0 else 'Unlimited'}")
        logger.info(f"OpenAI Logging: {'ENABLED' if self.enable_openai_logging else 'DISABLED'}")
        logger.info("=" * 60)
        
        logger.debug("Agent initialization complete with dual-analyzer system")

        # Initialize OpenAI call logging if enabled
        if self.enable_openai_logging:
            try:
                from src.utils.openai_logging import install_openai_logging

                log_path = self.openai_logging_config.get('log_path', 'logs/openai_calls.csv')
                max_chars = self.openai_logging_config.get('max_chars', 2000)
                redact_prompts = self.openai_logging_config.get('redact_prompts', False)
                log_to_console = self.openai_logging_config.get('log_to_console', False)
                install_openai_logging(True, log_path, max_chars=max_chars, redact_prompts=redact_prompts, log_to_console=log_to_console)
                logger.info(f"OpenAI logging initialized. Output: {log_path}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI logging: {e}")
        
    def start_automatic_scheduling(self):
        """Start automatic scheduling for all configured users."""
        if not self.auto_scheduling_enabled:
            logger.warning("Automatic scheduling is disabled in configuration")
            auto_schedule_logger.warning("AUTOMATIC SCHEDULING DISABLED - Cannot start scheduler")
            return False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler is already running")
            auto_schedule_logger.warning("Scheduler is already running")
            return True
        
        try:
            self.stop_event.clear()
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler_loop)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger.info("Automatic scheduling started successfully")
            auto_schedule_logger.info("=" * 80)
            auto_schedule_logger.info("AUTOMATIC SCHEDULING STARTED")
            auto_schedule_logger.info(f"Configuration: cycle_interval={self.cycle_interval_minutes}min, continuous_mode={self.continuous_mode}, max_consecutive_cycles={self.max_consecutive_cycles}")
            auto_schedule_logger.info("=" * 80)
            return True
        except Exception as e:
            logger.error(f"Failed to start automatic scheduling: {e}", exc_info=True)
            auto_schedule_logger.error(f"FAILED TO START AUTOMATIC SCHEDULING: {e}")
            return False
    
    def stop_automatic_scheduling(self, graceful: bool = False):
        """Stop scheduler and optionally allow in-flight cycles to finish."""
        logger.info(f"Stopping automatic scheduling (graceful={graceful})...")

        # Signal scheduler loop to stop scheduling new work
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_event.set()
            self.is_running = False

        if graceful:
            # Do not force-stop active collection threads; let them finish
            active_count = len(self.active_collection_threads)
            if active_count > 0:
                logger.info(f"Graceful stop requested: allowing {active_count} active collection thread(s) to finish.")
            else:
                logger.info("Graceful stop requested: no active collection threads.")

            # Join scheduler thread briefly just to tidy up
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=10)
                logger.info("Scheduler thread stopped (graceful).")
            logger.info("Graceful stop: scheduler halted; active cycles will complete naturally.")
            return

        # Hard stop path (existing behavior)
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
            logger.info("Scheduler thread stopped")

        active_count = len(self.active_collection_threads)
        if active_count > 0:
            logger.warning(f"Force-stopping {active_count} active collection threads...")

            for user_id, thread in list(self.active_collection_threads.items()):
                if thread.is_alive():
                    logger.warning(f"Collection thread for user {user_id} still running - marking for termination")
                    # Note: Python threads can't be force-killed safely
                    # We rely on subprocess timeouts to eventually complete

            # Wait up to 30 seconds for threads to finish
            timeout = 30
            start = time.time()
            while self.active_collection_threads and (time.time() - start) < timeout:
                time.sleep(1)
                logger.debug(f"Waiting for {len(self.active_collection_threads)} threads...")

            if self.active_collection_threads:
                logger.error(f"⚠️ {len(self.active_collection_threads)} threads did not stop gracefully")
                # Force-clear the dict
                self.active_collection_threads.clear()

        # Force-release the lock (critical fix!)
        if self.task_status['is_busy']:
            logger.warning("🔓 FORCE-RELEASING LOCK on stop API call")
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None

        logger.info("=" * 80)
        logger.info("AUTOMATIC SCHEDULING STOPPED")
        logger.info(f"Threads cleared: {active_count}")
        logger.info(f"Lock released: Yes")
        logger.info("=" * 80)

        auto_schedule_logger.info("=" * 80)
        auto_schedule_logger.info("AUTOMATIC SCHEDULING STOPPED")
        auto_schedule_logger.info(f"Active threads terminated: {active_count}")
        auto_schedule_logger.info(f"Lock force-released: {'Yes' if active_count > 0 or self.task_status.get('is_busy') else 'Not needed'}")
        auto_schedule_logger.info("=" * 80)
    
    def _run_scheduler_loop(self):
        """Main scheduler loop for automatic data collection."""
        logger.info(f"Starting automatic scheduler loop (continuous_mode={self.continuous_mode}, cycle_interval={self.cycle_interval_minutes}min, max_cycles={self.max_consecutive_cycles})")
        auto_schedule_logger.info(f"Scheduler loop started | continuous_mode={self.continuous_mode} | cycle_interval={self.cycle_interval_minutes}min | max_consecutive_cycles={self.max_consecutive_cycles}")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                check_time = datetime.now()
                # Get all users with active configurations
                active_users = self._get_active_users()
                
                if not active_users:
                    logger.info("No active users found, sleeping for 5 minutes")
                    auto_schedule_logger.debug(f"[SCHEDULER CHECK] Timestamp: {check_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Active users: 0 | Action: Sleeping for 5 minutes")
                    time.sleep(300)  # Sleep for 5 minutes
                    continue
                
                auto_schedule_logger.debug(f"[SCHEDULER CHECK] Timestamp: {check_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Active users: {len(active_users)} | Users: {', '.join(active_users)}")
                
                # Schedule collection for each user
                for user_id in active_users:
                    if self.stop_event.is_set():
                        break
                    
                    # Check if it's time to run collection for this user
                    if self._should_run_collection(user_id):
                        logger.info(f"Scheduling automatic collection for user {user_id}")
                        auto_schedule_logger.info(f"[SCHEDULER DECISION] User: {user_id} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Decision: SCHEDULE CYCLE")
                        
                        # Run collection in background thread to avoid blocking
                        collection_thread = threading.Thread(
                            target=self._run_automatic_collection_tracked,
                            args=(user_id,),
                            name=f"collection_{user_id}"
                        )
                        collection_thread.daemon = True
                        self.active_collection_threads[user_id] = collection_thread
                        collection_thread.start()
                        logger.debug(f"Started collection thread for user {user_id}")
                    else:
                        # Reset consecutive cycles when max is reached and enough time has passed
                        if self.max_consecutive_cycles > 0 and user_id in self.user_consecutive_cycles:
                            consecutive_count = self.user_consecutive_cycles.get(user_id, 0)
                            if consecutive_count >= self.max_consecutive_cycles:
                                # Check if enough time has passed since last run to reset counter
                                last_run_key = f'collect_user_{user_id}'
                                last_run_info = self.task_status['last_run'].get(last_run_key)
                                if last_run_info:
                                    try:
                                        last_run_time = datetime.fromisoformat(last_run_info['time'])
                                        time_since_last_run = datetime.now() - last_run_time
                                        # Reset counter after one full interval has passed
                                        if time_since_last_run.total_seconds() >= (self.cycle_interval_minutes * 60):
                                            self.user_consecutive_cycles[user_id] = 0
                                            logger.info(f"Reset consecutive cycles for user {user_id} after max cycles limit")
                                            auto_schedule_logger.info(f"[SCHEDULER RESET] User: {user_id} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Consecutive cycles reset (max limit reached)")
                                    except Exception:
                                        pass
                        else:
                            # Log why cycle is not scheduled
                            last_run_key = f'collect_user_{user_id}'
                            last_run_info = self.task_status['last_run'].get(last_run_key)
                            if last_run_info:
                                try:
                                    last_run_time = datetime.fromisoformat(last_run_info['time'])
                                    time_since_last_run = datetime.now() - last_run_time
                                    time_until_next = (self.cycle_interval_minutes * 60) - time_since_last_run.total_seconds()
                                    if time_until_next > 0:
                                        auto_schedule_logger.debug(f"[SCHEDULER DECISION] User: {user_id} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Decision: SKIP (next run in {time_until_next/60:.1f}min)")
                                except Exception:
                                    pass

                # If configured to stop after the first scheduling pass, exit loop gracefully
                if self.stop_after_first_cycle:
                    logger.info("stop_after_first_cycle enabled: exiting scheduler after initial cycle dispatch.")
                    auto_schedule_logger.info(f"[SCHEDULER] stop_after_first_cycle enabled - stopping after first dispatch at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

                    # Wait for any active collection threads to finish (up to 60s) before ending
                    wait_start = time.time()
                    while self.active_collection_threads and (time.time() - wait_start) < 60:
                        time.sleep(1)
                        logger.debug(f"Waiting for active collection threads to finish: {len(self.active_collection_threads)} remaining")

                    if self.active_collection_threads:
                        logger.warning(f"{len(self.active_collection_threads)} collection threads still running after wait; exiting scheduler loop.")

                    self.is_running = False
                    self.stop_event.set()
                    break
                
                # In continuous mode, sleep shorter to check more frequently
                # In interval mode, sleep for 1 minute before next check
                # Increased continuous mode sleep to 30s to allow collectors to finish
                sleep_time = 30 if self.continuous_mode else 60
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                auto_schedule_logger.error(f"[SCHEDULER ERROR] Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Error: {str(e)}")
                time.sleep(60)  # Sleep on error
        
        logger.info("Scheduler loop ended")
        auto_schedule_logger.info(f"Scheduler loop ended | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    
    def _get_active_users(self) -> List[str]:
        """Get list of users with active configurations."""
        try:
            with self.db_factory() as db:
                # Get users with target configurations
                configs = db.query(models.TargetIndividualConfiguration).all()
                user_ids = [str(config.user_id) for config in configs if config.user_id]
                
                # Filter out users who have disabled automatic scheduling
                active_users = []
                for user_id in user_ids:
                    if self._is_user_auto_scheduling_enabled(user_id):
                        active_users.append(user_id)
                
                return active_users
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    def _is_user_auto_scheduling_enabled(self, user_id: str) -> bool:
        """Check if automatic scheduling is enabled for a specific user."""
        try:
            # If whitelist is specified, only allow whitelisted users
            if self.enabled_user_ids:
                # Remove hyphens from user_id for comparison (DB stores without hyphens)
                user_id_normalized = user_id.replace('-', '')
                is_enabled = user_id_normalized in self.enabled_user_ids
                
                if not is_enabled:
                    logger.debug(f"User {user_id} not in whitelist - skipping automatic scheduling")
                
                return is_enabled
            
            # If no whitelist, enable for all users (backward compatibility)
            return True
        except Exception as e:
            logger.error(f"Error checking user auto-scheduling setting: {e}")
            return True  # Default to enabled on error
    
    def _should_run_collection(self, user_id: str) -> bool:
        """Check if it's time to run collection for a user."""
        try:
            # Check max consecutive cycles limit
            if self.max_consecutive_cycles > 0:
                consecutive_count = self.user_consecutive_cycles.get(user_id, 0)
                if consecutive_count >= self.max_consecutive_cycles:
                    logger.info(f"User {user_id} reached max consecutive cycles ({self.max_consecutive_cycles}), skipping")
                    return False
            
            # In continuous mode, always run if under max cycles limit
            if self.continuous_mode:
                logger.debug(f"Continuous mode enabled for user {user_id}, scheduling collection")
                return True
            
            # Get last run time for this user
            last_run_key = f'collect_user_{user_id}'
            last_run_info = self.task_status['last_run'].get(last_run_key)
            
            if not last_run_info:
                logger.info(f"No previous run found for user {user_id}, scheduling collection")
                return True
            
            # Check if a cycle is currently running for this user
            if last_run_info.get('status') == 'running':
                logger.debug(f"Collection already running for user {user_id}, skipping")
                return False
            
            # Check if enough time has passed
            last_run_time = datetime.fromisoformat(last_run_info['time'])
            time_since_last_run = datetime.now() - last_run_time
            interval_minutes = self.cycle_interval_minutes
            
            if time_since_last_run.total_seconds() >= (interval_minutes * 60):
                logger.info(f"Interval reached for user {user_id}, scheduling collection")
                return True
            
            logger.debug(f"Interval not reached for user {user_id} ({time_since_last_run.total_seconds()/60:.1f}/{interval_minutes} min)")
            return False
            
        except Exception as e:
            logger.error(f"Error checking collection schedule for user {user_id}: {e}")
            return False

    def _run_automatic_collection_tracked(self, user_id: str):
        """Wrapper that tracks thread lifecycle."""
        try:
            self._run_automatic_collection(user_id)
        finally:
            # Remove from active threads when done
            if user_id in self.active_collection_threads:
                del self.active_collection_threads[user_id]
                logger.debug(f"Removed collection thread for user {user_id}")

    def _run_automatic_collection(self, user_id: str):
        """Run automatic collection for a specific user."""
        cycle_start_time = datetime.now()
        try:
            logger.info(f"Starting automatic collection for user {user_id}")
            auto_schedule_logger.info("-" * 80)
            auto_schedule_logger.info(f"[CYCLE START] User: {user_id} | Timestamp: {cycle_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            auto_schedule_logger.info(f"Processing mode: {'PARALLEL' if self.parallel_enabled else 'SEQUENTIAL'}")
            if self.parallel_enabled:
                auto_schedule_logger.info(f"Worker Configuration: Collector={self.max_collector_workers} | Sentiment={self.max_sentiment_workers} | Location={self.max_location_workers}")
                auto_schedule_logger.info(f"Batch Sizes: Sentiment={self.sentiment_batch_size} | Location={self.location_batch_size}")
            
            # Use parallel processing if enabled, otherwise fallback to single-cycle wrapper
            if self.parallel_enabled:
                self.run_single_cycle_parallel(user_id)
            else:
                self.run_single_cycle(user_id)
            
            # Track successful consecutive cycle
            if user_id not in self.user_consecutive_cycles:
                self.user_consecutive_cycles[user_id] = 0
            self.user_consecutive_cycles[user_id] += 1
            
            cycle_end_time = datetime.now()
            cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
            logger.info(f"Completed automatic collection for user {user_id} (consecutive cycles: {self.user_consecutive_cycles.get(user_id, 0)})")
            auto_schedule_logger.info(f"[CYCLE END] User: {user_id} | Timestamp: {cycle_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {cycle_duration:.2f}s")
            auto_schedule_logger.info(f"Consecutive cycles: {self.user_consecutive_cycles.get(user_id, 0)}")
            auto_schedule_logger.info("-" * 80)
            
        except Exception as e:
            # Reset consecutive cycles on error
            if user_id in self.user_consecutive_cycles:
                self.user_consecutive_cycles[user_id] = 0
            cycle_end_time = datetime.now()
            cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
            logger.error(f"Error in automatic collection for user {user_id}: {e}", exc_info=True)
            auto_schedule_logger.error(f"[CYCLE ERROR] User: {user_id} | Timestamp: {cycle_end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {cycle_duration:.2f}s")
            auto_schedule_logger.error(f"Error: {str(e)}")
            auto_schedule_logger.info("-" * 80)
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            'is_running': self.is_running,
            'auto_scheduling_enabled': self.auto_scheduling_enabled,
            'cycle_interval_minutes': self.cycle_interval_minutes,
            'collection_interval_minutes': self.collection_interval_minutes,  # Backward compatibility
            'continuous_mode': self.continuous_mode,
            'stop_after_first_cycle': self.stop_after_first_cycle,
            'max_consecutive_cycles': self.max_consecutive_cycles,
            'processing_interval_minutes': self.processing_interval_minutes,
            'active_users_count': len(self.active_users),
            'scheduler_thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False,
            'last_run_times': self.task_status['last_run'],
            'user_consecutive_cycles': self.user_consecutive_cycles.copy(),
            'active_collection_threads': len(self.active_collection_threads)
        }

        logger.info(f"Agent initialized. Config loaded from {self.config_path}. Base path: {self.base_path}")
        logger.info(f"Database session factory provided: {db_factory}")
        logger.debug(f"SentimentAnalysisAgent.__init__ finished. Initial config: {self.config}")

    def _parse_date_string(self, date_str):
        """Parse date string to datetime object using DataProcessor's robust parser, return None if invalid"""
        if not date_str or pd.isna(date_str):
            return None
        try:
            # If already a datetime object, return as-is
            if isinstance(date_str, datetime):
                return date_str
            # Use DataProcessor's robust parse_date method which handles Twitter dates and multiple formats
            if isinstance(date_str, str):
                return self.data_processor.parse_date(date_str)
            return None
        except (ValueError, TypeError) as e:
            logger.debug(f"Error parsing date string '{date_str}': {e}")
            return None
    
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
        """Load agent configuration from JSON file, excluding the 'target' key."""
        logger.debug(f"load_config: Attempting to load config from {self.config_path}")
        default_config = {
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
                "log_path": "logs/openai_calls.csv",
                "max_chars": 2000,
                "redact_prompts": False
            }
            # 'target' key is intentionally omitted - fetched from DB
        }
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    loaded_conf = json.load(f)
                    # Explicitly remove 'target' if it exists from old file
                    loaded_conf.pop('target', None) 
                    # Merge with defaults, loaded keys take precedence
                    # We should ensure defaults cover all *expected* keys now
                    merged_config = default_config.copy()
                    merged_config.update(loaded_conf)
                    logger.debug(f"load_config: Loaded config: {merged_config}")
                    return merged_config
            else:
                logger.warning(f"Config file {self.config_path} not found. Using default configuration.")
                # Save default config if file doesn't exist
                with open(self.config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                return default_config
        except Exception as e:
            logger.error(f"Error loading config from {self.config_path}: {e}. Using default configuration.", exc_info=True)
            return default_config

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
        collector_logs_dir = self.base_path / 'logs' / 'collectors'
        collector_logs_dir.mkdir(parents=True, exist_ok=True)
        
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
                self._run_task(lambda: self.run_single_cycle(params['user_id']), f"process_cmd_{params['user_id']}") 
                return {"success": True, "message": f"Processing task triggered for user {params['user_id']}."}
            elif command == "update_locations":
                # --- Requires user_id now ---
                if 'user_id' not in params:
                    return {"success": False, "message": "update_locations command requires 'user_id' parameter."}
                batch_size = params.get('batch_size', 100)
                self._run_task(lambda: self.update_location_classifications(params['user_id'], batch_size), f"location_update_cmd_{params['user_id']}") 
                return {"success": True, "message": f"Location classification update triggered for user {params['user_id']} with batch size {batch_size}."}
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
        
        try:
            # Run the task function
            result = task_func() 
            # We assume the task function returns True on success, False or raises Exception on failure
            if isinstance(result, bool):
                success = result
            else:
                # Non-boolean return is treated as success (None or other values)
                success = True
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"_run_task: Task '{task_name}' completed successfully in {duration:.2f}s")
            
            # Update status
            self.task_status['last_run'][task_name].update({
                'success': success,
                'duration': duration,
                'status': 'completed'
            })
            
            return success
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            logger.error(f"_run_task: Task '{task_name}' failed after {duration:.2f}s: {error_msg}", exc_info=True)
            
            # Update status
            self.task_status['last_run'][task_name].update({
                'success': False,
                'duration': duration,
                'error': error_msg,
                'status': 'failed'
            })
            
            return False
        finally:
            # Always release lock
            self.task_status['is_busy'] = False
            self.task_status['current_task'] = None
            self.task_status['lock_time'] = None
            logger.debug(f"_run_task: Lock released for task '{task_name}'")

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
            logger.info(f"Sending {len(data_list)} records to API endpoint: {DATA_UPDATE_ENDPOINT}")
            # response = requests.post(DATA_UPDATE_ENDPOINT, json=payload, timeout=120) 
            response = requests.post(DATA_UPDATE_ENDPOINT, json=convert_uuid_to_str(payload), timeout=120)
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

    # --- Added method for user-triggered runs --- 
    def run_single_cycle(self, user_id: str):
        """Backward-compatible single-cycle runner. Currently delegates to parallel pipeline."""
        return self.run_single_cycle_parallel(user_id)

    def run_single_cycle_parallel(self, user_id: str):
        """Runs a single collection and processing cycle for a specific user with parallel processing."""
        if not user_id:
            logger.error("run_single_cycle_parallel: Called without user_id. Aborting.")
            return

        try:
            # 1. Parallel Data Collection (collect raw data, no analysis)
            collection_start = datetime.now()
            logger.info(f"Starting parallel data collection for user {user_id}...")
            
            auto_schedule_logger.info(f"[PHASE 1: COLLECTION START] User: {user_id} | Timestamp: {collection_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            
            collect_success = self._run_task(lambda: self.collect_data_parallel(user_id), f'collect_user_{user_id}')
            collection_end = datetime.now()
            collection_duration = (collection_end - collection_start).total_seconds()
            if collect_success:
                auto_schedule_logger.info(f"[PHASE 1: COLLECTION END] User: {user_id} | Timestamp: {collection_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {collection_duration:.2f}s | Max Workers: {self.max_collector_workers} | Status: SUCCESS")
            else:
                auto_schedule_logger.error(f"[PHASE 1: COLLECTION END] User: {user_id} | Timestamp: {collection_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {collection_duration:.2f}s | Max Workers: {self.max_collector_workers} | Status: FAILED")
            
            if collect_success:
                # 2. Load raw data from CSV files
                load_start = datetime.now()
                logger.info(f"Loading raw data from CSV files for user {user_id}...")
                auto_schedule_logger.info(f"[PHASE 2: DATA LOADING START] User: {user_id} | Timestamp: {load_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                load_success = self._run_task(
                    lambda: self._push_raw_data_to_db(user_id), 
                    f'load_raw_{user_id}'
                )
                load_end = datetime.now()
                load_duration = (load_end - load_start).total_seconds()
                if load_success:
                    # Get mention count after collection
                    mention_count = len(self._temp_raw_records) if hasattr(self, '_temp_raw_records') and self._temp_raw_records else 0
                    auto_schedule_logger.info(f"[PHASE 2: DATA LOADING END] User: {user_id} | Timestamp: {load_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {load_duration:.2f}s | Status: SUCCESS | Mentions Collected: {mention_count}")
                else:
                    auto_schedule_logger.error(f"[PHASE 2: DATA LOADING END] User: {user_id} | Timestamp: {load_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {load_duration:.2f}s | Status: FAILED")
                
                if load_success:
                    # 3. Run deduplication and insert unique records to DB
                    dedup_start = datetime.now()
                    logger.info(f"Running deduplication and inserting unique records for user {user_id}...")
                    auto_schedule_logger.info(f"[PHASE 3: DEDUPLICATION START] User: {user_id} | Timestamp: {dedup_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    dedup_success = self._run_task(
                        lambda: self._run_deduplication(user_id), 
                        f'dedup_{user_id}'
                    )
                    dedup_end = datetime.now()
                    dedup_duration = (dedup_end - dedup_start).total_seconds()
                    if dedup_success:
                        # Get deduplication stats if available
                        if hasattr(self, '_dedup_stats') and self._dedup_stats:
                            before_count = self._dedup_stats.get('total', 0)
                            after_count = self._dedup_stats.get('unique', 0)
                            auto_schedule_logger.info(f"[PHASE 3: DEDUPLICATION END] User: {user_id} | Timestamp: {dedup_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {dedup_duration:.2f}s | Status: SUCCESS | Records: {before_count} -> {after_count}")
                        else:
                            auto_schedule_logger.info(f"[PHASE 3: DEDUPLICATION END] User: {user_id} | Timestamp: {dedup_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {dedup_duration:.2f}s | Status: SUCCESS")
                    else:
                        auto_schedule_logger.error(f"[PHASE 3: DEDUPLICATION END] User: {user_id} | Timestamp: {dedup_end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | Duration: {dedup_duration:.2f}s | Status: FAILED")
                else:
                    dedup_success = False
                
                if dedup_success:
                    # 4. Parallel sentiment analysis (configurable batch size)
                    sentiment_start = datetime.now()
                    logger.info(f"Starting parallel sentiment analysis for user {user_id}...")
                    auto_schedule_logger.info(f"[PHASE 4: SENTIMENT ANALYSIS START] User: {user_id} | Timestamp: {sentiment_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
                    auto_schedule_logger.info(f"[PHASE 4: SENTIMENT] Max Workers: {self.max_sentiment_workers} | Batch Size: {self.sentiment_batch_size}")
                    sentiment_success = self._run_task(
                        lambda: self._run_sentiment_batch_update_parallel(user_id), 
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
                    
                    logger.info(f"Parallel cycle completed for user {user_id}: Collection ✅, Deduplication ✅, Sentiment ✅, Location ✅")
                    total_duration = (location_end - collection_start).total_seconds()
                    auto_schedule_logger.info(f"[CYCLE SUMMARY] User: {user_id} | Total Duration: {total_duration:.2f}s | Collection: {collection_duration:.2f}s | Loading: {load_duration:.2f}s | Dedup: {dedup_duration:.2f}s | Sentiment: {sentiment_duration:.2f}s | Location: {location_duration:.2f}s")
                else:
                    logger.warning(f"Deduplication failed for user {user_id}, skipping analysis steps")
                    auto_schedule_logger.warning(f"[CYCLE ABORTED] User: {user_id} | Reason: Deduplication failed")
            else:
                logger.warning(f"Parallel data collection failed for user {user_id}, skipping subsequent steps")
                auto_schedule_logger.warning(f"[CYCLE ABORTED] User: {user_id} | Reason: Collection failed")

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

    def update_location_classifications(self, user_id: str, batch_size: int = 100) -> Dict[str, Any]:
        """
        Update location classifications for existing records in the database.
        This is similar to the batch location classification script functionality.
        
        Args:
            user_id (str): The user ID to process records for
            batch_size (int): Number of records to process in each batch
            
        Returns:
            Dict containing update statistics
        """
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
            
            raw_data_path = self.base_path / 'data' / 'raw'
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

    def _prepare_record_mapping(self, record_data: Dict[str, Any], user_id: str, current_timestamp: datetime) -> Dict[str, Any]:
        """Helper method to prepare a record mapping dictionary for database insert/update"""
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
        
        return db_mapping

    def _run_deduplication(self, user_id: str):
        """Run deduplication on collected raw data - updates existing records instead of filtering duplicates"""
        try:
            logger.info(f"🔍 DEBUG: Starting _run_deduplication for user {user_id}")
            logger.info(f"🔍 DEBUG: Has _temp_raw_records: {hasattr(self, '_temp_raw_records')}")
            if hasattr(self, '_temp_raw_records'):
                logger.info(f"🔍 DEBUG: _temp_raw_records length: {len(self._temp_raw_records) if self._temp_raw_records else 'None'}")
            
            if not hasattr(self, '_temp_raw_records') or not self._temp_raw_records:
                logger.info("No raw records to process")
                # Set empty stats for logging
                self._dedup_stats = {'total': 0, 'unique': 0, 'duplicates': 0, 'updated': 0}
                return True
            
            logger.info(f"Starting deduplication/update for user {user_id} with {len(self._temp_raw_records)} records")
            logger.info("🔄 DEDUPLICATION DISABLED: Duplicate records will be updated instead of filtered out")
            
            with self.db_factory() as db:
                # Run deduplication to identify duplicates
                dedup_results = self.deduplication_service.deduplicate_new_data(
                    self._temp_raw_records, db, user_id
                )
                
                duplicate_map = dedup_results.get('duplicate_map', {})
                duplicate_records = dedup_results.get('duplicate_records', [])
                unique_records = dedup_results.get('unique_records', [])
                
                current_timestamp = datetime.utcnow()
                update_count = 0
                insert_count = 0
                update_mappings = []  # Initialize outside the if block
                
                # Update existing duplicate records
                if duplicate_map:
                    logger.info(f"Updating {len(duplicate_map)} existing duplicate records")
                    
                    # For each duplicate, update the first existing record (take the first entry_id from the list)
                    for new_index, existing_entry_ids in duplicate_map.items():
                        if new_index < len(self._temp_raw_records) and existing_entry_ids:
                            try:
                                record_data = self._temp_raw_records[new_index]
                                db_mapping = self._prepare_record_mapping(record_data, user_id, current_timestamp)
                                # Add entry_id for update
                                db_mapping['entry_id'] = existing_entry_ids[0]  # Update the first duplicate found
                                update_mappings.append(db_mapping)
                            except Exception as e:
                                logger.error(f"Error preparing duplicate record for update: {e}")
                                if new_index < len(self._temp_raw_records):
                                    record_data = self._temp_raw_records[new_index]
                                    logger.error(f"Record URL: {record_data.get('url', 'N/A')}")
                                continue
                    
                    # Perform bulk update
                    if update_mappings:
                        try:
                            db.bulk_update_mappings(models.SentimentData, update_mappings)
                            db.commit()
                            update_count = len(update_mappings)
                            logger.info(f"Successfully updated {update_count} existing records in database")
                        except Exception as e:
                            logger.error(f"Error during bulk update: {e}", exc_info=True)
                            db.rollback()
                
                # Insert unique records into database using bulk insert
                if unique_records:
                    logger.info(f"Inserting {len(unique_records)} unique records into database")
                    
                    # Prepare data for bulk insert
                    bulk_data = []
                    
                    for record_data in unique_records:
                        try:
                            db_mapping = self._prepare_record_mapping(record_data, user_id, current_timestamp)
                            bulk_data.append(db_mapping)
                        except Exception as e:
                            logger.error(f"Error preparing record for bulk insert: {e}")
                            logger.error(f"Record URL: {record_data.get('url', 'N/A')}")
                            logger.error(f"Record platform: {record_data.get('platform', 'N/A')}")
                            continue
                    
                    # Use bulk_insert_mappings for better performance and explicit column mapping
                    if bulk_data:
                        try:
                            db.bulk_insert_mappings(models.SentimentData, bulk_data)
                            db.commit()
                            insert_count = len(bulk_data)
                            logger.info(f"Successfully inserted {insert_count} unique records into database")
                        except Exception as e:
                            logger.error(f"Error during bulk insert: {e}", exc_info=True)
                            db.rollback()
                
                # Update stats for logging
                self._dedup_stats = {
                    'total': len(self._temp_raw_records),
                    'unique': insert_count,
                    'duplicates': len(duplicate_records),
                    'updated': update_count
                }
                
                # Log summary
                logger.info(f"Deduplication/Update completed: {insert_count} inserted, {update_count} updated, {len(duplicate_records)} duplicates found")
                
                # Store unique records for potential use in sentiment analysis
                self._unique_records = unique_records
                
                if not unique_records and not update_mappings:
                    logger.info("No records to insert or update")
                
                # Clean up raw CSV files after successful processing
                raw_data_path = self.base_path / 'data' / 'raw'
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

    def _run_sentiment_batch_update_parallel(self, user_id: str):
        """Run sentiment analysis in parallel batches for newly inserted unique records or existing unanalyzed records"""
        try:
            logger.info(f"Starting parallel batch sentiment analysis for user {user_id}")
            
            # Get the database records that need sentiment analysis
            with self.db_factory() as db:
                # If we have unique records from deduplication, filter to just those
                if hasattr(self, '_unique_records') and self._unique_records:
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
                        models.SentimentData.user_id == user_id,
                        models.SentimentData.sentiment_label.is_(None),  # Records without sentiment analysis
                        models.SentimentData.text.in_(unique_texts)  # Only the newly inserted records
                    ).all()
                else:
                    # No deduplication records, query for all unanalyzed records for this user
                    logger.info(f"No deduplication records, querying database for all unanalyzed records")
                    records_to_update = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id,
                        models.SentimentData.sentiment_label.is_(None)  # Records without sentiment analysis
                    ).limit(10000).all()  # Process up to 10k records at a time
                
                if not records_to_update:
                    logger.info(f"No newly inserted records found for sentiment analysis for user {user_id}")
                    return True
                
                logger.info(f"Found {len(records_to_update)} newly inserted records for parallel sentiment analysis")
                
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
                auto_schedule_logger.info(f"[PHASE 4: SENTIMENT] Batches: {len(batches)} | Max Workers: {self.max_sentiment_workers} | Actual Workers: {actual_sentiment_workers} | Records: {len(records_to_update)}")
                
                # Process batches in parallel
                batch_results = self._process_sentiment_batches_parallel(batches, user_id)
                
                # Count successful processing
                processed_count = sum(batch_results.values())
                
                logger.info(f"Parallel sentiment analysis completed: {processed_count}/{len(records_to_update)} records processed")
                
                return processed_count > 0
                
        except Exception as e:
            logger.error(f"Error during parallel sentiment batch update: {e}", exc_info=True)
            return False
    
    def _process_sentiment_batches_parallel(self, batches: List[List], user_id: str) -> Dict[int, int]:
        """Process sentiment analysis batches in parallel using ThreadPoolExecutor."""
        results = {}
        
        def process_single_batch(batch_data: tuple) -> int:
            """Process a single batch of records and return count of processed records."""
            batch_idx, batch = batch_data
            processed_in_batch = 0
            
            try:
                logger.info(f"Processing sentiment batch {batch_idx + 1}/{len(batches)} ({len(batch)} records)")
                
                # Create a new database session for this thread
                with self.db_factory() as db:
                    # Prepare batch data
                    records_list = []
                    texts_list = []
                    source_types_list = []
                    
                    for record in batch:
                        # CRITICAL FIX: Merge record into this thread's session
                        record = db.merge(record)
                        records_list.append(record)
                        
                        text_content = record.text or record.content or record.title or record.description
                        if text_content:
                            texts_list.append(text_content)
                            source_types_list.append(record.source_type)
                        else:
                            texts_list.append("")  # Empty text placeholder
                            source_types_list.append(record.source_type)
                    
                    if texts_list:
                        # Batch process all texts at once
                        try:
                            analysis_results = self.data_processor.batch_get_sentiment(
                                texts_list, 
                                source_types_list, 
                                max_workers=min(self.max_sentiment_workers, len(texts_list))
                            )
                            
                            # Update all records with batch results
                            for i, record in enumerate(records_list):
                                if i < len(analysis_results):
                                    try:
                                        analysis_result = analysis_results[i]
                                        
                                        # Update record with presidential sentiment analysis
                                        record.sentiment_label = analysis_result['sentiment_label']
                                        record.sentiment_score = analysis_result['sentiment_score']
                                        record.sentiment_justification = analysis_result['sentiment_justification']
                                        
                                        # Update record with governance classification (two-phase: ministry + issue)
                                        record.issue_label = analysis_result.get('issue_label')
                                        record.issue_slug = analysis_result.get('issue_slug')
                                        record.issue_confidence = analysis_result.get('issue_confidence')
                                        record.issue_keywords = json.dumps(analysis_result.get('issue_keywords', []))
                                        record.ministry_hint = analysis_result.get('ministry_hint')
                                        
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
                                        record.issue_label = analysis_result.get('issue_label')
                                        record.issue_slug = analysis_result.get('issue_slug')
                                        record.issue_confidence = analysis_result.get('issue_confidence')
                                        record.issue_keywords = json.dumps(analysis_result.get('issue_keywords', []))
                                        record.ministry_hint = analysis_result.get('ministry_hint')
                                        processed_in_batch += 1
                                except Exception as e2:
                                    logger.error(f"Error in fallback processing for record {record.entry_id}: {e2}")
                                    continue
                    
                    # Commit changes for this batch
                    db.commit()
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
                    records_needing_location = db.query(models.SentimentData).filter(
                        models.SentimentData.user_id == user_id,
                        or_(
                            models.SentimentData.location_label.is_(None),
                            models.SentimentData.location_confidence < 0.7
                        )
                    ).limit(10000).all()  # Process up to 10k records at a time
                
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
