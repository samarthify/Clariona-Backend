"""
DatasetTailerService - Tails Apify runs and streams data into the database.

This service monitors Apify for active runs and streams their dataset items
into the database in real-time using the DataIngestor.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set, Deque
from collections import deque

from apify_client import ApifyClientAsync
from dotenv import load_dotenv

# Load environment variables from multiple locations
ENV_PATHS = [
    Path(__file__).resolve().parent.parent.parent / '.env',  # Project root
    Path(__file__).resolve().parent.parent.parent / 'config' / '.env',  # config/.env
    Path(__file__).resolve().parent.parent / 'config' / '.env',  # src/config/.env
    Path(__file__).resolve().parent.parent / 'collectors' / '.env',  # src/collectors/.env
]
for env_path in ENV_PATHS:
    if env_path.exists():
        load_dotenv(env_path, override=False)

# Use dedicated logger for dataset tailer (writes to logs/dataset_tailer.log)
logger = logging.getLogger('services.dataset_tailer')


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
        
        api_token = os.getenv('APIFY_API_TOKEN')
        self.client = ApifyClientAsync(api_token)
        
        # Log API token status
        if api_token:
            masked_token = f"{api_token[:8]}...{api_token[-4:]}" if len(api_token) > 12 else "***"
            logger.info(f"DatasetTailer: Apify API token configured ({masked_token})")
        else:
            logger.warning("DatasetTailer: No APIFY_API_TOKEN found - Apify tailing will not work!")
        
        # Track active runs: run_id -> asyncio.Task
        self.watching_runs: Dict[str, asyncio.Task] = {}
        
        # Track processed run IDs to avoid re-processing
        # Track processed run IDs to avoid re-processing (bounded to prevent memory leak)
        self.processed_run_ids: Deque[str] = deque(maxlen=1000)
        
        # Filter to specific actor IDs (set via config or hardcode)
        self.allowed_actor_ids: Optional[Set[str]] = None  # None = all actors
        
        self._running = False
        self._last_empty_log = 0  # For rate-limiting empty poll logs
        self._poll_count = 0  # Track polling iterations
        self._service_start_time = datetime.now()  # Only process runs that finished after service started
        self._max_run_age_hours = 0.5  # 30 minutes - don't process runs older than this
    
    async def run_forever(self):
        """
        Main loop: discover and tail active Apify runs.
        """
        logger.info("DatasetTailerService starting...")
        self._running = True
        
        while self._running:
            try:
                self._poll_count += 1
                
                # Log first poll to confirm polling is working
                if self._poll_count == 1:
                    logger.info("DatasetTailer: First poll - checking Apify for runs...")
                
                await self._discover_and_tail_runs()
                await self._cleanup_finished_tasks()
                
                # Periodic status log every 60 polls (~5 minutes at 5s interval)
                if self._poll_count % 60 == 0:
                    logger.info(f"DatasetTailer status: polls={self._poll_count}, watching={len(self.watching_runs)}, processed={len(self.processed_run_ids)}")
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
        Poll Apify for RUNNING and recently SUCCEEDED runs to catch fast-completing jobs.
        """
        try:
            runs_client = self.client.runs()
            all_runs = []
            
            # Get currently running runs with timeout
            logger.info("DatasetTailer: Querying Apify API...")
            try:
                running_list = await asyncio.wait_for(
                    runs_client.list(status='RUNNING', limit=50),
                    timeout=10.0  # Reduced to 10s for faster feedback
                )
                logger.info(f"DatasetTailer: RUNNING query returned {len(running_list.items) if running_list.items else 0} runs")
                if running_list.items:
                    all_runs.extend(running_list.items)
            except asyncio.TimeoutError:
                logger.error("DatasetTailer: ⚠️ Timeout querying Apify RUNNING runs (10s) - API may be unreachable")
                return
            except Exception as e:
                logger.error(f"DatasetTailer: Error querying RUNNING runs: {e}")
                return
            
            # Also check recently succeeded runs (catches fast jobs that completed between polls)
            try:
                succeeded_list = await asyncio.wait_for(
                    runs_client.list(status='SUCCEEDED', limit=20),
                    timeout=10.0
                )
                if succeeded_list.items:
                    # Filter to runs we haven't processed yet AND finished recently
                    from datetime import timedelta
                    from dateutil.parser import parse as parse_date
                    
                    cutoff_time = datetime.now() - timedelta(hours=self._max_run_age_hours)
                    new_succeeded = []
                    
                    for r in succeeded_list.items:
                        run_id = r['id']
                        
                        # Skip if already processed or watching
                        if run_id in self.processed_run_ids or run_id in self.watching_runs:
                            continue
                        
                        # Check if run finished recently (within max_run_age_hours)
                        finished_at = r.get('finishedAt')
                        if finished_at:
                            try:
                                if isinstance(finished_at, str):
                                    finished_time = parse_date(finished_at)
                                else:
                                    finished_time = finished_at
                                
                                # Make timezone-naive for comparison
                                if finished_time.tzinfo:
                                    finished_time = finished_time.replace(tzinfo=None)
                                
                                # Skip runs older than cutoff
                                if finished_time < cutoff_time:
                                    continue
                            except Exception:
                                pass  # If we can't parse date, include the run
                        
                        new_succeeded.append(r)
                    
                    if new_succeeded:
                        all_runs.extend(new_succeeded)
                        logger.info(f"DatasetTailer: Found {len(new_succeeded)} new SUCCEEDED run(s) (within last {int(self._max_run_age_hours * 60)}min)")
            except asyncio.TimeoutError:
                logger.warning("DatasetTailer: Timeout querying SUCCEEDED runs")
            except Exception as e:
                logger.error(f"DatasetTailer: Error querying SUCCEEDED runs: {e}")
            
            # Log status periodically even if no runs found (every 30 seconds for visibility)
            total_runs = len(all_runs)
            loop_time = asyncio.get_event_loop().time()
            should_log = not hasattr(self, '_last_status_log') or (loop_time - self._last_status_log) > 30
            
            if total_runs == 0 and should_log:
                logger.info(f"DatasetTailer: Polling Apify - no active runs found (processed={len(self.processed_run_ids)})")
                self._last_status_log = loop_time
            elif total_runs > 0:
                logger.info(f"DatasetTailer: Found {total_runs} run(s) to process")
            
            for run in all_runs:
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
            error_msg = str(e).lower()
            if 'unauthorized' in error_msg or '401' in error_msg or 'authentication' in error_msg:
                logger.error(f"Apify API authentication failed - check APIFY_API_TOKEN: {e}")
            elif 'forbidden' in error_msg or '403' in error_msg:
                logger.error(f"Apify API access denied - token may lack permissions: {e}")
            else:
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
                    
                    # Debug: Log first item structure to understand data format
                    if offset == 0 and items:
                        first_item = items[0]
                        item_keys = list(first_item.keys()) if isinstance(first_item, dict) else f"Not a dict: {type(first_item)}"
                        logger.info(f"Run {run_id}: First item keys: {item_keys}")
                        # Log URL-related fields specifically
                        if isinstance(first_item, dict):
                            url_fields = {k: str(v)[:80] for k, v in first_item.items() if 'url' in k.lower() or 'link' in k.lower()}
                            logger.info(f"Run {run_id}: URL-related fields: {url_fields}")
                            
                            # Log author/user object structure (for debugging user_handle gap)
                            author_obj = first_item.get('author')
                            user_obj = first_item.get('user')
                            if author_obj and isinstance(author_obj, dict):
                                author_keys = list(author_obj.keys())
                                author_sample = {k: str(v)[:60] for k, v in list(author_obj.items())[:10]}
                                logger.info(f"Run {run_id}: Author object keys: {author_keys}")
                                logger.debug(f"Run {run_id}: Author object sample: {author_sample}")
                            if user_obj and isinstance(user_obj, dict):
                                user_keys = list(user_obj.keys())
                                logger.debug(f"Run {run_id}: User object keys: {user_keys}")
                            
                            # Log engagement metrics from first item (for debugging gaps)
                            engagement_fields = {
                                'likeCount': first_item.get('likeCount'),
                                'likesCount': first_item.get('likesCount'),
                                'retweetCount': first_item.get('retweetCount'),
                                'replyCount': first_item.get('replyCount'),
                                'commentsCount': first_item.get('commentsCount'),
                                'viewCount': first_item.get('viewCount'),
                                'views': first_item.get('views'),
                            }
                            logger.info(f"Run {run_id}: Engagement fields (raw): {engagement_fields}")
                    
                    # Insert items via ingestor efficiently using batch upsert
                    # This reduces DB round trips from N to 1
                    try:
                        success_count = self.ingestor.insert_batch(items)
                        
                        # Log stored values for first record (to debug coverage gaps)
                        if offset == 0 and items:  # First item of first batch
                            first_item = items[0]
                            first_url = first_item.get('url') or first_item.get('link') or first_item.get('postUrl')
                            if first_url:
                                self.ingestor.log_stored_record(first_url)
                        
                        logger.info(f"Run {run_id}: Batch processed - {success_count} records")
                    except Exception as e:
                        logger.error(f"Run {run_id}: Batch insert failed: {e}")
                    
                    offset += len(items)
                else:
                    # No new items, wait before next poll
                    if is_running:
                        await asyncio.sleep(self.poll_interval)
            
            # Final fetch to ensure we didn't miss anything
            result = await dataset_client.list_items(offset=offset, limit=1000)
            if result.items:
                logger.info(f"Run {run_id}: Final catch-up, {len(result.items)} items")
                try:
                    final_success = self.ingestor.insert_batch(result.items)
                    
                    # Log stored values for first record of final batch
                    if result.items:
                        first_item = result.items[0]
                        first_url = first_item.get('url') or first_item.get('link') or first_item.get('postUrl')
                        if first_url:
                            self.ingestor.log_stored_record(first_url)
                    
                    logger.info(f"Run {run_id}: Final batch processed - {final_success} records")
                except Exception as e:
                    logger.error(f"Run {run_id}: Final batch insert failed: {e}")
            
            logger.info(f"Run {run_id}: Completed tailing. Total items: {offset + len(result.items)}")
            if run_id not in self.processed_run_ids:
                self.processed_run_ids.append(run_id)
            
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
