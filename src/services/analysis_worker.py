"""
AnalysisWorker - Event-driven analysis service with queue consumer and poll fallback.

Consumes from analysis_queue (SELECT FOR UPDATE SKIP LOCKED), processes sentiment/emotion/topic
analysis, with fallback to polling sentiment_data when queue is empty.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

# Local imports
from src.api.database import SessionLocal
from src.api import models
from src.config.logging_config import get_logger

# Use dedicated logger for analysis worker (writes to logs/analysis_worker.log)
logger = get_logger('services.analysis_worker')


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key, str(default)).lower()
    return v in ('true', 'yes', 'on', '1')


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


class AnalysisWorker:
    """
    Queue-first consumer with poll fallback. Consumes from analysis_queue,
    processes sentiment/emotion/topic analysis in parallel.
    """

    def __init__(
        self,
        max_workers: int = None,
        poll_interval: float = None,
        batch_size: int = None,
        use_queue: bool = None,
        max_retries: int = None,
        poll_lookback_hours: float = None,
        use_notify: bool = None,
    ):
        """
        Initialize the AnalysisWorker. All args read from env if not provided.
        """
        self.max_workers = max_workers if max_workers is not None else _env_int('ANALYSIS_MAX_WORKERS', 25)
        self.poll_interval = poll_interval if poll_interval is not None else _env_float('ANALYSIS_POLL_INTERVAL', 2.0)
        self.batch_size = batch_size if batch_size is not None else _env_int('ANALYSIS_BATCH_SIZE', 50)
        self.use_queue = use_queue if use_queue is not None else _env_bool('ANALYSIS_USE_QUEUE', True)
        self.max_retries = max_retries if max_retries is not None else _env_int('ANALYSIS_MAX_RETRIES', 3)
        self.poll_lookback_hours = poll_lookback_hours if poll_lookback_hours is not None else _env_float('ANALYSIS_POLL_LOOKBACK_HOURS', 168.0)
        self.use_notify = use_notify if use_notify is not None else _env_bool('ANALYSIS_USE_NOTIFY', True)
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._notify_event = None  # asyncio.Event, set when NOTIFY listener started
        self._listen_thread = None
        self._listen_stop = threading.Event()
        
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
                
                date_or_run = or_(
                    models.SentimentData.date >= cutoff_time,
                    models.SentimentData.run_timestamp >= cutoff_time,
                )
                rows = db.query(
                    models.SentimentData.entry_id,
                    models.SentimentData.text,
                    models.SentimentData.content,
                    models.SentimentData.title,
                    models.SentimentData.description,
                ).filter(
                    models.SentimentData.sentiment_label.is_(None),
                    # Only process records from the last 24 hours (date or run_timestamp)
                    date_or_run
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
            
            # --- Phase 1: Short read transaction (release before heavy I/O) ---
            data = None
            with SessionLocal() as db:
                record = db.query(models.SentimentData).options(
                    joinedload(models.SentimentData.embedding)
                ).filter(models.SentimentData.entry_id == entry_id).first()
                if not record:
                    logger.warning(f"Worker [{entry_id}]: Record not found in DB, skipping")
                    return
                if record.sentiment_label is not None:
                    logger.info(f"Worker [{entry_id}]: Already analyzed (race), skipping")
                    return
                text_content = prefetched_text or record.text or record.content or record.title or record.description
                if not text_content:
                    record.processing_status = 'failed'
                    record.sentiment_label = 'neutral'
                    record.processing_completed_at = datetime.now()
                    db.commit()
                    logger.warning(f"Worker [{entry_id}]: No text content")
                    return
                # Copy to plain dict (safe for use after session close - no lazy loads)
                emb = None
                if record.embedding and hasattr(record.embedding, 'embedding') and record.embedding.embedding:
                    emb = list(record.embedding.embedding) if isinstance(record.embedding.embedding, (list, tuple)) else None
                data = {
                    'entry_id': entry_id,
                    'text_content': text_content,
                    'user_id': record.user_id,
                }
                db.commit()

            # --- Phase 2: Heavy I/O outside transaction (no session held) ---
            agent = self._get_agent()
            result = None
            sentiment_ok = False
            try:
                result = agent.sentiment_analyzer.analyze(data['text_content'])
                sentiment_label = result.get('sentiment_label')
                sentiment_score = result.get('sentiment_score')
                sentiment_justification = result.get('sentiment_justification')
                justif = (sentiment_justification or "").strip()
                if "Analysis failed" in justif or "rate limit" in justif.lower():
                    sentiment_ok = False
                    # Diagnostic: log the actual justification to detect cause (rate limit vs parse vs API error)
                    justif_preview = (justif[:200] + "…") if len(justif) > 200 else justif
                    logger.warning(
                        f"Worker [{entry_id}]: Sentiment analyzer returned failure fallback | justification={justif_preview!r}"
                    )
                elif sentiment_label and str(sentiment_label).strip():
                    sentiment_ok = True
                    if result.get('embedding'):
                        emb = list(result['embedding']) if isinstance(result['embedding'], (list, tuple)) else emb
                else:
                    sentiment_ok = False
                    justif_preview = (justif[:150] + "…") if len(justif) > 150 else (justif or "(empty)")
                    logger.warning(
                        f"Worker [{entry_id}]: Sentiment analyzer returned no valid label | label={sentiment_label!r} justification={justif_preview!r}"
                    )
            except Exception as e:
                logger.error(f"Worker [{entry_id}]: Sentiment analysis failed: {e}")
                sentiment_ok = False

            if not sentiment_ok:
                with SessionLocal() as db:
                    record = db.query(models.SentimentData).filter(
                        models.SentimentData.entry_id == entry_id
                    ).first()
                    if record:
                        record.processing_status = 'failed'
                        record.processing_completed_at = datetime.now()
                        db.commit()
                logger.warning(f"Worker [{entry_id}]: Marked failed (no valid sentiment)")
                return

            logger.info(f"Worker [{entry_id}]: Sentiment step done (label={result.get('sentiment_label')})")

            # Topic classification (still Phase 2 - no DB session)
            topic_results = []
            try:
                if hasattr(agent, 'topic_classifier') and agent.topic_classifier:
                    logger.info(f"Worker [{entry_id}]: Starting topic classification (embedding={'yes' if emb else 'no'})...")
                    try:
                        topic_results = self._run_with_timeout(
                            90.0,
                            agent.topic_classifier.classify,
                            data['text_content'],
                            emb,
                        )
                    except (FuturesTimeoutError, TimeoutError) as e:
                        logger.warning(f"Worker [{entry_id}]: Topic classification timed out after 90s: {e}")
                    logger.info(f"Worker [{entry_id}]: Topic classification returned ({len(topic_results)} topics)")
            except Exception as e:
                logger.error(f"Worker [{entry_id}]: Topic classification failed: {e}")

            current_topics = [t['topic'] for t in topic_results if t.get('topic')]

            # --- Phase 3: Short write transaction ---
            with SessionLocal() as db:
                record = db.query(models.SentimentData).options(
                    joinedload(models.SentimentData.embedding)
                ).filter(models.SentimentData.entry_id == entry_id).first()
                if not record:
                    logger.warning(f"Worker [{entry_id}]: Record vanished before write, skipping")
                    return
                if record.sentiment_label is not None:
                    logger.info(f"Worker [{entry_id}]: Already analyzed (race), skipping write")
                    return

                record.sentiment_label = result.get('sentiment_label')
                record.sentiment_score = result.get('sentiment_score')
                record.sentiment_justification = result.get('sentiment_justification')
                if result.get('emotion_label'):
                    record.emotion_label = result.get('emotion_label')
                    record.emotion_score = result.get('emotion_score')
                    record.emotion_distribution = result.get('emotion_distribution')
                if emb:
                    if record.embedding:
                        record.embedding.embedding = emb
                    else:
                        record.embedding = models.SentimentEmbedding(
                            entry_id=entry_id,
                            embedding=emb,
                        )

                if record.sentiment_label and str(record.sentiment_label).strip():
                    record.processing_status = 'completed'
                else:
                    record.processing_status = 'failed'
                record.processing_completed_at = datetime.now()

                if topic_results:
                    from src.api.models import MentionTopic
                    values = [
                        {
                            'mention_id': entry_id,
                            'topic_key': t['topic'],
                            'topic_confidence': float(t.get('confidence', 0.0)),
                            'keyword_score': float(t.get('keyword_score', 0.0)),
                            'embedding_score': float(t.get('embedding_score', 0.0)),
                        }
                        for t in topic_results
                    ]
                    stmt = pg_insert(MentionTopic).values(values).on_conflict_do_nothing(
                        index_elements=['mention_id', 'topic_key']
                    )
                    db.execute(stmt)
                    db.flush()

                if record.processing_status == 'completed':
                    try:
                        from config.config_manager import ConfigManager
                        config = ConfigManager()
                        if config.use_incremental_clustering():
                            if emb and isinstance(emb, (list, tuple)) and len(emb) == 1536:
                                all_topic_keys = [t for t in current_topics if t]
                                if all_topic_keys:
                                    cq = models.ClusterQueue(
                                        entry_id=entry_id,
                                        topic_key=all_topic_keys[0],
                                        topic_keys=all_topic_keys,
                                        user_id=record.user_id,
                                        embedding=list(emb),
                                        status='pending',
                                    )
                                    db.add(cq)
                                    logger.info(f"Worker [{entry_id}]: Enqueued 1 cluster_queue event (topics={len(all_topic_keys)})")
                    except Exception as eq:
                        logger.warning(f"Worker [{entry_id}]: Cluster enqueue failed (non-fatal): {eq}")

                db.commit()
                logger.info(f"✓ Analyzed [{entry_id}] | Sentiment: {record.sentiment_label} | Topics: {len(current_topics)}")
                
        except Exception as e:
            logger.error(f"✗ Failed [{entry_id}]: {e}", exc_info=True)
    
    def _claim_from_queue(self, limit: int) -> List[dict]:
        """
        Claim pending rows from analysis_queue using FOR UPDATE SKIP LOCKED.
        Returns list of stubs {entry_id, text_content, queue_row_id}.
        """
        stubs = []
        try:
            with SessionLocal() as db:
                AnalysisQueue = models.AnalysisQueue
                # SELECT FOR UPDATE SKIP LOCKED
                rows = db.query(AnalysisQueue.id, AnalysisQueue.entry_id).filter(
                    AnalysisQueue.status == 'pending'
                ).order_by(AnalysisQueue.created_at).limit(limit).with_for_update(skip_locked=True).all()
                if not rows:
                    return []
                row_ids = [r[0] for r in rows]
                entry_ids = [r[1] for r in rows]
                # Mark queue as processing
                db.query(AnalysisQueue).filter(AnalysisQueue.id.in_(row_ids)).update(
                    {AnalysisQueue.status: 'processing'},
                    synchronize_session=False
                )
                # Also mark sentiment_data as processing so poll path won't double-claim
                db.query(models.SentimentData).filter(
                    models.SentimentData.entry_id.in_(entry_ids)
                ).update(
                    {models.SentimentData.processing_status: 'processing'},
                    synchronize_session=False
                )
                db.commit()
                # Fetch text content for stubs
                records = db.query(
                    models.SentimentData.entry_id,
                    models.SentimentData.text,
                    models.SentimentData.content,
                    models.SentimentData.title,
                    models.SentimentData.description,
                ).filter(models.SentimentData.entry_id.in_(entry_ids)).all()
                text_by_id = {}
                for r in records:
                    text_content = r[1] or r[2] or r[3] or r[4]
                    text_by_id[r[0]] = text_content
                for (qid, eid) in zip(row_ids, entry_ids):
                    stubs.append({
                        'entry_id': eid,
                        'text_content': text_by_id.get(eid),
                        'queue_row_id': qid,
                    })
                logger.info(f"AnalysisWorker: Claimed {len(stubs)} from queue: entry_ids={entry_ids[:5]}{'...' if len(entry_ids) > 5 else ''}")
        except Exception as e:
            logger.error(f"AnalysisWorker: Error claiming from queue: {e}", exc_info=True)
        return stubs

    def _mark_queue_completed(self, queue_row_id: int) -> None:
        """Mark queue row as completed (delete to avoid table bloat)."""
        try:
            with SessionLocal() as db:
                db.query(models.AnalysisQueue).filter(
                    models.AnalysisQueue.id == queue_row_id
                ).delete(synchronize_session=False)
                db.commit()
        except Exception as e:
            logger.warning(f"AnalysisWorker: Failed to mark queue row {queue_row_id} completed: {e}")

    def _mark_queue_failed_or_retry(self, queue_row_id: int) -> None:
        """On failure: increment retry_count; if >= max_retries set failed, else pending."""
        try:
            with SessionLocal() as db:
                row = db.query(models.AnalysisQueue).filter(
                    models.AnalysisQueue.id == queue_row_id
                ).first()
                if not row:
                    return
                row.retry_count = (row.retry_count or 0) + 1
                if row.retry_count >= self.max_retries:
                    row.status = 'failed'
                    logger.warning(f"AnalysisWorker: Queue row {queue_row_id} (entry_id={row.entry_id}) failed after {row.retry_count} retries")
                else:
                    row.status = 'pending'
                    logger.info(f"AnalysisWorker: Queue row {queue_row_id} (entry_id={row.entry_id}) retry {row.retry_count}/{self.max_retries}")
                db.commit()
        except Exception as e:
            logger.warning(f"AnalysisWorker: Failed to update queue row {queue_row_id}: {e}")

    def get_metrics(self, active_tasks: int = 0) -> dict:
        """Return queue depth and worker metrics for observability."""
        metrics = {'analysis_worker_active_tasks': active_tasks}
        try:
            with SessionLocal() as db:
                from sqlalchemy import func
                pending = db.query(func.count(models.AnalysisQueue.id)).filter(
                    models.AnalysisQueue.status == 'pending'
                ).scalar() or 0
                processing = db.query(func.count(models.AnalysisQueue.id)).filter(
                    models.AnalysisQueue.status == 'processing'
                ).scalar() or 0
                failed = db.query(func.count(models.AnalysisQueue.id)).filter(
                    models.AnalysisQueue.status == 'failed'
                ).scalar() or 0
                metrics['analysis_queue_pending'] = pending
                metrics['analysis_queue_processing'] = processing
                metrics['analysis_queue_failed'] = failed
        except Exception as e:
            logger.warning(f"AnalysisWorker: Failed to get metrics: {e}")
            metrics['metrics_error'] = str(e)
        return metrics

    def _reset_stuck_queue_records(self) -> int:
        """Reset analysis_queue rows stuck in 'processing' (e.g. after crash) to 'pending'."""
        try:
            with SessionLocal() as db:
                stuck = db.query(models.AnalysisQueue).filter(
                    models.AnalysisQueue.status == 'processing'
                ).all()
                for r in stuck:
                    r.status = 'pending'
                if stuck:
                    db.commit()
                    logger.info(f"AnalysisWorker: Reset {len(stuck)} stuck queue row(s) to 'pending'")
                return len(stuck)
        except Exception as e:
            logger.error(f"AnalysisWorker: Error resetting stuck queue records: {e}")
            return 0

    def _analyze_record_with_queue_ack(self, stub: dict) -> None:
        """Wrapper: run _analyze_record, then ack queue (completed or retry/failed)."""
        queue_row_id = stub.get('queue_row_id')
        try:
            self._analyze_record(stub)
            if queue_row_id:
                self._mark_queue_completed(queue_row_id)
        except Exception as e:
            if queue_row_id:
                self._mark_queue_failed_or_retry(queue_row_id)
            raise

    def _claim_records(self, limit: int) -> List[dict]:
        """
        Fetch and 'claim' pending records from sentiment_data (poll fallback).
        Uses configurable lookback window (ANALYSIS_POLL_LOOKBACK_HOURS).
        Excludes entry_ids that are in analysis_queue (pending or processing) to avoid double-claim.
        Includes created_at in window so records with NULL/old date/run_timestamp are not missed.
        """
        claimed_records = []
        try:
            lookback = self.poll_lookback_hours
            logger.info(f"AnalysisWorker: Claiming up to {limit} pending records (lookback={lookback}h, exclude queue)...")
            with SessionLocal() as db:
                base_filter = and_(
                    or_(
                        models.SentimentData.processing_status == 'pending',
                        models.SentimentData.processing_status.is_(None),
                        models.SentimentData.processing_status == 'failed',  # Retry failed (e.g. LLM parse/rate-limit)
                    ),
                    models.SentimentData.sentiment_label.is_(None),  # Only unanalyzed
                )
                if lookback > 0:
                    cutoff_time = datetime.now() - timedelta(hours=lookback)
                    # Include date, run_timestamp, OR created_at so we don't miss records with NULL/old dates
                    date_or_run_or_created = or_(
                        models.SentimentData.date >= cutoff_time,
                        models.SentimentData.run_timestamp >= cutoff_time,
                        models.SentimentData.created_at >= cutoff_time,
                    )
                    base_filter = and_(base_filter, date_or_run_or_created)
                # Exclude entry_ids that are in analysis_queue (queue path owns them)
                queue_entry_ids = db.query(models.AnalysisQueue.entry_id).filter(
                    models.AnalysisQueue.status.in_(['pending', 'processing'])
                )
                base_filter = and_(base_filter, ~models.SentimentData.entry_id.in_(queue_entry_ids))
                # Order by date (coalesce with run_timestamp, created_at for NULLs) then entry_id
                order_date = func.coalesce(
                    models.SentimentData.date,
                    models.SentimentData.run_timestamp,
                    models.SentimentData.created_at,
                )
                subquery = db.query(models.SentimentData.entry_id).filter(
                    base_filter
                ).order_by(
                    desc(order_date),
                    desc(models.SentimentData.entry_id),
                ).limit(limit).subquery()

                # Fetch full objects for the selected IDs
                records_to_claim = db.query(models.SentimentData).filter(
                    models.SentimentData.entry_id.in_(subquery)
                ).all()

                if not records_to_claim:
                    logger.info("AnalysisWorker: No pending records in poll fallback window")
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
                cutoff = datetime.now() - timedelta(hours=max(24, self.poll_lookback_hours))
                date_or_run_or_created = or_(
                    models.SentimentData.date >= cutoff,
                    models.SentimentData.run_timestamp >= cutoff,
                    models.SentimentData.created_at >= cutoff,
                )
                stuck = db.query(models.SentimentData).filter(
                    and_(
                        models.SentimentData.processing_status == 'processing',
                        date_or_run_or_created,
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

    def _start_notify_listener(self, loop) -> None:
        """Start PG LISTEN thread if use_notify and PostgreSQL."""
        if not self.use_notify:
            return
        try:
            from src.api.database import DATABASE_URL
            if not DATABASE_URL or 'postgresql' not in DATABASE_URL.lower():
                logger.info("AnalysisWorker: NOTIFY disabled (not PostgreSQL)")
                return
            self._notify_event = asyncio.Event()

            def on_notify():
                if self._notify_event:
                    loop.call_soon_threadsafe(self._notify_event.set)

            from src.services.analysis_notify_listener import run_listen_loop
            self._listen_stop.clear()
            self._listen_thread = threading.Thread(
                target=run_listen_loop,
                args=(DATABASE_URL, on_notify, self._listen_stop),
                daemon=True,
            )
            self._listen_thread.start()
            logger.info("AnalysisWorker: NOTIFY listener started")
        except Exception as e:
            logger.warning("AnalysisWorker: Could not start NOTIFY listener: %s (polling only)", e)
            self._notify_event = None

    def _stop_notify_listener(self) -> None:
        """Stop the PG LISTEN thread."""
        self._listen_stop.set()
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=3.0)
        self._listen_thread = None
        self._notify_event = None

    async def _sleep_with_notify(self) -> None:
        """Sleep poll_interval, or wake early on NOTIFY."""
        if self._notify_event:
            self._notify_event.clear()
            try:
                await asyncio.wait_for(self._notify_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(self.poll_interval)

    async def run_forever(self):
        """Run the queue-first loop with poll fallback."""
        self._running = True
        loop = asyncio.get_running_loop()
        logger.info(
            f"AnalysisWorker: Starting (queue={self.use_queue}, workers={self.max_workers}, "
            f"lookback={self.poll_lookback_hours}h)"
        )
        # Reset stuck records from previous crash
        await asyncio.to_thread(self._reset_stuck_processing)
        await asyncio.to_thread(self._reset_stuck_queue_records)
        self._start_notify_listener(loop)
        active_futures = set()
        
        try:
            last_heartbeat = time.time()
            heartbeat_interval = 5.0  # log when at capacity every 5s so it's clear we're busy, not stuck
            last_keepalive = time.time()
            keepalive_interval = 10.0  # log every 10s so heartbeats are easy to spot in noisy logs
            
            while self._running:
                try:
                    # 0. Keep-alive + metrics: log every N seconds (grep for "KEEPALIVE" to find these)
                    now = time.time()
                    if now - last_keepalive >= keepalive_interval:
                        m = self.get_metrics(active_tasks=len(active_futures))
                        logger.info(
                            f"AnalysisWorker: *** KEEPALIVE *** Active: {len(active_futures)} | "
                            f"Queue pending: {m.get('analysis_queue_pending', '?')} | "
                            f"processing: {m.get('analysis_queue_processing', '?')} | "
                            f"failed: {m.get('analysis_queue_failed', '?')}"
                        )
                        last_keepalive = now
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

                    # 2. Check capacity (no backoff — we just wait for a slot)
                    capacity = self.max_workers - len(active_futures)
                    if capacity <= 0:
                        # Full capacity: all 25 workers busy (e.g. topic classification ~10s each). Not stuck.
                        now = time.time()
                        if now - last_heartbeat >= heartbeat_interval:
                            logger.info(f"AnalysisWorker: At capacity (Active: {len(active_futures)}), waiting for tasks to complete...")
                            last_heartbeat = now
                        await asyncio.sleep(0.1)
                        continue
                    
                    # 3. Fetch & Claim (queue-first, then poll fallback)
                    fetch_limit = min(self.batch_size, capacity)
                    new_stubs = []
                    try:
                        if self.use_queue:
                            new_stubs = await asyncio.wait_for(
                                asyncio.to_thread(self._claim_from_queue, fetch_limit),
                                timeout=30.0,
                            )
                        if not new_stubs:
                            new_stubs = await asyncio.wait_for(
                                asyncio.to_thread(self._claim_records, fetch_limit),
                                timeout=30.0,
                            )  # poll fallback for pre-queue records or when queue disabled
                    except asyncio.TimeoutError:
                        logger.warning("AnalysisWorker: Claim timed out (30s) - DB may be under load. Retrying...")
                        await asyncio.sleep(2.0)
                        continue
                    except Exception as e:
                        logger.error(f"AnalysisWorker: Fetch error: {e}", exc_info=True)
                        await asyncio.sleep(1.0)
                        continue
                    
                    if not new_stubs:
                        logger.info(f"AnalysisWorker: No work; sleeping {self.poll_interval}s (Active: {len(active_futures)})")
                        await self._sleep_with_notify()
                        continue
                    
                    # 4. Submit Tasks (use _analyze_record_with_queue_ack for queue ack on success/failure)
                    for stub in new_stubs:
                        future = loop.run_in_executor(self._executor, self._analyze_record_with_queue_ack, stub)
                        active_futures.add(future)
                    logger.info(f"AnalysisWorker: Submitted {len(new_stubs)} tasks (Active now: {len(active_futures)})")
                    last_heartbeat = time.time()
                except asyncio.CancelledError:
                    raise  # Let cancellation propagate so the task can end cleanly
                except Exception as e:
                    # Any other exception: log and keep looping (do not exit)
                    logger.error(f"AnalysisWorker: Loop error (continuing): {e}", exc_info=True)
                    await asyncio.sleep(2.0)
                    
        except asyncio.CancelledError:
            logger.info("AnalysisWorker: Task cancelled")
            raise
        except Exception as e:
            logger.error(f"AnalysisWorker: Fatal error: {e}", exc_info=True)
        finally:
            self._running = False
            self._stop_notify_listener()
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
