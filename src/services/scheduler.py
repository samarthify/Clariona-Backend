"""
LocalScheduler - Schedules and runs local collectors (YouTube, Radio, RSS).

This service uses APScheduler to trigger local collector scripts on a schedule.
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


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
        }
    
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
        Run a collector script as a subprocess.
        
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
        
        try:
            # Run as subprocess
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(full_path),
                cwd=str(self.base_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if process.returncode == 0:
                logger.info(f"Collector '{name}' completed in {duration:.1f}s")
                return True
            else:
                logger.error(f"Collector '{name}' failed (exit code {process.returncode})")
                if stderr:
                    logger.error(f"stderr: {stderr.decode()[:500]}")
                return False
                
        except Exception as e:
            logger.error(f"Error running collector '{name}': {e}", exc_info=True)
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
