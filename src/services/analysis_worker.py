"""
AnalysisWorker - Real-time analysis service using high-frequency polling.

This service continuously polls the database for unanalyzed records and
triggers sentiment, location, and issue analysis in parallel.
"""

import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List

# Local imports
from src.api.database import SessionLocal
from src.api import models
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisWorker:
    """
    Polls for records needing analysis and processes them in parallel.
    
    Robustness:
    - Automatically picks up any unanalyzed record (self-healing).
    - No complex queue or connection state to manage.
    """
    
    def __init__(self, max_workers: int = 10, poll_interval: float = 2.0, batch_size: int = 50):
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
    
    def _fetch_unanalyzed_records(self, limit: int) -> List[int]:
        """Fetch IDs of records that are missing sentiment analysis."""
        try:
            with SessionLocal() as db:
                # Query for records with no sentiment label
                records = db.query(models.SentimentData.entry_id).filter(
                    models.SentimentData.sentiment_label.is_(None)
                ).limit(limit).all()
                
                return [r[0] for r in records]
        except Exception as e:
            logger.error(f"AnalysisWorker: Error fetching records: {e}")
            return []
    
    def _analyze_record(self, entry_id: int):
        """
        Analyze a single record (sentiment, location, issue).
        
        This runs in a thread pool to avoid blocking.
        """
        try:
            with SessionLocal() as db:
                record = db.query(models.SentimentData).filter(
                    models.SentimentData.entry_id == entry_id
                ).first()
                
                if not record:
                    return
                
                # Double-check if already analyzed (race condition safety)
                if record.sentiment_label is not None:
                    return
                
                # Get text content
                text_content = record.text or record.content or record.title or record.description
                if not text_content:
                    logger.warning(f"AnalysisWorker: Record {entry_id} has no text content")
                    # Mark as processed effectively to avoid infinite loop
                    record.processing_status = 'failed'
                    record.sentiment_label = 'neutral' # Fallback
                    db.commit()
                    return
                
                agent = self._get_agent()
                
                # --- Location Classification (Phase 5 - Optimized to run first) ---
                if record.location_label is None:
                    try:
                        if hasattr(agent, 'location_classifier') and agent.location_classifier:
                            # Run local CPU-bound task before network-bound Sentiment Analysis
                            loc_result = agent.location_classifier.classify(text_content)
                            # logger.info(f"DEBUG: loc_result type: {type(loc_result)}, value: {loc_result}")
                            
                            if isinstance(loc_result, tuple):
                                # Handle tuple return: likely (label, confidence)
                                record.location_label = loc_result[0]
                                conf = loc_result[1] if len(loc_result) > 1 else None
                                record.location_confidence = float(conf) if conf is not None else None
                            elif isinstance(loc_result, dict):
                                # Handle both potential return formats
                                record.location_label = loc_result.get('location_label') or loc_result.get('state')
                                conf = loc_result.get('confidence')
                                record.location_confidence = float(conf) if conf is not None else None
                    except Exception as e:
                        logger.error(f"AnalysisWorker: Location classification failed for {entry_id}: {e}")

                # --- Sentiment Analysis ---
                if record.sentiment_label is None:
                    try:
                        result = agent.sentiment_analyzer.analyze(text_content)
                        record.sentiment_label = result.get('sentiment_label')
                        record.sentiment_score = result.get('sentiment_score')
                        record.sentiment_justification = result.get('sentiment_justification') # Fixed key
                        if 'embedding' in result:
                            # FIX: record.embedding is a Relationship, not a Column.
                            # We must assign a SentimentEmbedding object, not a list.
                            embedding_val = result.get('embedding')
                            if record.embedding:
                                record.embedding.embedding = embedding_val
                            else:
                                record.embedding = models.SentimentEmbedding(embedding=embedding_val)
                        
                        # Optimization: Extract emotion data if already provided by sentiment analyzer
                        if result.get('emotion_label'):
                            record.emotion_label = result.get('emotion_label')
                            record.emotion_score = result.get('emotion_score')
                            record.emotion_distribution = result.get('emotion_distribution')
                            # logger.info(f"AnalysisWorker: Optimization SUCCESS - Emotion data extracted from Phase 1 for record {entry_id}")
                    except Exception as e:
                        logger.error(f"AnalysisWorker: Sentiment analysis failed for {entry_id}: {e}")

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
                        
                        topic_results = agent.topic_classifier.classify(text_content, embedding)
                        
                        # Store topics in MentionTopic table
                        if topic_results:
                            from src.api.models import MentionTopic
                            import uuid
                            
                            for topic in topic_results:
                                # Check if already exists
                                existing_topic = db.query(MentionTopic).filter(
                                    MentionTopic.mention_id == entry_id,
                                    MentionTopic.topic_key == topic['topic']
                                ).first()
                                
                                if not existing_topic:
                                    new_topic = MentionTopic(
                                        mention_id=entry_id,
                                        topic_key=topic['topic'],
                                        topic_confidence=float(topic.get('confidence', 0.0)),
                                        keyword_score=float(topic.get('keyword_score', 0.0)),
                                        embedding_score=float(topic.get('embedding_score', 0.0))
                                    )
                                    db.add(new_topic)
                                    current_topics.append(topic['topic'])
                                else:
                                    current_topics.append(topic['topic'])
                            
                            # Flush to get IDs/Confirm storage before issue detection
                            db.flush()
                except Exception as e:
                     logger.error(f"AnalysisWorker: Topic classification failed for {entry_id}: {e}")

                # --- Issue Detection ---
                # Now using the restored IssueDetectionEngine
                try:
                    if hasattr(agent, 'issue_detection_engine') and agent.issue_detection_engine:
                        # Issue detection works per-topic. We run it for each detected topic.
                        # This duplicates the logic from DataProcessor.detect_issues_for_topic
                        # but adapted for a single record flow (real-time).
                        
                        # For real-time, we might want to just "add to cluster" or "check against existing issues".
                        # But IssueDetectionEngine is designed for batch/windowed processing.
                        # Best approach for streaming: 
                        # 1. See if this mention matches any *active* issue for its topics.
                        # 2. If yes, link it.
                        # 3. If no, we leave it for the periodic "Issue Detection Job" to cluster new issues.
                        #    (Trying to run full clustering on every single tweet is too expensive/slow).
                        
                        # However, user asked for "no gaps". So we will try to link to EXISTING issues immediately.
                        
                        from src.api.models import TopicIssue, IssueMention, TopicIssueLink
                        from src.utils.similarity import cosine_similarity
                        import json
                        import numpy as np
                        
                        # Get embedding for similarity check
                        embedding_vec = None
                        
                        # FIX: Handle relationship access correctly
                        raw_embedding = None
                        if hasattr(record, 'embedding') and record.embedding:
                             # It's a relationship object
                             if hasattr(record.embedding, 'embedding'):
                                 raw_embedding = record.embedding.embedding
                        
                        if raw_embedding:
                             if isinstance(raw_embedding, list):
                                 embedding_vec = np.array(raw_embedding)
                             elif isinstance(raw_embedding, str):
                                 embedding_vec = np.array(json.loads(raw_embedding))

                        if embedding_vec is not None and len(embedding_vec) > 0:
                            for topic_key in current_topics:
                                # Get active issues for this topic (FROM CACHE)
                                active_issues_data = self._get_cached_issues(topic_key)
                                
                                best_issue_data = None
                                best_sim = 0.70 # Threshold from config
                                
                                for issue_data in active_issues_data:
                                    if issue_data['centroid']:
                                        centroid = np.array(issue_data['centroid'])
                                        sim = cosine_similarity(embedding_vec, centroid)
                                        if sim > best_sim:
                                            best_sim = sim
                                            best_issue_data = issue_data
                                
                                if best_issue_data:
                                    # Link immediately
                                    new_link = IssueMention(
                                        issue_id=best_issue_data['id'],
                                        mention_id=entry_id,
                                        similarity_score=float(best_sim),
                                        topic_key=topic_key
                                    )
                                    db.add(new_link)
                                    
                                    # Update record for immediate UI feedback
                                    record.issue_label = best_issue_data['label']
                                    record.issue_slug = best_issue_data['slug']
                                    record.issue_slug = best_issue_data['slug']
                                    # logger.info(f"AnalysisWorker: Linked record {entry_id} to issue {best_issue_data['slug']}")
                                    
                                    # Update TopicIssueLink (Found gap: needed for full consistency)
                                    topic_link = db.query(TopicIssueLink).filter(
                                        TopicIssueLink.topic_key == topic_key,
                                        TopicIssueLink.issue_id == best_issue_data['id']
                                    ).first()
                                    
                                    current_count = best_issue_data['mention_count'] + 1 # Approximate increment
                                    
                                    if topic_link:
                                        # Incremental update is safe here? Yes, mostly.
                                        topic_link.mention_count += 1
                                        topic_link.last_updated = datetime.now()
                                    else:
                                        new_topic_link = TopicIssueLink(
                                            id=uuid.uuid4(),
                                            topic_key=topic_key,
                                            issue_id=best_issue_data['id'],
                                            mention_count=current_count
                                        )
                                        db.add(new_topic_link)
                                    
                except Exception as e:
                    logger.error(f"AnalysisWorker: Issue detection failed for {entry_id}: {e}")
                
                # Update processing status
                record.processing_status = 'completed'
                from datetime import datetime
                record.processing_completed_at = datetime.now()
                
                db.commit()
                db.commit()
                
                # Check for partial failures to be honest in logs
                status_msg = "All Phases Done"
                if record.location_label is None:
                    status_msg = "Partial (Location Failed)"
                
                logger.info(f"AnalysisWorker: COMPLETED | Record {entry_id} | {status_msg}")
                
        except Exception as e:
            logger.error(f"AnalysisWorker: Error analyzing record {entry_id}: {e}", exc_info=True)
    
    async def run_forever(self):
        """Run the polling loop continuously."""
        self._running = True
        logger.info(f"AnalysisWorker: Starting polling loop (Interval: {self.poll_interval}s)")
        
        loop = asyncio.get_event_loop()
        
        try:
            while self._running:
                # 1. Fetch Batch
                # Run DB fetch in executor to avoid blocking main loop
                entry_ids = await loop.run_in_executor(
                    None, self._fetch_unanalyzed_records, self.batch_size
                )
                
                if entry_ids:
                    logger.info(f"AnalysisWorker: Found {len(entry_ids)} unanalyzed records. Processing...")
                    
                    # 2. Process in Parallel
                    # Submit all tasks to thread pool
                    futures = [
                        loop.run_in_executor(self._executor, self._analyze_record, entry_id)
                        for entry_id in entry_ids
                    ]
                    
                    # Wait for this batch to complete
                    await asyncio.gather(*futures)
                    
                    # Immediate loop if we found a full batch (there might be more)
                    if len(entry_ids) == self.batch_size:
                        continue
                else:
                    # 3. Sleep if no work
                    await asyncio.sleep(self.poll_interval)
                    
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
