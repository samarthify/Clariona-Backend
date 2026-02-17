"""
LocalScheduler - Schedules and runs local collectors (YouTube, Radio, RSS, News API).

This service uses APScheduler to trigger local collector scripts on a schedule.
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

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
        
        # Collector configurations
        self.collectors = {
            'youtube': {
                'script': 'src/collectors/collect_youtube_api.py',
                'schedule': {'hour': 6, 'minute': 0},  # Run at 6 AM daily
                'enabled': True,
            },
            'radio_hybrid': {
                'script': 'src/collectors/collect_radio_hybrid.py',
                'schedule': {'hour': 7, 'minute': 0},  # Run at 7 AM daily
                'enabled': True,
            },
            'rss_nigerian_qatar_indian': {
                'script': 'src/collectors/collect_rss_nigerian_qatar_indian.py',
                'schedule': {'hour': 8, 'minute': 0},  # Run at 8 AM daily
                'enabled': True,
            },
            'news_api': {
                'script': 'src/collectors/collect_news_from_api.py',
                'schedule': {'hour': 9, 'minute': 0},  # Run at 9 AM daily
                'enabled': True,
            },
        }
        
        # Ensure collectors log directory exists
        self.collectors_log_dir = self.base_path / 'logs' / 'collectors'
        self.collectors_log_dir.mkdir(parents=True, exist_ok=True)
    
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
        
        for name, config in self.collectors.items():
            if not config['enabled']:
                continue
            
            schedule = config['schedule']
            trigger = CronTrigger(hour=schedule['hour'], minute=schedule['minute'])
            
            self._scheduler.add_job(
                self._run_collector,
                trigger=trigger,
                args=[name, config['script']],
                id=f"collector_{name}",
                name=f"Collector: {name}",
                replace_existing=True,
            )
            
            logger.info(f"Scheduled collector '{name}' at {schedule['hour']:02d}:{schedule['minute']:02d}")
        
        self._scheduler.start()
        logger.info("LocalScheduler started.")
    
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
            
            # Run as subprocess with log file redirection
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(full_path),
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
