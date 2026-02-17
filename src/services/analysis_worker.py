"""
AnalysisWorker - Real-time analysis service using high-frequency polling.

This service continuously polls the database for unanalyzed records and
triggers sentiment, location, and issue analysis in parallel.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List
from sqlalchemy import and_, desc, func

# Local imports
from src.api.database import SessionLocal
from src.api import models
from src.config.logging_config import get_logger

# Use dedicated logger for analysis worker (writes to logs/analysis_worker.log)
logger = get_logger('services.analysis_worker')


class AnalysisWorker:
    """
    Polls for records needing analysis and processes them in parallel.
    
    Robustness:
    - Automatically picks up any unanalyzed record (self-healing).
    - No complex queue or connection state to manage.
    """
    
    def __init__(self, max_workers: int = 25, poll_interval: float = 2.0, batch_size: int = 50):
        """
        Initialize the AnalysisWorker.
        
        Args:
            max_workers: Maximum concurrent analysis tasks.
            poll_interval: Seconds to wait when no records are found.
            batch_size: Number of records to fetch per poll cycle.
        """
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Lazy-load the agent to avoid circular imports
        self._agent = None
        self._agent_lock = threading.Lock()
        
        # Issue Cache (Optimization)
        self._issue_cache = {}  # {topic_key: [issue_dict]}
        self._last_cache_update = 0
        self._cache_lock = threading.Lock()
        self.CACHE_TTL = 30.0  # Seconds
    
    def _get_agent(self):
        """Lazy-load the SentimentAnalysisAgent (thread-safe)."""
        if self._agent is None:
            with self._agent_lock:
                # Check again under lock
                if self._agent is None:
                    from src.agent.core import SentimentAnalysisAgent
                    self._agent = SentimentAnalysisAgent(db_factory=SessionLocal)
        return self._agent
    
    def _get_cached_issues(self, topic_key: str) -> List[dict]:
        """
        Get active issues for a topic from cache, refreshing if needed.
        Returns a list of issue dicts (id, slug, embedding, mention_count, issue_label).
        """
        import time
        
        # Check if refresh needed
        if time.time() - self._last_cache_update > self.CACHE_TTL:
            with self._cache_lock:
                # Double-check under lock
                if time.time() - self._last_cache_update > self.CACHE_TTL:
                    self._refresh_issue_cache()
        
        return self._issue_cache.get(topic_key, [])

    def _refresh_issue_cache(self):
        """Refreshes the in-memory cache of all active issues."""
        try:
            with SessionLocal() as db:
                from src.api.models import TopicIssue
                import json
                import time
                
                # Fetch all active non-archived issues
                issues = db.query(TopicIssue).filter(
                    TopicIssue.is_active == True,
                    TopicIssue.is_archived == False
                ).all()
                
                # Rebuild cache
                new_cache = {}
                for issue in issues:
                    if issue.topic_key not in new_cache:
                        new_cache[issue.topic_key] = []
                    
                    # Store only what we need for matching
                    centroid = None
                    if issue.cluster_centroid_embedding:
                         if isinstance(issue.cluster_centroid_embedding, list):
                             centroid = issue.cluster_centroid_embedding
                         elif isinstance(issue.cluster_centroid_embedding, str):
                             centroid = json.loads(issue.cluster_centroid_embedding)
                    
                    new_cache[issue.topic_key].append({
                        'id': issue.id,
                        'slug': issue.issue_slug,
                        'label': issue.issue_label,
                        'centroid': centroid,
                        'mention_count': issue.mention_count
                    })
                
                self._issue_cache = new_cache
                self._last_cache_update = time.time()
                logger.debug(f"AnalysisWorker: Refreshed issue cache ({len(issues)} total issues)")
                
        except Exception as e:
            logger.error(f"AnalysisWorker: Failed to refresh issue cache: {e}")
    
    def _run_with_timeout(self, timeout_sec: float, func, *args, **kwargs):
        """Run a callable in a thread with a timeout; raise FuturesTimeoutError on timeout."""
        import time as _time
        from concurrent.futures import ThreadPoolExecutor
        func_name = getattr(func, '__name__', str(func))
        logger.info(f"_run_with_timeout: Starting {func_name} with timeout={timeout_sec}s")
        start = _time.time()
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout_sec)
                elapsed = _time.time() - start
                logger.info(f"_run_with_timeout: {func_name} completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = _time.time() - start
                logger.warning(f"_run_with_timeout: {func_name} failed/timed out after {elapsed:.2f}s: {e}")
                raise
    
    def _fetch_unanalyzed_records(self, limit: int) -> List[dict]:
        """
        Fetch unanalyzed records and include text fields to avoid a second query
        in the worker just to resolve content.
        """
        try:
            logger.info("AnalysisWorker: Creating database session...")
            with SessionLocal() as db:
                logger.info("AnalysisWorker: Session created, executing query...")
                # Calculate cutoff time (last 24 hours)
                cutoff_time = datetime.now() - timedelta(days=1)
                
                rows = db.query(
                    models.SentimentData.entry_id,
                    models.SentimentData.text,
                    models.SentimentData.content,
                    models.SentimentData.title,
                    models.SentimentData.description,
                ).filter(
                    models.SentimentData.sentiment_label.is_(None),
                    # Only process records from the last 24 hours
                    models.SentimentData.date >= cutoff_time
                ).order_by(
                    # Order by date
                    desc(models.SentimentData.date),
                    # Stable tiebreaker
                    desc(models.SentimentData.entry_id)
                ).limit(limit).all()
                
                logger.info(f"AnalysisWorker: Query executed, got {len(rows)} rows")
                records: List[dict] = []
                for row in rows:
                    entry_id, text, content, title, description = row
                    text_content = text or content or title or description
                    records.append({
                        "entry_id": entry_id,
                        "text_content": text_content
                    })
                logger.info(f"AnalysisWorker: Prepared {len(records)} records, exiting context manager...")
            # Context manager handles session close
            logger.info("AnalysisWorker: Session auto-closed by context manager")
            logger.info(f"AnalysisWorker: About to return {len(records)} records")
            return records
        except Exception as e:
            logger.error(f"AnalysisWorker: Error fetching records: {e}", exc_info=True)
            return []
    
    def _analyze_record(self, record_stub: dict):
        """
        Analyze a single record (sentiment, location, issue).
        
        This runs in a thread pool to avoid blocking.
        """
        entry_id = None
        try:
            entry_id = record_stub.get("entry_id")
            prefetched_text = record_stub.get("text_content")
            logger.info(f"Worker: Starting analysis for entry_id={entry_id}")
            
            with SessionLocal() as db:
                record = db.query(models.SentimentData).filter(
                    models.SentimentData.entry_id == entry_id
                ).first()
                
                if not record:
                    logger.warning(f"Worker [{entry_id}]: Record not found in DB, skipping")
                    return
                
                # Double-check if already analyzed (race condition safety)
                if record.sentiment_label is not None:
                    logger.info(f"Worker [{entry_id}]: Already analyzed (race), skipping")
                    return
                
                # Get text content
                text_content = prefetched_text or record.text or record.content or record.title or record.description
                if not text_content:
                    logger.warning(f"Worker [{entry_id}]: No text content")
                    record.processing_status = 'failed'
                    record.sentiment_label = 'neutral'
                    db.commit()
                    return
                
                agent = self._get_agent()
                
                # --- Sentiment Analysis ---
                if record.sentiment_label is None:
                    try:
                        result = agent.sentiment_analyzer.analyze(text_content)
                        record.sentiment_label = result.get('sentiment_label')
                        record.sentiment_score = result.get('sentiment_score')
                        record.sentiment_justification = result.get('sentiment_justification')
                        
                        if 'embedding' in result:
                            embedding_val = result.get('embedding')
                            if record.embedding:
                                record.embedding.embedding = embedding_val
                            else:
                                # Create new embedding with explicit entry_id
                                record.embedding = models.SentimentEmbedding(
                                    entry_id=entry_id,
                                    embedding=embedding_val
                                )
                        
                        # Optimization: Extract emotion data if already provided by sentiment analyzer
                        if result.get('emotion_label'):
                            record.emotion_label = result.get('emotion_label')
                            record.emotion_score = result.get('emotion_score')
                            record.emotion_distribution = result.get('emotion_distribution')
                    except Exception as e:
                        logger.error(f"Worker [{entry_id}]: Sentiment analysis failed: {e}")
                logger.info(f"Worker [{entry_id}]: Sentiment step done (label={getattr(record, 'sentiment_label', None)})")

                # --- Emotion Analysis (Phase 2 - Disabled/Redundant) ---
                # Optimization: Phase 1 now provides emotion data 99% of the time.
                # Explicitly disabling the fallback to prevent any double-billing/latency.
                # if record.emotion_label is None:
                #     try:
                #         # First check if sentiment analysis already provided it (optimization)
                #         if record.emotion_label is None and hasattr(agent, 'emotion_analyzer') and agent.emotion_analyzer:
                #              emotion_result = agent.emotion_analyzer.analyze_emotion(text_content)
                #              record.emotion_label = emotion_result.get('emotion_label')
                #              record.emotion_score = emotion_result.get('emotion_score')
                #              record.emotion_distribution = emotion_result.get('emotion_distribution')
                #     except Exception as e:
                #         logger.error(f"AnalysisWorker: Emotion analysis failed for {entry_id}: {e}")
                # else:
                #     logger.debug(f"AnalysisWorker: Phase 2 Emotion skipped (already present) for {entry_id}")

                # --- Topic Classification & Storage ---
                current_topics = []
                try:
                    if hasattr(agent, 'topic_classifier') and agent.topic_classifier:
                        # Get embedding if available from sentiment result
                        embedding = None
                        if hasattr(record, 'embedding') and record.embedding:
                             if hasattr(record.embedding, 'embedding'):
                                 embedding = record.embedding.embedding
                        
                        logger.info(f"Worker [{entry_id}]: Starting topic classification (embedding={'yes' if embedding else 'no'})...")
                        try:
                            # Run classify with timeout so one stuck call doesn't block the queue (spaCy can be slow with many topics)
                            topic_results = self._run_with_timeout(
                                90.0,
                                agent.topic_classifier.classify,
                                text_content,
                                embedding,
                            )
                        except (FuturesTimeoutError, TimeoutError) as e:
                            logger.warning(f"Worker [{entry_id}]: Topic classification timed out after 90s, skipping topics: {e}")
                            topic_results = []
                        logger.info(f"Worker [{entry_id}]: Topic classification returned ({len(topic_results) if topic_results else 0} topics)")
                        
                        # Store topics in MentionTopic table
                        if topic_results:
                            from src.api.models import MentionTopic
                            import uuid
                            
                            new_topics = []
                            for topic in topic_results:
                                # Check if already exists
                                existing_topic = db.query(MentionTopic).filter(
                                    MentionTopic.mention_id == entry_id,
                                    MentionTopic.topic_key == topic['topic']
                                ).first()
                                
                                if not existing_topic:
                                    new_topics.append(MentionTopic(
                                        mention_id=entry_id,
                                        topic_key=topic['topic'],
                                        topic_confidence=float(topic.get('confidence', 0.0)),
                                        keyword_score=float(topic.get('keyword_score', 0.0)),
                                        embedding_score=float(topic.get('embedding_score', 0.0))
                                    ))
                                    current_topics.append(topic['topic'])
                                else:
                                    current_topics.append(topic['topic'])
                            
                            if new_topics:
                                db.add_all(new_topics)
                            db.flush()
                except Exception as e:
                     logger.error(f"Worker [{entry_id}]: Topic classification failed: {e}")
                logger.info(f"Worker [{entry_id}]: Topic classification done ({len(current_topics)} topics)")

                # Update processing status and commit
                record.processing_status = 'completed'
                record.processing_completed_at = datetime.now()
                db.commit()
                
                # Single completion log with summary
                logger.info(f"✓ Analyzed [{entry_id}] | Sentiment: {record.sentiment_label} | Topics: {len(current_topics)}")
                
        except Exception as e:
            logger.error(f"✗ Failed [{entry_id}]: {e}", exc_info=True)
    
    def _claim_records(self, limit: int) -> List[dict]:
        """
        Fetch and 'claim' pending records by setting status to 'processing'.
        Atomic-like operation to allow multiple workers/overlapping batches.
        """
        claimed_records = []
        try:
            logger.info(f"AnalysisWorker: Claiming up to {limit} pending records (24h window)...")
            with SessionLocal() as db:
                # Calculate cutoff time (last 24 hours) - same as _fetch_unanalyzed_records
                cutoff_time = datetime.now() - timedelta(days=1)
                
                # Find pending records — order by date DESC then entry_id DESC so newest
                # (and newly ingested) records are claimed first; otherwise we drain old
                # pending rows and new inserts (highest entry_id) never get picked in time.
                subquery = db.query(models.SentimentData.entry_id).filter(
                    models.SentimentData.processing_status == 'pending',
                    models.SentimentData.date >= cutoff_time
                ).order_by(
                    desc(models.SentimentData.date),
                    desc(models.SentimentData.entry_id),
                ).limit(limit).subquery()

                # Fetch full objects for the selected IDs
                records_to_claim = db.query(models.SentimentData).filter(
                    models.SentimentData.entry_id.in_(subquery)
                ).all()

                if not records_to_claim:
                    logger.info("AnalysisWorker: No pending records in 24h window")
                    return []

                # Mark as processing immediately
                claimed_ids = []
                for record in records_to_claim:
                    record.processing_status = 'processing'
                    claimed_ids.append(record.entry_id)
                    
                    # Prepare stub
                    text_content = record.text or record.content or record.title or record.description
                    claimed_records.append({
                        "entry_id": record.entry_id,
                        "text_content": text_content
                    })
                
                db.commit()
                logger.info(f"AnalysisWorker: Claimed {len(claimed_records)} records: entry_ids={claimed_ids[:5]}{'...' if len(claimed_ids) > 5 else ''}")
                return claimed_records
        except Exception as e:
            logger.error(f"AnalysisWorker: Error claiming records: {e}", exc_info=True)
            return []

    def _reset_stuck_processing(self) -> int:
        """
        Reset records stuck in 'processing' (e.g. after crash) back to 'pending'.
        Returns the number of records reset.
        """
        try:
            with SessionLocal() as db:
                stuck = db.query(models.SentimentData).filter(
                    and_(
                        models.SentimentData.processing_status == 'processing',
                        models.SentimentData.date >= datetime.now() - timedelta(days=1),
                    )
                ).all()
                for r in stuck:
                    r.processing_status = 'pending'
                if stuck:
                    db.commit()
                    logger.info(f"AnalysisWorker: Reset {len(stuck)} stuck 'processing' record(s) to 'pending' for retry.")
                return len(stuck)
        except Exception as e:
            logger.error(f"AnalysisWorker: Error resetting stuck records: {e}")
            return 0

    async def run_forever(self):
        """Run the polling loop continuously with flow control."""
        self._running = True
        logger.info(f"AnalysisWorker: Starting continuous processing loop (Max Workers: {self.max_workers})")
        # Reset any records left in 'processing' from a previous crash
        await asyncio.to_thread(self._reset_stuck_processing)
        active_futures = set()
        
        try:
            loop = asyncio.get_running_loop()
            last_heartbeat = time.time()
            heartbeat_interval = 15.0  # log heartbeat every 15s when busy
            
            while self._running:
                # 1. Clean up finished futures
                done_futures = {f for f in active_futures if f.done()}
                active_futures -= done_futures
                if done_futures:
                    logger.info(f"AnalysisWorker: {len(done_futures)} task(s) completed this cycle (Active now: {len(active_futures)})")
                # Retrieve exceptions from done futures to log errors
                for f in done_futures:
                    try:
                        f.result()  # Will raise if exception occurred
                    except Exception as e:
                        logger.error(f"AnalysisWorker: Task failed: {e}", exc_info=True)

                # 2. Check capacity
                capacity = self.max_workers - len(active_futures)
                if capacity <= 0:
                    # Full capacity, wait a bit; log heartbeat periodically
                    now = time.time()
                    if now - last_heartbeat >= heartbeat_interval:
                        logger.info(f"AnalysisWorker: At capacity (Active: {len(active_futures)}), waiting for tasks to complete...")
                        last_heartbeat = now
                    await asyncio.sleep(0.1)
                    continue
                
                # 3. Fetch & Claim (Fetch only what we can handle)
                fetch_limit = min(self.batch_size, capacity)
                
                try:
                    new_stubs = await asyncio.to_thread(self._claim_records, fetch_limit)
                except Exception as e:
                    logger.error(f"AnalysisWorker: Fetch error: {e}", exc_info=True)
                    await asyncio.sleep(1.0)
                    continue
                
                if not new_stubs:
                    # No work found, sleep longer
                    logger.debug(f"AnalysisWorker: No work; sleeping {self.poll_interval}s (Active: {len(active_futures)})")
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                # 4. Submit Tasks
                for stub in new_stubs:
                    future = loop.run_in_executor(self._executor, self._analyze_record, stub)
                    active_futures.add(future)
                logger.info(f"AnalysisWorker: Submitted {len(new_stubs)} tasks (Active now: {len(active_futures)})")
                last_heartbeat = time.time()
                    
        except Exception as e:
            logger.error(f"AnalysisWorker: Fatal error: {e}", exc_info=True)
        finally:
            self._running = False
            self._executor.shutdown(wait=False)
            logger.info("AnalysisWorker: Stopped")
    
    def stop(self):
        """Signal the worker to stop."""
        self._running = False


# For standalone testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = AnalysisWorker()
    try:
        asyncio.run(worker.run_forever())
    except KeyboardInterrupt:
        worker.stop()
