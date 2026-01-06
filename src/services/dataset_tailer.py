"""
DatasetTailerService - Tails Apify runs and streams data into the database.

This service monitors Apify for active runs and streams their dataset items
into the database in real-time using the DataIngestor.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, Set

from apify_client import ApifyClientAsync
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'collectors', '.env'))

logger = logging.getLogger(__name__)


class DatasetTailerService:
    """
    Service that monitors Apify for active runs and tails their datasets.
    
    Usage:
        tailer = DatasetTailerService(ingestor)
        await tailer.run_forever()
    """
    
    def __init__(self, ingestor, poll_interval: float = 5.0):
        """
        Initialize the DatasetTailerService.
        
        Args:
            ingestor: DataIngestor instance for inserting records.
            poll_interval: Seconds between polling for new runs.
        """
        self.ingestor = ingestor
        self.poll_interval = poll_interval
        self.client = ApifyClientAsync(os.getenv('APIFY_API_TOKEN'))
        
        # Track active runs: run_id -> asyncio.Task
        self.watching_runs: Dict[str, asyncio.Task] = {}
        
        # Track processed run IDs to avoid re-processing
        self.processed_run_ids: Set[str] = set()
        
        # Filter to specific actor IDs (set via config or hardcode)
        self.allowed_actor_ids: Optional[Set[str]] = None  # None = all actors
        
        self._running = False
    
    async def run_forever(self):
        """
        Main loop: discover and tail active Apify runs.
        """
        logger.info("DatasetTailerService starting...")
        self._running = True
        
        while self._running:
            try:
                await self._discover_and_tail_runs()
                await self._cleanup_finished_tasks()
            except Exception as e:
                logger.error(f"Error in tailer main loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval)
    
    async def stop(self):
        """Gracefully stop the service."""
        logger.info("DatasetTailerService stopping...")
        self._running = False
        
        # Cancel all running tasks
        for run_id, task in self.watching_runs.items():
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete
        if self.watching_runs:
            await asyncio.gather(*self.watching_runs.values(), return_exceptions=True)
    
    async def _discover_and_tail_runs(self):
        """
        Poll Apify for RUNNING runs and start tailing new ones.
        """
        try:
            # Get list of currently running runs
            runs_client = self.client.runs()
            runs_list = await runs_client.list(status='RUNNING', limit=50)
            
            for run in runs_list.items:
                run_id = run['id']
                actor_id = run.get('actId')
                
                # Skip if already watching
                if run_id in self.watching_runs:
                    continue
                
                # Skip if already processed
                if run_id in self.processed_run_ids:
                    continue
                
                # Skip if not in allowed actors (if filter is set)
                if self.allowed_actor_ids and actor_id not in self.allowed_actor_ids:
                    continue
                
                # Start tailing this run
                logger.info(f"Discovered new run: {run_id} (Actor: {actor_id})")
                task = asyncio.create_task(self._tail_run(run))
                self.watching_runs[run_id] = task
        
        except Exception as e:
            logger.error(f"Error discovering runs: {e}", exc_info=True)
    
    async def _tail_run(self, run: Dict[str, Any]):
        """
        Tail a single run's dataset until it completes.
        
        Args:
            run: Run info dictionary from Apify.
        """
        run_id = run['id']
        dataset_id = run['defaultDatasetId']
        
        logger.info(f"Starting to tail run {run_id}, dataset {dataset_id}")
        
        offset = 0
        limit = 100
        is_running = True
        
        try:
            while is_running:
                # Check run status
                run_client = self.client.run(run_id)
                run_info = await run_client.get()
                status = run_info.get('status', 'UNKNOWN')
                
                if status in ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT']:
                    is_running = False
                    logger.info(f"Run {run_id} finished with status: {status}")
                
                # Fetch new items
                dataset_client = self.client.dataset(dataset_id)
                result = await dataset_client.list_items(offset=offset, limit=limit)
                items = result.items
                
                if items:
                    logger.info(f"Run {run_id}: Received {len(items)} new items (offset={offset})")
                    
                    # Insert items via ingestor
                    for item in items:
                        self.ingestor.insert_record(item, commit=False)
                    
                    # Commit batch
                    self.ingestor.session.commit()
                    
                    offset += len(items)
                else:
                    # No new items, wait before next poll
                    if is_running:
                        await asyncio.sleep(self.poll_interval)
            
            # Final fetch to ensure we didn't miss anything
            result = await dataset_client.list_items(offset=offset, limit=1000)
            if result.items:
                logger.info(f"Run {run_id}: Final catch-up, {len(result.items)} items")
                for item in result.items:
                    self.ingestor.insert_record(item, commit=False)
                self.ingestor.session.commit()
            
            logger.info(f"Run {run_id}: Completed tailing. Total items: {offset + len(result.items)}")
            self.processed_run_ids.add(run_id)
            
        except asyncio.CancelledError:
            logger.info(f"Tailing task for run {run_id} was cancelled.")
        except Exception as e:
            logger.error(f"Error tailing run {run_id}: {e}", exc_info=True)
    
    async def _cleanup_finished_tasks(self):
        """
        Remove completed tasks from the watching_runs dict.
        """
        finished_runs = [run_id for run_id, task in self.watching_runs.items() if task.done()]
        
        for run_id in finished_runs:
            task = self.watching_runs.pop(run_id)
            try:
                # Check for exceptions
                exc = task.exception()
                if exc:
                    logger.warning(f"Task for run {run_id} had exception: {exc}")
            except asyncio.InvalidStateError:
                pass  # Task was cancelled
