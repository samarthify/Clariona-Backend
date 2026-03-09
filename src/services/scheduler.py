"""
LocalScheduler - Schedules and runs local collectors (YouTube, Radio, RSS, News API).

This service uses APScheduler to trigger local collector scripts on a schedule.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Use dedicated logger for scheduler (writes to logs/scheduler.log)
logger = logging.getLogger('services.scheduler')


class LocalScheduler:
    """
    Scheduler for local collectors that run on a daily basis.
    
    Usage:
        scheduler = LocalScheduler(ingestor)
        await scheduler.start()
    """
    
    def __init__(self, ingestor=None, base_path: Optional[Path] = None):
        """
        Initialize the LocalScheduler.
        
        Args:
            ingestor: DataIngestor instance (for future direct import use).
            base_path: Base path of the project.
        """
        self.ingestor = ingestor
        self.base_path = base_path or Path(__file__).resolve().parent.parent.parent
        self._running = False
        self._scheduler = None
        
        # Load environment variables from config/.env
        env_path = self.base_path / 'config' / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from {env_path}")
        
        # Get configurable target queries from environment
        self.default_queries = self._load_default_queries()
        
        # Collector configurations - Run twice daily (AM and PM)
        self.collectors = {
            'youtube': {
                'script': 'src/collectors/collect_youtube_api.py',
                'schedule': [
                    {'hour': 6, 'minute': 0},   # 6 AM
                    {'hour': 18, 'minute': 0},  # 6 PM
                ],
                'enabled': True,
                'requires_queries': False,
            },
            'radio_hybrid': {
                'script': 'src/collectors/collect_radio_hybrid.py',
                'schedule': [
                    {'hour': 7, 'minute': 0},   # 7 AM
                    {'hour': 19, 'minute': 0},  # 7 PM
                ],
                'enabled': True,
                'requires_queries': False,
            },
            'rss_nigerian_qatar_indian': {
                'script': 'src/collectors/collect_rss_nigerian_qatar_indian.py',
                'schedule': [
                    {'hour': 8, 'minute': 0},   # 8 AM
                    {'hour': 20, 'minute': 0},  # 8 PM
                ],
                'enabled': True,
                'requires_queries': True,
                'default_queries': self.default_queries,
            },
            'news_api': {
                'script': 'src/collectors/collect_news_from_api.py',
                'schedule': [
                    {'hour': 9, 'minute': 0},   # 9 AM
                    {'hour': 21, 'minute': 0},  # 9 PM
                ],
                'enabled': True,
                'requires_queries': True,
                'default_queries': self.default_queries,
            },
        }
        
        # Ensure collectors log directory exists
        self.collectors_log_dir = self.base_path / 'logs' / 'collectors'
        self.collectors_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log retention settings
        self.log_retention_days = int(os.getenv('COLLECTOR_LOG_RETENTION_DAYS', '5'))
        logger.info(f"Collector log retention: {self.log_retention_days} days")
    
    def _load_default_queries(self) -> List[str]:
        """
        Load default queries from environment variables.
        
        Reads TARGET_INDIVIDUAL and QUERY_VARIATIONS from .env file.
        Falls back to hardcoded Tinubu queries if not set.
        
        Returns:
            List of query strings (target name + variations)
        """
        target_individual = os.getenv('TARGET_INDIVIDUAL', 'Bola Ahmed Tinubu')
        query_variations_str = os.getenv('QUERY_VARIATIONS', '[]')
        
        # Remove quotes if present
        target_individual = target_individual.strip('"').strip("'")
        
        try:
            # Parse JSON array from environment
            query_variations = json.loads(query_variations_str)
            
            # Build queries list: [target_name, variation1, variation2, ...]
            queries = [target_individual] + query_variations
            logger.info(f"Loaded default queries from environment: {queries}")
            return queries
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse QUERY_VARIATIONS JSON: {e}. Using fallback.")
            # Fallback to Tinubu queries
            return [
                "Bola Ahmed Tinubu",
                "Bola Tinubu", 
                "President Tinubu",
                "Tinubu",
                "Nigeria President",
                "Nigerian President",
                "Nigeria"
            ]
    
    async def start(self):
        """
        Start the scheduler using APScheduler (async).
        """
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.error("APScheduler not installed. Install with: pip install apscheduler")
            return
        
        self._scheduler = AsyncIOScheduler()
        self._running = True
        
        # Schedule collectors (now supports multiple schedules per collector)
        for name, config in self.collectors.items():
            if not config['enabled']:
                continue
            
            schedules = config['schedule']
            
            # Handle both single schedule (dict) and multiple schedules (list of dicts)
            if isinstance(schedules, dict):
                schedules = [schedules]
            
            # Add a job for each schedule time
            for idx, schedule in enumerate(schedules):
                trigger = CronTrigger(hour=schedule['hour'], minute=schedule['minute'])
                
                job_id = f"collector_{name}_{idx}" if len(schedules) > 1 else f"collector_{name}"
                job_name = f"Collector: {name} ({schedule['hour']:02d}:{schedule['minute']:02d})"
                
                self._scheduler.add_job(
                    self._run_collector,
                    trigger=trigger,
                    args=[name, config['script']],
                    id=job_id,
                    name=job_name,
                    replace_existing=True,
                )
                
                logger.info(f"Scheduled collector '{name}' at {schedule['hour']:02d}:{schedule['minute']:02d}")
        
        # Schedule log cleanup job (runs daily at 2 AM)
        self._scheduler.add_job(
            self._cleanup_old_logs,
            trigger=CronTrigger(hour=2, minute=0),
            id="log_cleanup",
            name="Collector Log Cleanup",
            replace_existing=True,
        )
        logger.info(f"Scheduled log cleanup at 02:00 (retention: {self.log_retention_days} days)")
        
        self._scheduler.start()
        logger.info("LocalScheduler started.")
        
        # Run initial log cleanup on startup
        await self._cleanup_old_logs()
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("LocalScheduler stopped.")
    
    async def run_collector_now(self, collector_name: str) -> bool:
        """
        Manually trigger a collector to run immediately.
        
        Args:
            collector_name: Name of the collector to run.
            
        Returns:
            True if successful, False otherwise.
        """
        if collector_name not in self.collectors:
            logger.error(f"Unknown collector: {collector_name}")
            return False
        
        config = self.collectors[collector_name]
        return await self._run_collector(collector_name, config['script'])
    
    async def _run_collector(self, name: str, script_path: str) -> bool:
        """
        Run a collector script as a subprocess with separate log files.
        
        Args:
            name: Collector name (for logging).
            script_path: Relative path to the collector script.
            
        Returns:
            True if successful, False otherwise.
        """
        full_path = self.base_path / script_path
        
        if not full_path.exists():
            logger.error(f"Collector script not found: {full_path}")
            return False
        
        logger.info(f"Running collector: {name} ({script_path})")
        start_time = datetime.now()
        
        # Create log file path with timestamp
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        log_file = self.collectors_log_dir / f"{name}_{timestamp}.log"
        
        try:
            # Open log file for writing (write mode since each run has unique timestamp)
            log_file_handle = open(log_file, 'w', encoding='utf-8')
            
            # Write header to log file
            log_file_handle.write(f"\n{'='*80}\n")
            log_file_handle.write(f"Collector: {name}\n")
            log_file_handle.write(f"Script: {script_path}\n")
            log_file_handle.write(f"Started: {start_time.isoformat()}\n")
            log_file_handle.write(f"{'='*80}\n\n")
            log_file_handle.flush()
            
            # Build command with arguments if collector requires queries
            config = self.collectors.get(name, {})
            cmd_args = [sys.executable, str(full_path)]
            
            if config.get('requires_queries') and config.get('default_queries'):
                import json
                queries_json = json.dumps(config['default_queries'])
                cmd_args.extend(['--queries', queries_json])
                logger.info(f"Running {name} with queries: {queries_json}")
            
            # Run as subprocess with log file redirection
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=str(self.base_path),
                stdout=log_file_handle,
                stderr=asyncio.subprocess.STDOUT,  # Redirect stderr to stdout
            )
            
            await process.wait()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Write footer to log file
            log_file_handle.write(f"\n{'='*80}\n")
            log_file_handle.write(f"Completed: {datetime.now().isoformat()}\n")
            log_file_handle.write(f"Duration: {duration:.1f}s\n")
            log_file_handle.write(f"Exit Code: {process.returncode}\n")
            log_file_handle.write(f"{'='*80}\n")
            log_file_handle.close()
            
            if process.returncode == 0:
                logger.info(f"Collector '{name}' completed in {duration:.1f}s (log: {log_file.name})")
                return True
            else:
                logger.error(f"Collector '{name}' failed (exit code {process.returncode}, log: {log_file.name})")
                # Read last 500 chars from log file for error summary
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if len(content) > 500:
                            logger.error(f"Last 500 chars from log: {content[-500:]}")
                        else:
                            logger.error(f"Log content: {content}")
                except Exception as read_err:
                    logger.error(f"Could not read log file: {read_err}")
                return False
                
        except Exception as e:
            logger.error(f"Error running collector '{name}': {e}", exc_info=True)
            # Try to close log file if it was opened
            try:
                if 'log_file_handle' in locals():
                    log_file_handle.close()
            except:
                pass
            return False
    
    async def _cleanup_old_logs(self):
        """
        Clean up old collector log files based on retention policy.
        Keeps only logs from the last N days (configured by log_retention_days).
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)
            deleted_count = 0
            kept_count = 0
            total_size_deleted = 0
            
            logger.info(f"Starting log cleanup (retention: {self.log_retention_days} days, cutoff: {cutoff_date.date()})")
            
            # Get all log files in the collectors directory
            if not self.collectors_log_dir.exists():
                logger.warning(f"Collectors log directory does not exist: {self.collectors_log_dir}")
                return
            
            log_files = list(self.collectors_log_dir.glob("*.log"))
            
            for log_file in log_files:
                try:
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    
                    if file_mtime < cutoff_date:
                        # File is older than retention period
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        deleted_count += 1
                        total_size_deleted += file_size
                        logger.debug(f"Deleted old log: {log_file.name} (age: {(datetime.now() - file_mtime).days} days)")
                    else:
                        kept_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing log file {log_file.name}: {e}")
            
            # Convert size to human-readable format
            if total_size_deleted > 1024 * 1024:
                size_str = f"{total_size_deleted / (1024 * 1024):.2f} MB"
            elif total_size_deleted > 1024:
                size_str = f"{total_size_deleted / 1024:.2f} KB"
            else:
                size_str = f"{total_size_deleted} bytes"
            
            logger.info(
                f"Log cleanup complete: {deleted_count} files deleted ({size_str}), "
                f"{kept_count} files kept"
            )
            
        except Exception as e:
            logger.error(f"Error during log cleanup: {e}", exc_info=True)
    
    def get_next_run_times(self) -> Dict[str, Any]:
        """
        Get next scheduled run times for all collectors.
        
        Returns:
            Dict mapping collector name to next run time.
        """
        result = {}
        
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                result[job.id] = {
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                }
        
        return result
