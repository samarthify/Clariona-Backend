"""
Issue Detection Engine - Detects and manages issues from clustered mentions.

Week 4: Clustering-based issue detection and management.
"""

# Standard library imports
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
import sys
import os
from pathlib import Path

# Third-party imports
import numpy as np
import openai
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select
from sqlalchemy.sql import exists
from sqlalchemy.exc import IntegrityError

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - processing
from processing.issue_clustering_service import IssueClusteringService
from processing.issue_lifecycle_manager import IssueLifecycleManager
from processing.issue_priority_calculator import IssuePriorityCalculator
# Note: SentimentAggregationService imported locally to avoid circular imports

# Local imports - utils
from utils.similarity import cosine_similarity
from utils.multi_model_rate_limiter import get_multi_model_rate_limiter

# Local imports - database
from api.database import SessionLocal
from api.models import (
    SentimentData, SentimentEmbedding, MentionTopic,
    TopicIssue, IssueMention, TopicIssueLink,
    ProcessingCluster, ClusterMention
)

# Module-level setup
logger = get_logger(__name__)


class IssueDetectionEngine:
    """
    Detects and manages issues from clustered mentions.
    
    Process:
    1. Cluster mentions by topic
    2. Check if clusters match existing issues
    3. Create new issues from clusters (if conditions met)
    4. Update existing issues with new mentions
    5. Manage issue lifecycle and priority
    
    Week 4: Core issue detection and management logic.
    """
    
    def __init__(self,
                 similarity_threshold: Optional[float] = None,
                 min_cluster_size: Optional[int] = None,
                 time_window_hours: Optional[int] = None,
                 issue_similarity_threshold: Optional[float] = None,
                 db_session: Optional[Session] = None):
        """
        Initialize issue detection engine.
        
        Args:
            similarity_threshold: Clustering similarity threshold (0.0-1.0). 
                                 If None, loads from ConfigManager. Default: 0.75
            min_cluster_size: Minimum mentions per cluster. 
                            If None, loads from ConfigManager. Default: 3
            time_window_hours: Time window for clustering. 
                              If None, loads from ConfigManager. Default: 24
            issue_similarity_threshold: Similarity threshold for matching to existing issues. 
                                       If None, loads from ConfigManager. Default: 0.70
            db_session: Optional database session
        """
        # Load configuration from ConfigManager
        try:
            config = ConfigManager()
            self.issue_similarity_threshold = issue_similarity_threshold or config.get_float(
                'processing.issue.detection.issue_similarity_threshold', 0.70
            )
            self.promotion_enabled = config.get_bool('processing.issue.promotion.enabled', False)
            self.promotion_top_n = config.get_int('processing.issue.promotion.top_n', 5)
            self.promotion_min_density = config.get_float('processing.issue.promotion.min_density_threshold', 0.0)
            self.attach_similarity_threshold = config.get_float('processing.issue.incremental.attach_similarity_threshold', 0.70)
            self.cluster_expiry_hours = config.get_int('processing.issue.incremental.cluster_expiry_hours', 336)
            # Optional merge similarity for clusters (reuse issue threshold)
            self.cluster_merge_similarity = self.issue_similarity_threshold
            self.cluster_merge_enabled = config.get_bool('processing.issue.incremental.cluster_merge_enabled', True)
            self.cluster_merge_max_clusters = config.get_int('processing.issue.incremental.cluster_merge_max_clusters', 100)
            
            # Load enhanced issue creation thresholds
            self.min_sentiment_magnitude = config.get_float(
                'processing.issue.creation.min_sentiment_magnitude', 0.0
            )
            self.min_negative_sentiment_ratio = config.get_float(
                'processing.issue.creation.min_negative_sentiment_ratio', 0.0
            )
            self.min_volume_current_window = config.get_int(
                'processing.issue.creation.min_volume_current_window', 0
            )
            self.min_velocity_percent = config.get_float(
                'processing.issue.creation.min_velocity_percent', -100.0
            )
            self.min_source_diversity = config.get_int(
                'processing.issue.creation.min_source_diversity', 1
            )
            self.min_emotion_severity = config.get_float(
                'processing.issue.creation.min_emotion_severity', 0.0
            )
            self.require_negative_sentiment = config.get_bool(
                'processing.issue.creation.require_negative_sentiment', False
            )
            self.max_time_span_hours = config.get_int(
                'processing.issue.creation.max_time_span_hours', None
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for detection settings: {e}. Using defaults.")
            self.issue_similarity_threshold = issue_similarity_threshold or 0.70
            self.cluster_merge_enabled = True
            self.cluster_merge_max_clusters = 100
            # Default values for enhanced conditions
            self.min_sentiment_magnitude = 0.0
            self.min_negative_sentiment_ratio = 0.0
            self.min_volume_current_window = 0
            self.min_velocity_percent = -100.0
            self.min_source_diversity = 1
            self.min_emotion_severity = 0.0
            self.require_negative_sentiment = False
            self.max_time_span_hours = None
        
        self.clustering_service = IssueClusteringService(
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size,
            time_window_hours=time_window_hours,
            db_session=db_session
        )
        
        # Initialize lifecycle manager and priority calculator
        self.lifecycle_manager = IssueLifecycleManager()
        self.priority_calculator = IssuePriorityCalculator()
        
        # Initialize OpenAI client for label and summary generation
        self.openai_client = None
        try:
            config_for_llm = ConfigManager()
            self.llm_model = config_for_llm.get('processing.issue.llm_model', 'gpt-4.1-nano')
        except:
            self.llm_model = 'gpt-4.1-nano'
        
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.debug("OpenAI client initialized for issue label/summary generation")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.openai_client = None
        else:
            logger.warning("OpenAI API key not available for issue label/summary generation")
        
        self.db = db_session
        
        logger.info(
            f"IssueDetectionEngine initialized: "
            f"cluster_threshold={similarity_threshold}, "
            f"issue_threshold={issue_similarity_threshold}, "
            f"min_size={min_cluster_size}"
        )
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def detect_issues(self, topic_key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Detect issues for a specific topic.
        
        Process:
        1. Get mentions for topic (without issues)
        2. Cluster mentions
        3. Match clusters to existing issues
        4. Create new issues from unmatched clusters
        5. Update existing issues with new mentions
        
        Args:
            topic_key: Topic key to detect issues for
            limit: Optional limit on number of mentions to process
        
        Returns:
            List of created/updated issue dictionaries
        """
        session = self._get_db_session()
        
        try:
            logger.info(f"Detecting issues for topic: {topic_key}")
            
            # Maintain clusters: expire old, merge similar
            logger.debug(f"Maintaining clusters for topic: {topic_key}")
            self._expire_clusters(session, topic_key)
            if self.cluster_merge_enabled:
                self._merge_clusters(session, topic_key)
            logger.debug(f"Cluster maintenance complete for topic: {topic_key}")
            
            # Start batch processing
            BATCH_SIZE = 300  # Smaller batches: less lock time, predictable latency, better concurrency
            total_created_issues = []
            
            last_entry_id = 0  # For keyset pagination
        
            while True:
                logger.info(f"Fetching batch of unprocessed mentions for topic: {topic_key} (limit={BATCH_SIZE}, after_id={last_entry_id})")
                mentions = self._get_unprocessed_mentions(session, topic_key, limit=BATCH_SIZE, after_entry_id=last_entry_id)
                
                if not mentions:
                    logger.info(f"No more unprocessed mentions for topic: {topic_key}")
                    break
                
                # Update last_entry_id for next batch
                if mentions:
                    last_entry_id = max(m['entry_id'] for m in mentions)
                
                logger.info(f"Processing batch of {len(mentions)} unprocessed mentions for topic: {topic_key}")
                
                # Incremental attach to existing clusters (magnet) to reduce re-clustering
                logger.info(f"Attaching mentions to existing clusters for topic: {topic_key}")
                mentions = self._attach_mentions_to_clusters(session, mentions, topic_key)
                logger.info(f"After magnet attachment: {len(mentions)} mentions remaining for clustering")
                
                if not mentions:
                    logger.info(f"All mentions in batch attached to existing clusters/issues. Fetching next batch...")
                    session.commit()  # Commit attachments
                    continue
                
                # Cluster remaining mentions
                logger.debug(f"Starting clustering for {len(mentions)} mentions, topic: {topic_key}")
                clusters = self.clustering_service.cluster_mentions(mentions, topic_key)
                logger.debug(f"Clustering complete for topic: {topic_key}")
                
                if not clusters:
                    logger.info(f"No valid clusters found for current batch, continuing...")
                    continue
                
                logger.info(f"Found {len(clusters)} clusters for topic: {topic_key}")
                
                # Get existing issues for this topic
                logger.debug(f"Fetching existing issues for topic: {topic_key}")
                existing_issues = self._get_existing_issues(session, topic_key)
                
                # Process each cluster
                batch_created_issues = []
                
                logger.info(f"Processing {len(clusters)} clusters for topic: {topic_key}")
                for i, cluster in enumerate(clusters):
                    logger.debug(f"Processing cluster {i+1}/{len(clusters)} for topic: {topic_key}")
                    cluster_row = self._persist_cluster(session, cluster, topic_key)
                    if not cluster_row:
                         continue
                         
                    density_str = f"{cluster_row.density_score:.3f}" if cluster_row.density_score is not None else "None"
                    logger.info(
                        f"Persisted cluster {cluster_row.id} for topic {topic_key}: "
                        f"size={len(cluster)}, density={density_str}, "
                        f"status={cluster_row.status}"
                    )

                    # If promotion mode is on, we only persist and continue
                    if self.promotion_enabled:
                        logger.debug(f"Promotion mode: Cluster {cluster_row.id} persisted, will be promoted later")
                        continue

                    # Check if cluster matches existing issue
                    matched_issue = self._find_similar_issue(session, cluster, existing_issues, topic_key)
                    
                    if matched_issue:
                        # Update existing issue
                        logger.info(f"Updating existing issue: {matched_issue.issue_slug}")
                        self._update_issue_with_mentions(session, matched_issue, cluster, topic_key, cluster_row)
                        batch_created_issues.append({
                            'issue_id': str(matched_issue.id),
                            'issue_slug': matched_issue.issue_slug,
                            'action': 'updated',
                            'mentions_added': len(cluster)
                        })
                    else:
                        # Create new issue (if conditions met)
                        if self._check_issue_conditions(cluster):
                            new_issue = self._create_issue_from_cluster(session, cluster, topic_key, cluster_row)
                            if new_issue:
                                batch_created_issues.append({
                                    'issue_id': str(new_issue.id),
                                    'issue_slug': new_issue.issue_slug,
                                    'action': 'created',
                                    'mentions_count': len(cluster)
                                })
                                existing_issues.append(new_issue)  # Add to list for future matching
                
                # Add batch results to total
                total_created_issues.extend(batch_created_issues)
                
                # Commit batch
                session.commit()
                
                # Check if we should stop (if original limit was provided and reached)
                if limit and len(total_created_issues) >= limit:
                    logger.info(f"Reached limit of {limit} created/updated issues. Stopping...")
                    break

            created_issues = total_created_issues
            
            # If promotion mode, skip recalculation; promotion handles updates
            recalculated_count = 0
            if not self.promotion_enabled:
                # Recalculate all existing issues for this topic (even if no new mentions)
                # This ensures volume/velocity, sentiment aggregation, and metadata are up-to-date
                for existing_issue in existing_issues:
                    if existing_issue.id not in updated_issue_ids:
                        logger.debug(f"Recalculating metrics for existing issue: {existing_issue.issue_slug}")
                        self._recalculate_issue_metrics(session, existing_issue)
                        recalculated_count += 1
            
            session.commit()
            
            if self.promotion_enabled:
                logger.info(
                    f"Issue detection complete for topic {topic_key}: "
                    f"{len(clusters)} clusters persisted (promotion will run after all topics processed)"
                )
            else:
                logger.info(
                    f"Issue detection complete for topic {topic_key}: "
                    f"{len(created_issues)} issues created/updated, {recalculated_count} issues recalculated"
                )
            
            return created_issues
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error detecting issues for topic {topic_key}: {e}", exc_info=True)
            raise
        finally:
            self._close_db_session(session)
    
    def recalculate_all_issues(self, topic_key: Optional[str] = None) -> int:
        """
        Recalculate metrics for all existing issues (volume, velocity, sentiment, metadata).
        
        Useful when processing existing data to ensure all calculated fields are up-to-date.
        
        Args:
            topic_key: Optional topic key to filter by. If None, processes all topics.
            
        Returns:
            Number of issues recalculated
        """
        session = self._get_db_session()
        recalculated_count = 0
        
        try:
            # Get all existing issues
            query = session.query(TopicIssue).filter(
                TopicIssue.is_archived == False
            )
            
            if topic_key:
                query = query.filter(TopicIssue.topic_key == topic_key)
            
            issues = query.all()
            
            logger.info(f"Recalculating metrics for {len(issues)} existing issues")
            
            for issue in issues:
                try:
                    self._recalculate_issue_metrics(session, issue)
                    recalculated_count += 1
                except Exception as e:
                    logger.warning(f"Error recalculating issue {issue.id}: {e}")
                    continue
            
            session.commit()
            
            logger.info(f"Recalculated metrics for {recalculated_count} issues")
            return recalculated_count
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error recalculating all issues: {e}", exc_info=True)
            return recalculated_count
        finally:
            self._close_db_session(session)
    
    def _get_unprocessed_mentions(self, session: Session, topic_key: str, limit: Optional[int] = None, after_entry_id: int = 0) -> List[Dict[str, Any]]:
        """
        Get mentions for a topic that don't have issues yet.
        Uses NOT EXISTS (correlated) and minimal column projection for performance.
        
        Args:
            session: Database session
            topic_key: Topic key
            limit: Optional limit
            after_entry_id: Fetch mentions with entry_id > this value (keyset pagination)
        
        Returns:
            List of mention dictionaries with embeddings
        """
        # Correlated NOT EXISTS: no issue row for this entry_id, no active cluster for this entry_id
        subq_issue = select(1).select_from(IssueMention).where(
            IssueMention.mention_id == SentimentData.entry_id
        )
        no_issue = ~exists(subq_issue)
        subq_active_cluster = (
            select(1)
            .select_from(ClusterMention)
            .join(ProcessingCluster, ClusterMention.cluster_id == ProcessingCluster.id)
            .where(
                ClusterMention.mention_id == SentimentData.entry_id,
                ProcessingCluster.status == 'active',
            )
        )
        no_active_cluster = ~exists(subq_active_cluster)

        stmt = (
            select(
                SentimentData.entry_id,
                SentimentData.text,
                SentimentData.content,
                SentimentData.title,
                SentimentData.run_timestamp,
                SentimentData.created_at,
                SentimentData.sentiment_label,
                SentimentData.sentiment_score,
                SentimentData.emotion_label,
                SentimentData.source_type,
                MentionTopic.topic_confidence,
            )
            .select_from(SentimentData)
            .join(MentionTopic, SentimentData.entry_id == MentionTopic.mention_id)
            .where(
                MentionTopic.topic_key == topic_key,
                no_issue,
                no_active_cluster,
            )
        )
        if after_entry_id > 0:
            stmt = stmt.where(SentimentData.entry_id > after_entry_id)
        stmt = stmt.order_by(SentimentData.entry_id.asc())
        if limit:
            stmt = stmt.limit(limit)

        result = session.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # Batch load embeddings (entry_id, embedding only)
        entry_ids = [row[0] for row in rows]
        emb_rows = session.execute(
            select(SentimentEmbedding.entry_id, SentimentEmbedding.embedding).where(
                SentimentEmbedding.entry_id.in_(entry_ids)
            )
        ).all()
        embeddings_map = {r[0]: r[1] for r in emb_rows}

        mentions = []
        for row in rows:
            # Tuple access: 0=entry_id, 1=text, 2=content, 3=title, 4=run_timestamp, 5=created_at,
            # 6=sentiment_label, 7=sentiment_score, 8=emotion_label, 9=source_type, 10=topic_confidence
            text_val = row[1] or row[2] or row[3] or ''
            run_ts = row[4] or row[5]
            mention_dict = {
                'entry_id': row[0],
                'text': text_val,
                'run_timestamp': run_ts,
                'sentiment_label': row[6],
                'sentiment_score': row[7],
                'emotion_label': row[8],
                'source_type': row[9],
                'topic_key': topic_key,
                'topic_confidence': row[10],
            }
            embedding = embeddings_map.get(row[0])
            if embedding:
                if isinstance(embedding, str):
                    try:
                        mention_dict['embedding'] = json.loads(embedding)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode embedding for mention {row[0]}, skipping embedding")
                        mention_dict['embedding'] = None
                else:
                    mention_dict['embedding'] = embedding
            mentions.append(mention_dict)

        return mentions
    
    def _get_existing_issues(self, session: Session, topic_key: str) -> List[TopicIssue]:
        """Get existing active issues for a topic."""
        return session.query(TopicIssue).filter(
            TopicIssue.topic_key == topic_key,
            TopicIssue.is_active == True,
            TopicIssue.is_archived == False
        ).all()

    def _get_active_clusters(self, session: Session, topic_key: str) -> List[ProcessingCluster]:
        """Get active clusters for a topic."""
        return session.query(ProcessingCluster).filter(
            ProcessingCluster.topic_key == topic_key,
            ProcessingCluster.status == 'active'
        ).all()

    def _expire_clusters(self, session: Session, topic_key: str):
        """Expire clusters older than configured expiry window."""
        if not self.cluster_expiry_hours or self.cluster_expiry_hours <= 0:
            return
        cutoff = datetime.now() - timedelta(hours=self.cluster_expiry_hours)
        expired = session.query(ProcessingCluster).filter(
            ProcessingCluster.topic_key == topic_key,
            ProcessingCluster.status == 'active',
            ProcessingCluster.created_at < cutoff
        ).all()
        for c in expired:
            c.status = 'expired'
        if expired:
            logger.info(f"Expired {len(expired)} clusters for topic {topic_key} older than {self.cluster_expiry_hours}h")

    def _merge_clusters(self, session: Session, topic_key: str):
        """
        Merge highly similar active clusters (centroid similarity).
        Simple greedy merge: smaller into larger when sim >= cluster_merge_similarity.
        Optimized: Only recomputes centroid/density at the end, not during merge.
        """
        active = self._get_active_clusters(session, topic_key)
        logger.debug(f"Merge check: Found {len(active)} active clusters for topic: {topic_key}")
        if len(active) < 2:
            return

        # Limit merge checks to avoid O(n²) explosion on large datasets
        if len(active) > self.cluster_merge_max_clusters:
            logger.debug(f"Limiting merge check to {self.cluster_merge_max_clusters} largest clusters (out of {len(active)})")
            active = sorted(active, key=lambda c: c.size or 0, reverse=True)[:self.cluster_merge_max_clusters]

        # Preload centroids
        def to_vec(c):
            if c.centroid:
                return np.array(c.centroid, dtype=np.float32)
            return None

        merged_ids = set()
        merges_to_recompute = []  # Track which clusters need centroid/density recomputation
        
        for i, ci in enumerate(active):
            if ci.id in merged_ids:
                continue
            ci_vec = to_vec(ci)
            if ci_vec is None:
                continue
            for cj in active[i+1:]:
                if cj.id in merged_ids:
                    continue
                cj_vec = to_vec(cj)
                if cj_vec is None:
                    continue
                sim = cosine_similarity(ci_vec, cj_vec)
                if sim >= self.cluster_merge_similarity:
                    # merge smaller into larger (by size)
                    target, source = (ci, cj) if (ci.size or 0) >= (cj.size or 0) else (cj, ci)
                    target_size = target.size or 0
                    source_size = source.size or 0
                    
                    # Move mentions (handle duplicates: mentions already in target should be removed from source)
                    # Get all mention IDs from target cluster
                    target_mention_ids = [
                        row[0] for row in session.query(ClusterMention.mention_id).filter(
                            ClusterMention.cluster_id == target.id
                        ).all()
                    ]
                    
                    # Find duplicate mentions (in both source and target)
                    if target_mention_ids:
                        duplicate_mentions = session.query(ClusterMention.mention_id).filter(
                            ClusterMention.cluster_id == source.id,
                            ClusterMention.mention_id.in_(target_mention_ids)
                        ).all()
                        duplicate_mention_ids = [d[0] for d in duplicate_mentions]
                    else:
                        duplicate_mention_ids = []
                    
                    # Delete duplicate entries from source (they're already in target)
                    if duplicate_mention_ids:
                        session.query(ClusterMention).filter(
                            ClusterMention.cluster_id == source.id,
                            ClusterMention.mention_id.in_(duplicate_mention_ids)
                        ).delete(synchronize_session=False)
                    
                    # Update remaining mentions from source to point to target
                    mention_count = session.query(ClusterMention).filter(
                        ClusterMention.cluster_id == source.id
                    ).count()
                    if mention_count > 0:
                        session.query(ClusterMention).filter(
                            ClusterMention.cluster_id == source.id
                        ).update({ClusterMention.cluster_id: target.id})
                    
                    # Total unique mentions in merged cluster = target_size (already has duplicates) + unique mentions from source
                    # Since duplicates were already in target, we only add the non-duplicate mentions
                    unique_added = mention_count  # This is the count after deleting duplicates
                    total_size = target_size + unique_added
                    
                    # Update size immediately (cheap)
                    target.size = total_size
                    
                    # Update centroid using weighted average (fast, no DB queries needed)
                    target_vec = to_vec(target)
                    source_vec = to_vec(source)
                    if target_vec is not None and source_vec is not None and total_size > 0:
                        # Weighted average: (size_a * centroid_a + size_b * centroid_b) / (size_a + size_b)
                        new_centroid = (target_size * target_vec + source_size * source_vec) / total_size
                        target.centroid = new_centroid.tolist()
                    
                    source.status = 'merged'
                    merged_ids.add(source.id)
                    logger.info(f"Merged clusters {source.id} -> {target.id} (sim={sim:.3f}, target_size={target.size}, source_size={mention_count})")
        
        # Note: Density is not recomputed here (expensive). It will be recalculated lazily
        # when the cluster is used for promotion or matching, or can be recalculated in a background job.


    def _persist_cluster(self, session: Session, cluster: List[Dict[str, Any]], topic_key: str,
                         status: str = 'active', cluster_type: str = 'dynamic') -> Optional[ProcessingCluster]:
        """Persist a cluster for traceability and incremental updates."""
        if not cluster:
            return None
        centroid = self.clustering_service._calculate_centroid(cluster)
        centroid_json = centroid.tolist() if centroid is not None else None

        # Vectorized density calculation (much faster for large clusters)
        density_score = None
        if centroid is not None:
            embeddings = []
            for mention in cluster:
                emb = mention.get('embedding')
                if emb:
                    embeddings.append(np.array(emb, dtype=np.float32))
            
            if embeddings:
                # Vectorized cosine similarity calculation
                embeddings_matrix = np.stack(embeddings)  # Shape: (n_mentions, embedding_dim)
                centroid_vec = np.array(centroid, dtype=np.float32)
                
                # Normalize
                embeddings_norm = embeddings_matrix / np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
                centroid_norm = centroid_vec / np.linalg.norm(centroid_vec)
                
                # Compute all similarities at once
                similarities = np.dot(embeddings_norm, centroid_norm)
                similarities = np.maximum(similarities, 0.0)  # Clip to [0, 1]
                
                density_score = float(np.mean(similarities))

        cluster_row = ProcessingCluster(
            topic_key=topic_key,
            cluster_type=cluster_type,
            centroid=centroid_json,
            size=len(cluster),
            density_score=density_score,
            status=status
        )
        session.add(cluster_row)
        session.flush()  # get id

        # Batch check existing links (fixes N+1 query problem)
        mention_ids = [mention['entry_id'] for mention in cluster]
        existing_links = {
            cm.mention_id
            for cm in session.query(ClusterMention.mention_id).filter(
                ClusterMention.cluster_id == cluster_row.id,
                ClusterMention.mention_id.in_(mention_ids)
            ).all()
        }

        # Batch calculate similarities if centroid exists
        similarities_map = {}
        if centroid is not None:
            embeddings_list = []
            mention_id_list = []
            for mention in cluster:
                emb = mention.get('embedding')
                if emb:
                    embeddings_list.append(np.array(emb, dtype=np.float32))
                    mention_id_list.append(mention['entry_id'])
            
            if embeddings_list:
                # Vectorized similarity calculation
                embeddings_matrix = np.stack(embeddings_list)
                centroid_vec = np.array(centroid, dtype=np.float32)
                
                embeddings_norm = embeddings_matrix / np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
                centroid_norm = centroid_vec / np.linalg.norm(centroid_vec)
                
                similarities = np.dot(embeddings_norm, centroid_norm)
                similarities = np.maximum(similarities, 0.0)
                
                similarities_map = dict(zip(mention_id_list, similarities.tolist()))

        # Batch add cluster mentions
        cluster_mentions_to_add = []
        for mention in cluster:
            mention_id = mention['entry_id']
            
            # Skip if already linked
            if mention_id in existing_links:
                logger.debug(f"Mention {mention_id} already linked to cluster {cluster_row.id}, skipping")
                continue
            
            similarity = similarities_map.get(mention_id, 1.0)
            cluster_mentions_to_add.append(ClusterMention(
                cluster_id=cluster_row.id,
                mention_id=mention_id,
                similarity_score=float(similarity)
            ))
        
        # Bulk add all cluster mentions at once
        if cluster_mentions_to_add:
            session.bulk_save_objects(cluster_mentions_to_add)

        return cluster_row

    def _attach_mentions_to_clusters(self, session: Session, mentions: List[Dict[str, Any]],
                                     topic_key: str) -> List[Dict[str, Any]]:
        """
        Incremental magnet: try to attach mentions to active clusters AND active issues by centroid similarity.
        Returns ALL mentions for clustering (mentions can belong to multiple clusters).
        
        Note: Mentions attached via magnet are still returned for clustering, allowing them
        to be part of multiple clusters if they match different cluster patterns.
        """
        if not mentions:
            return []

        # Get active clusters
        active_clusters = self._get_active_clusters(session, topic_key)
        
        # Get active issues for direct attachment
        active_issues = self._get_existing_issues(session, topic_key)
        
        if not active_clusters and not active_issues:
            return mentions

        # Limit active clusters to avoid O(n*m) explosion
        max_clusters_to_check = 50  # Only check top 50 largest clusters
        original_count = len(active_clusters)
        if original_count > max_clusters_to_check:
            active_clusters = sorted(active_clusters, key=lambda c: c.size or 0, reverse=True)[:max_clusters_to_check]
            logger.debug(f"Limiting magnet attachment to {max_clusters_to_check} largest clusters (out of {original_count})")

        # Preload centroids as numpy arrays for vectorized operations
        cluster_centroids = []
        valid_clusters = []
        for c in active_clusters:
            if c.centroid:
                centroid = np.array(c.centroid, dtype=np.float32)
                cluster_centroids.append(centroid)
                valid_clusters.append(c)
        
        if not cluster_centroids:
            return mentions

        # Batch load existing cluster-mention links to avoid N+1 queries
        mention_ids = [m['entry_id'] for m in mentions if m.get('embedding')]
        cluster_ids = [c.id for c in valid_clusters]
        existing_links = {
            (cm.cluster_id, cm.mention_id)
            for cm in session.query(ClusterMention).filter(
                ClusterMention.cluster_id.in_(cluster_ids),
                ClusterMention.mention_id.in_(mention_ids)
            ).all()
        }
        
        # Batch load cluster->issue mappings to avoid N+1 queries
        cluster_to_issue = {}
        issue_mentions = session.query(IssueMention).filter(
            IssueMention.cluster_id.in_(cluster_ids)
        ).all()
        for im in issue_mentions:
            if im.cluster_id and im.issue_id:
                cluster_to_issue[im.cluster_id] = im.issue_id

        # Vectorized similarity calculation (much faster for large batches)
        # Stack all mention embeddings into a matrix
        mention_embeddings = []
        mention_indices = []
        for i, mention in enumerate(mentions):
            emb = mention.get('embedding')
            if emb:
                mention_embeddings.append(np.array(emb, dtype=np.float32))
                mention_indices.append(i)
        
        if not mention_embeddings:
            return mentions
        
        # Stack centroids and mention embeddings
        centroids_matrix = np.stack(cluster_centroids)  # Shape: (n_clusters, embedding_dim)
        mentions_matrix = np.stack(mention_embeddings)  # Shape: (n_mentions, embedding_dim)
        
        # Compute all similarities at once using matrix multiplication (much faster)
        # cosine_similarity = dot product of normalized vectors
        centroids_norm = centroids_matrix / np.linalg.norm(centroids_matrix, axis=1, keepdims=True)
        mentions_norm = mentions_matrix / np.linalg.norm(mentions_matrix, axis=1, keepdims=True)
        similarity_matrix = np.dot(mentions_norm, centroids_norm.T)  # Shape: (n_mentions, n_clusters)
        
        # Also attach directly to active issues (not just through clusters)
        issue_centroids = []
        valid_issues = []
        for issue in active_issues:
            issue_centroid = self._get_issue_centroid(session, issue)
            if issue_centroid is not None:
                issue_centroids.append(issue_centroid)
                valid_issues.append(issue)
        
        # Compute similarities to issues if we have any
        issue_similarity_matrix = None
        if issue_centroids and mention_embeddings:
            issue_centroids_matrix = np.stack(issue_centroids)  # Shape: (n_issues, embedding_dim)
            issue_centroids_norm = issue_centroids_matrix / np.linalg.norm(issue_centroids_matrix, axis=1, keepdims=True)
            issue_similarity_matrix = np.dot(mentions_norm, issue_centroids_norm.T)  # Shape: (n_mentions, n_issues)
        
        # Batch load existing issue-mention links
        existing_issue_links = {
            im.mention_id
            for im in session.query(IssueMention.mention_id).filter(
                IssueMention.issue_id.in_([i.id for i in valid_issues]),
                IssueMention.mention_id.in_(mention_ids)
            ).all()
        }
        
        # Batch collect all attachments (avoid individual session.add calls)
        cluster_mentions_to_add = []
        issue_mentions_to_add = []
        cluster_size_updates = {}  # Track size updates per cluster
        issue_mention_count_updates = {}  # Track mention count updates per issue
        
        # Find best cluster and issue for each mention
        for idx, mention_idx in enumerate(mention_indices):
            mention = mentions[mention_idx]
            mention_id = mention['entry_id']
            
            # Check cluster similarity
            best_cluster_sim = 0.0
            best_cluster = None
            
            if cluster_centroids:
                similarities = similarity_matrix[idx]  # Similarities to all clusters
                best_cluster_idx = np.argmax(similarities)
                best_cluster_sim = similarities[best_cluster_idx]
                best_cluster = valid_clusters[best_cluster_idx] if best_cluster_sim >= self.attach_similarity_threshold else None
            
            # Check issue similarity
            best_issue_sim = 0.0
            best_issue = None
            
            if issue_similarity_matrix is not None:
                issue_similarities = issue_similarity_matrix[idx]  # Similarities to all issues
                best_issue_idx = np.argmax(issue_similarities)
                best_issue_sim = issue_similarities[best_issue_idx]
                best_issue = valid_issues[best_issue_idx] if best_issue_sim >= self.attach_similarity_threshold else None
            
            # Attach to cluster if similarity is high enough
            if best_cluster and best_cluster_sim >= self.attach_similarity_threshold:
                # Check if already linked using preloaded set (fast lookup)
                if (best_cluster.id, mention_id) not in existing_links:
                    # Collect for batch insert
                    cluster_mentions_to_add.append(ClusterMention(
                        cluster_id=best_cluster.id,
                        mention_id=mention_id,
                        similarity_score=float(best_cluster_sim)
                    ))
                    
                    # Track cluster size updates
                    cluster_size_updates[best_cluster.id] = cluster_size_updates.get(best_cluster.id, 0) + 1
                    
                    # If cluster already promoted, link to issue too (use preloaded mapping)
                    linked_issue_id = cluster_to_issue.get(best_cluster.id)
                    if linked_issue_id:
                        issue_mentions_to_add.append(IssueMention(
                            id=uuid4(),
                            issue_id=linked_issue_id,
                            mention_id=mention_id,
                            similarity_score=float(best_cluster_sim),
                            topic_key=topic_key,
                            cluster_id=best_cluster.id
                        ))
                        issue_mention_count_updates[linked_issue_id] = issue_mention_count_updates.get(linked_issue_id, 0) + 1
            
            # Attach directly to issue if similarity is high enough (and not already linked)
            if best_issue and best_issue_sim >= self.attach_similarity_threshold:
                if mention_id not in existing_issue_links:
                    issue_mentions_to_add.append(IssueMention(
                        id=uuid4(),
                        issue_id=best_issue.id,
                        mention_id=mention_id,
                        similarity_score=float(best_issue_sim),
                        topic_key=topic_key,
                        cluster_id=None  # Direct attachment, not through cluster
                    ))
                    issue_mention_count_updates[best_issue.id] = issue_mention_count_updates.get(best_issue.id, 0) + 1
        
        # Bulk insert all cluster mentions at once (much faster)
        if cluster_mentions_to_add:
            session.bulk_save_objects(cluster_mentions_to_add)
            logger.debug(f"Bulk attached {len(cluster_mentions_to_add)} mentions to clusters")
        
        # Bulk insert all issue mentions at once
        if issue_mentions_to_add:
            session.bulk_save_objects(issue_mentions_to_add)
            logger.info(f"Bulk linked {len(issue_mentions_to_add)} mentions to issues ({len([i for i in issue_mentions_to_add if i.cluster_id is None])} direct, {len([i for i in issue_mentions_to_add if i.cluster_id is not None])} via clusters)")
        
        # Update cluster sizes in batch
        for cluster_id, size_increment in cluster_size_updates.items():
            cluster = next((c for c in valid_clusters if c.id == cluster_id), None)
            if cluster:
                cluster.size = (cluster.size or 0) + size_increment
        
        # Update issue mention counts in batch
        for issue_id, count_increment in issue_mention_count_updates.items():
            issue = next((i for i in valid_issues if i.id == issue_id), None)
            if issue:
                issue.mention_count = (issue.mention_count or 0) + count_increment
                issue.last_activity = datetime.now(timezone.utc)

        # Return ALL mentions for clustering (allows multi-cluster membership)
        return mentions
    
    def _find_similar_issue(self,
                           session: Session,
                           cluster: List[Dict[str, Any]],
                           existing_issues: List[TopicIssue],
                           topic_key: str) -> Optional[TopicIssue]:
        """
        Find existing issue that matches cluster.
        
        Args:
            session: Database session
            cluster: Cluster of mentions
            existing_issues: List of existing issues
            topic_key: Topic key
        
        Returns:
            Matching issue or None
        """
        if not cluster or not existing_issues:
            return None
        
        # Calculate cluster centroid
        cluster_centroid = self.clustering_service._calculate_centroid(cluster)
        if cluster_centroid is None:
            return None
        
        # Check similarity with each existing issue
        best_match = None
        best_similarity = 0.0
        
        for issue in existing_issues:
            # Get issue centroid (from cluster_centroid_embedding or calculate from mentions)
            issue_centroid = self._get_issue_centroid(session, issue)
            
            if issue_centroid is None:
                continue
            
            similarity = cosine_similarity(cluster_centroid, issue_centroid)
            
            if similarity >= self.issue_similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = issue
        
        if best_match:
            logger.info(f"Found matching issue: {best_match.issue_slug} (similarity: {best_similarity:.3f}, cluster_size={len(cluster)}, issue_mentions={best_match.mention_count})")
        else:
            logger.debug(f"No matching issue found for cluster (size={len(cluster)}, checked {len(existing_issues)} issues, threshold={self.issue_similarity_threshold})")
        
        return best_match

    def _get_cluster_mentions(self, session: Session, cluster_row: ProcessingCluster) -> List[Dict[str, Any]]:
        """Fetch mentions for a persisted cluster with embeddings (optimized with batch loading)."""
        cluster_mentions = session.query(ClusterMention).filter(
            ClusterMention.cluster_id == cluster_row.id
        ).all()
        if not cluster_mentions:
            return []

        mention_ids = [cm.mention_id for cm in cluster_mentions]
        mentions = session.query(SentimentData).filter(SentimentData.entry_id.in_(mention_ids)).all()

        if not mentions:
            return []

        # Batch load all embeddings at once (fixes N+1 query problem)
        embeddings_map = {
            emb.entry_id: emb.embedding
            for emb in session.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id.in_(mention_ids)
            ).all()
        }

        result = []
        for mention in mentions:
            embedding = embeddings_map.get(mention.entry_id)
            emb = None
            if embedding:
                if isinstance(embedding, str):
                    emb = json.loads(embedding)
                else:
                    emb = embedding
            result.append({
                'entry_id': mention.entry_id,
                'text': mention.text or mention.content or mention.title or '',
                'run_timestamp': mention.run_timestamp or mention.created_at,
                'sentiment_label': mention.sentiment_label,
                'sentiment_score': mention.sentiment_score,
                'emotion_label': mention.emotion_label,
                'source_type': mention.source_type,
                'topic_key': cluster_row.topic_key,
                'embedding': emb
            })
        return result

    def _cluster_growth_metrics(self, session: Session, cluster_row: ProcessingCluster) -> Dict[str, float]:
        """Compute simple growth metrics using mention timestamps."""
        from datetime import timezone
        recent_hours = 24
        now = datetime.now(timezone.utc)
        recent_start = now - timedelta(hours=recent_hours)
        prev_start = recent_start - timedelta(hours=recent_hours)

        cm_query = session.query(ClusterMention, SentimentData).join(
            SentimentData, ClusterMention.mention_id == SentimentData.entry_id
        ).filter(ClusterMention.cluster_id == cluster_row.id)

        recent = 0
        prev = 0
        for cm, sd in cm_query:
            ts = sd.run_timestamp or sd.created_at
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= recent_start:
                recent += 1
            elif ts >= prev_start:
                prev += 1

        growth_rate = 0.0
        if prev > 0:
            growth_rate = (recent - prev) / prev
        elif recent > 0:
            growth_rate = 1.0
        return {"recent": recent, "prev": prev, "growth_rate": growth_rate}

    def promote_clusters_for_topic(self, topic_key: str, top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Promote top N clusters for a topic into issues, using priority ranking.
        """
        session = self._get_db_session()
        results = []
        top_n_val = top_n or self.promotion_top_n

        try:
            clusters = session.query(ProcessingCluster).filter(
                ProcessingCluster.topic_key == topic_key,
                ProcessingCluster.status == 'active'
            ).all()

            logger.info(f"Promotion check: Found {len(clusters)} active clusters for topic: {topic_key}")
            
            if not clusters:
                logger.info(f"No active clusters to promote for topic: {topic_key}")
                return []

            # Filter by density threshold
            eligible = [
                c for c in clusters
                if c.density_score is None or c.density_score >= self.promotion_min_density
            ]
            
            logger.info(f"Promotion check: {len(eligible)}/{len(clusters)} clusters meet density threshold (min={self.promotion_min_density})")
            
            if not eligible:
                logger.info(f"No clusters meet density threshold for topic: {topic_key} (min={self.promotion_min_density})")
                return []

            def score(c: ProcessingCluster) -> float:
                size = c.size or 0
                density = c.density_score or 0.0
                growth = 0.0
                try:
                    gm = self._cluster_growth_metrics(session, c)
                    growth = gm.get("growth_rate", 0.0)
                except Exception:
                    growth = 0.0
                return float(size * max(density, 0.0001) * (1.0 + growth))

            ranked = sorted(eligible, key=score, reverse=True)[:top_n_val]
            logger.info(f"Promotion: Ranking top {len(ranked)}/{len(eligible)} clusters for topic: {topic_key} (top_n={top_n_val})")

            # Get existing issues for this topic to check for matches
            existing_issues = self._get_existing_issues(session, topic_key)
            logger.debug(f"Promotion: Found {len(existing_issues)} existing issues for topic: {topic_key}")

            # Promote top N ranked clusters that meet issue conditions
            for i, cluster_row in enumerate(ranked):
                cluster_mentions = self._get_cluster_mentions(session, cluster_row)
                if not cluster_mentions:
                    logger.warning(f"Promotion: Cluster {cluster_row.id} has no mentions, skipping")
                    continue
                
                density_str = f"{cluster_row.density_score:.3f}" if cluster_row.density_score is not None else "None"
                logger.info(f"Promotion: Checking cluster {i+1}/{len(ranked)} (id={cluster_row.id}, size={len(cluster_mentions)}, density={density_str})")
                
                # Check if cluster meets issue creation conditions
                if not self._check_issue_conditions(cluster_mentions):
                    logger.warning(f"Promotion: Cluster {cluster_row.id} (size={len(cluster_mentions)}) does not meet issue conditions, skipping")
                    continue
                
                # Check if cluster matches an existing issue
                # Only match if cluster is small relative to existing issue (to allow large distinct clusters to become new issues)
                matched_issue = None
                if len(cluster_mentions) < 100:  # Only try matching smaller clusters
                    matched_issue = self._find_similar_issue(session, cluster_mentions, existing_issues, topic_key)
                
                if matched_issue:
                    # Update existing issue instead of creating new one
                    logger.info(f"Promotion: Cluster {cluster_row.id} (size={len(cluster_mentions)}) matches existing issue {matched_issue.issue_slug}, updating...")
                    self._update_issue_with_mentions(session, matched_issue, cluster_mentions, topic_key, cluster_row)
                    cluster_row.status = 'promoted'
                    
                    # Recalculate priority and lifecycle for updated issue
                    try:
                        priority_result = self.priority_calculator.calculate_priority(matched_issue, session)
                        matched_issue.priority_score = priority_result['priority_score']
                        matched_issue.priority_band = priority_result['priority_band']
                        
                        lifecycle_state = self.lifecycle_manager.update_lifecycle(str(matched_issue.id))
                        if lifecycle_state:
                            matched_issue.state = lifecycle_state
                    except Exception as e:
                        logger.warning(f"Error updating priority/lifecycle for issue {matched_issue.id}: {e}")
                    
                    logger.info(f"Promotion: ✓ Updated issue {matched_issue.issue_slug} with cluster {cluster_row.id} ({len(cluster_mentions)} mentions)")
                    results.append({
                        'cluster_id': str(cluster_row.id),
                        'issue_id': str(matched_issue.id),
                        'issue_slug': matched_issue.issue_slug,
                        'action': 'updated',
                        'mentions_count': len(cluster_mentions)
                    })
                    # Add to existing_issues list so future clusters can match it
                    if matched_issue not in existing_issues:
                        existing_issues.append(matched_issue)
                else:
                    # Create new issue from cluster
                    issue = self._create_issue_from_cluster(session, cluster_mentions, topic_key, cluster_row)
                    if issue:
                        cluster_row.status = 'promoted'
                        logger.info(f"Promotion: ✓ Promoted cluster {cluster_row.id} -> issue {issue.issue_slug} ({len(cluster_mentions)} mentions)")
                        results.append({
                            'cluster_id': str(cluster_row.id),
                            'issue_id': str(issue.id),
                            'issue_slug': issue.issue_slug,
                            'action': 'promoted',
                            'mentions_count': len(cluster_mentions)
                        })
                        # Add to existing_issues list so future clusters can match it
                        existing_issues.append(issue)
                    else:
                        logger.warning(f"Promotion: Failed to create issue from cluster {cluster_row.id}")

            session.commit()
            
            # After promotion, check for and merge similar issues (only if we promoted something)
            if results:
                logger.debug(f"Checking for similar issues to merge for topic: {topic_key} (after promotion)")
                merged_count = self._merge_similar_issues(session, topic_key)
                if merged_count > 0:
                    logger.info(f"Merged {merged_count} pairs of similar issues for topic: {topic_key}")
                    session.commit()
            
            if results:
                logger.info(f"Promotion complete for topic {topic_key}: {len(results)} clusters promoted to issues")
            else:
                logger.info(f"Promotion complete for topic {topic_key}: No clusters were promoted (check conditions/logs above)")
            
            return results

        except Exception as e:
            session.rollback()
            logger.error(f"Error promoting clusters for topic {topic_key}: {e}", exc_info=True)
            return []
        finally:
            self._close_db_session(session)
    
    def _merge_similar_issues(self, session: Session, topic_key: str) -> int:
        """
        Merge highly similar active issues (centroid similarity).
        Merges smaller issue into larger issue when similarity >= issue_similarity_threshold.
        
        Returns:
            Number of issue pairs merged
        """
        issues = self._get_existing_issues(session, topic_key)
        if len(issues) < 2:
            return 0
        
        logger.debug(f"Issue merge check: Found {len(issues)} active issues for topic: {topic_key}")
        
        merged_ids = set()
        merge_count = 0
        
        for i, issue_i in enumerate(issues):
            if issue_i.id in merged_ids:
                continue
            
            centroid_i = self._get_issue_centroid(session, issue_i)
            if centroid_i is None:
                continue
            
            for issue_j in issues[i+1:]:
                if issue_j.id in merged_ids:
                    continue
                
                centroid_j = self._get_issue_centroid(session, issue_j)
                if centroid_j is None:
                    continue
                
                similarity = cosine_similarity(centroid_i, centroid_j)
                if similarity >= self.issue_similarity_threshold:
                    # Merge smaller into larger (by mention_count, then priority)
                    if (issue_i.mention_count or 0) >= (issue_j.mention_count or 0):
                        target, source = issue_i, issue_j
                    else:
                        target, source = issue_j, issue_i
                    
                    # If same mention count, prefer higher priority
                    if target.mention_count == source.mention_count:
                        if (source.priority_score or 0) > (target.priority_score or 0):
                            target, source = source, target
                    
                    logger.info(
                        f"Merging issues: {source.issue_slug} -> {target.issue_slug} "
                        f"(similarity={similarity:.3f}, target_mentions={target.mention_count}, source_mentions={source.mention_count})"
                    )
                    
                    # Merge source into target
                    self._merge_issue_into_target(session, target, source)
                    
                    merged_ids.add(source.id)
                    merge_count += 1
        
        return merge_count
    
    def _merge_issue_into_target(self, session: Session, target: TopicIssue, source: TopicIssue):
        """
        Merge source issue into target issue.
        
        Args:
            session: Database session
            target: Target issue (kept active)
            source: Source issue (archived after merge)
        """
        # Get all mentions from source issue
        source_mentions = session.query(IssueMention).filter(
            IssueMention.issue_id == source.id
        ).all()
        
        # Check for duplicate mentions (already in target)
        target_mention_ids = {
            row[0] for row in session.query(IssueMention.mention_id).filter(
                IssueMention.issue_id == target.id
            ).all()
        }
        
        # Move non-duplicate mentions from source to target
        moved_count = 0
        for issue_mention in source_mentions:
            if issue_mention.mention_id in target_mention_ids:
                # Duplicate - delete from source
                session.delete(issue_mention)
            else:
                # Move to target
                issue_mention.issue_id = target.id
                moved_count += 1
        
        # Update target's mention count
        target.mention_count = (target.mention_count or 0) + moved_count
        
        # Update target's centroid (weighted average)
        target_centroid = self._get_issue_centroid(session, target)
        source_centroid = self._get_issue_centroid(session, source)
        
        if target_centroid is not None and source_centroid is not None:
            target_weight = target.mention_count - moved_count  # Original count
            source_weight = moved_count
            total_weight = target_weight + source_weight
            
            if total_weight > 0:
                new_centroid = (
                    (target_centroid * target_weight + source_centroid * source_weight) / total_weight
                )
                target.cluster_centroid_embedding = new_centroid.tolist()
        
        # Update target's last_activity to most recent
        if source.last_activity and target.last_activity:
            if source.last_activity > target.last_activity:
                target.last_activity = source.last_activity
        elif source.last_activity:
            target.last_activity = source.last_activity
        
        # Update target's start_time to earliest
        if source.start_time and target.start_time:
            if source.start_time < target.start_time:
                target.start_time = source.start_time
        elif source.start_time:
            target.start_time = source.start_time
        
        # Move topic links from source to target (avoid duplicates)
        source_topic_links = session.query(TopicIssueLink).filter(
            TopicIssueLink.issue_id == source.id
        ).all()
        
        for link in source_topic_links:
            # Check if target already has link to this topic
            existing = session.query(TopicIssueLink).filter(
                TopicIssueLink.issue_id == target.id,
                TopicIssueLink.topic_key == link.topic_key
            ).first()
            
            if existing:
                # Update mention count
                existing.mention_count = (existing.mention_count or 0) + (link.mention_count or 0)
                session.delete(link)
            else:
                # Move link to target
                link.issue_id = target.id
        
        # Recalculate all metrics for target issue
        self._recalculate_issue_metrics(session, target)
        
        # Archive source issue
        source.is_active = False
        source.is_archived = True
        source.state = 'archived'
        
        logger.info(
            f"✓ Merged issue {source.issue_slug} into {target.issue_slug} "
            f"({moved_count} mentions moved, target now has {target.mention_count} mentions)"
        )
    
    def _get_issue_centroid(self, session: Session, issue: TopicIssue) -> Optional[np.ndarray]:
        """
        Get centroid embedding for an issue.
        
        Tries to get from cluster_centroid_embedding, otherwise calculates from mentions.
        
        Args:
            session: Database session
            issue: Issue object
        
        Returns:
            Centroid embedding or None
        """
        # Try to get from stored centroid
        if issue.cluster_centroid_embedding:
            if isinstance(issue.cluster_centroid_embedding, dict):
                emb = issue.cluster_centroid_embedding
            elif isinstance(issue.cluster_centroid_embedding, str):
                emb = json.loads(issue.cluster_centroid_embedding)
            else:
                emb = issue.cluster_centroid_embedding
            
            if isinstance(emb, list) and len(emb) == 1536:
                return np.array(emb, dtype=np.float32)
        
        # Calculate from issue mentions
        issue_mentions = session.query(IssueMention).filter(
            IssueMention.issue_id == issue.id
        ).limit(10).all()  # Limit for performance
        
        if not issue_mentions:
            return None
        
        embeddings = []
        for issue_mention in issue_mentions:
            embedding_record = session.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id == issue_mention.mention_id
            ).first()
            
            if embedding_record and embedding_record.embedding:
                if isinstance(embedding_record.embedding, str):
                    emb = json.loads(embedding_record.embedding)
                else:
                    emb = embedding_record.embedding
                
                if isinstance(emb, list) and len(emb) == 1536:
                    embeddings.append(np.array(emb, dtype=np.float32))
        
        if not embeddings:
            return None
        
        # Calculate centroid
        centroid = np.mean(embeddings, axis=0)
        return centroid
    
    def _check_issue_conditions(self, cluster: List[Dict[str, Any]]) -> bool:
        """
        Check if cluster meets conditions to create an issue.
        
        Enhanced conditions:
        1. Minimum cluster size (handled by clustering service)
        2. Temporal proximity (time span check)
        3. Sentiment-based conditions (magnitude, negative ratio)
        4. Volume/velocity thresholds
        5. Source diversity
        6. Emotion-based severity
        
        Args:
            cluster: Cluster of mentions
        
        Returns:
            True if all conditions met
        """
        # Condition 1: Minimum size (already filtered by clustering service)
        if len(cluster) < self.clustering_service.min_cluster_size:
            logger.debug(f"Condition check: Cluster size {len(cluster)} < min {self.clustering_service.min_cluster_size}")
            return False
        
        # Condition 2: Temporal proximity
        timestamps = [
            self.clustering_service._get_timestamp(m) 
            for m in cluster
        ]
        
        if timestamps:
            time_span = max(timestamps) - min(timestamps)
            # Use configured max_time_span_hours or default to 2x time_window_hours
            max_time_span_hours = (
                self.max_time_span_hours 
                if self.max_time_span_hours is not None 
                else (self.clustering_service.time_window_hours * 2)
            )
            max_time_span = timedelta(hours=max_time_span_hours)
            if time_span > max_time_span:
                logger.warning(f"Condition check FAILED: Cluster time span {time_span} exceeds max {max_time_span}")
                return False
        
        # Condition 3: Sentiment magnitude check
        sentiment_scores = [
            m.get('sentiment_score', 0.0) 
            for m in cluster 
            if m.get('sentiment_score') is not None
        ]
        if sentiment_scores:
            avg_sentiment_magnitude = abs(sum(sentiment_scores) / len(sentiment_scores))
            if avg_sentiment_magnitude < self.min_sentiment_magnitude:
                logger.warning(
                    f"Condition check FAILED: Sentiment magnitude {avg_sentiment_magnitude:.3f} < min {self.min_sentiment_magnitude}"
                )
                return False
        
        # Condition 4: Negative sentiment ratio (if required)
        if self.min_negative_sentiment_ratio > 0.0 or self.require_negative_sentiment:
            negative_count = sum(
                1 for m in cluster 
                if m.get('sentiment_label') == 'negative' or 
                (m.get('sentiment_score', 0.0) < 0.0)
            )
            negative_ratio = negative_count / len(cluster) if cluster else 0.0
            
            if self.require_negative_sentiment and negative_ratio == 0.0:
                logger.debug(f"No negative sentiment found, but required")
                return False
            
            if negative_ratio < self.min_negative_sentiment_ratio:
                logger.debug(
                    f"Negative sentiment ratio {negative_ratio:.3f} < min {self.min_negative_sentiment_ratio}"
                )
                return False
        
        # Condition 5: Source diversity (only check if requirement > 0)
        if self.min_source_diversity > 0:
            sources = set()
            for m in cluster:
                source = m.get('source_type') or m.get('source') or m.get('platform')
                if source:
                    sources.add(str(source))
            
            if len(sources) < self.min_source_diversity:
                logger.debug(
                    f"Source diversity {len(sources)} < min {self.min_source_diversity}"
                )
                return False
        
        # Condition 6: Emotion severity (if emotion data available)
        if self.min_emotion_severity > 0.0:
            emotion_scores = []
            for m in cluster:
                emotion_label = m.get('emotion_label')
                if emotion_label and emotion_label != 'neutral':
                    # High severity emotions: anger, fear, disgust
                    if emotion_label in ['anger', 'fear', 'disgust']:
                        emotion_scores.append(1.0)
                    # Medium severity: sadness
                    elif emotion_label == 'sadness':
                        emotion_scores.append(0.5)
                    # Low severity: trust, joy
                    else:
                        emotion_scores.append(0.2)
            
            if emotion_scores:
                avg_emotion_severity = sum(emotion_scores) / len(emotion_scores)
                if avg_emotion_severity < self.min_emotion_severity:
                    logger.debug(
                        f"Emotion severity {avg_emotion_severity:.3f} < min {self.min_emotion_severity}"
                    )
                    return False
        
        # Condition 7: Volume/velocity (calculated from cluster timestamps)
        # This is a preliminary check - full calculation happens after issue creation
        if self.min_volume_current_window > 0:
            # Count mentions in recent time window (last 24h by default)
            now = datetime.now()
            if timestamps:
                # Use timezone-aware comparison if available
                from datetime import timezone
                if timestamps[0].tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                
                recent_window = now - timedelta(hours=24)
                recent_count = sum(1 for ts in timestamps if ts >= recent_window)
                
                if recent_count < self.min_volume_current_window:
                    logger.debug(
                        f"Recent volume {recent_count} < min {self.min_volume_current_window}"
                    )
                    return False
        
        # All conditions passed
        logger.debug(f"Cluster passed all issue creation conditions ({len(cluster)} mentions)")
        return True
    
    def _create_issue_from_cluster(self,
                                   session: Session,
                                   cluster: List[Dict[str, Any]],
                                   topic_key: str,
                                   cluster_row: Optional[ProcessingCluster] = None) -> Optional[TopicIssue]:
        """
        Create new issue from cluster.
        
        Args:
            session: Database session
            cluster: Cluster of mentions
            topic_key: Topic key
        
        Returns:
            Created issue or None
        """
        if not cluster:
            return None
        
        # Check global issue limit
        from config.config_manager import ConfigManager
        config = ConfigManager()
        MAX_ACTIVE_ISSUES = config.get_int('processing.issue.promotion.max_active_issues', 30)
        current_active = session.query(TopicIssue).filter(
            TopicIssue.is_active == True
        ).count()
        
        if current_active >= MAX_ACTIVE_ISSUES:
            logger.warning(f"Cannot create new issue: at limit ({current_active}/{MAX_ACTIVE_ISSUES} active issues)")
            return None
        
        logger.info(f"Creating new issue from cluster with {len(cluster)} mentions (active issues: {current_active}/{MAX_ACTIVE_ISSUES})")
        
        # Generate issue slug, label, and summary (pass session to check for duplicates)
        issue_slug = self._generate_issue_slug(topic_key, cluster, session)
        # Generate label and summary together (single LLM call for efficiency)
        label_result = self._generate_issue_label_and_summary(cluster)
        issue_label = label_result.get('title', self._generate_issue_label(cluster))
        issue_summary = label_result.get('statement', self._generate_issue_summary(cluster))
        
        # Calculate cluster centroid
        cluster_centroid = self.clustering_service._calculate_centroid(cluster)
        centroid_json = None
        if cluster_centroid is not None:
            centroid_json = cluster_centroid.tolist()
        
        # Calculate initial metrics
        timestamps = [self.clustering_service._get_timestamp(m) for m in cluster]
        start_time = min(timestamps) if timestamps else datetime.now()
        
        # Create issue
        issue = TopicIssue(
            id=uuid4(),
            issue_slug=issue_slug,
            issue_label=issue_label,
            issue_summary=issue_summary,
            topic_key=topic_key,
            primary_topic_key=topic_key,
            state='emerging',
            start_time=start_time,
            last_activity=start_time,
            mention_count=len(cluster),
            cluster_centroid_embedding=centroid_json,
            similarity_threshold=self.clustering_service.similarity_threshold,
            is_active=True
        )
        
        try:
            session.add(issue)
            session.flush()  # Get issue.id
        except IntegrityError as e:
            # Handle duplicate slug (race condition)
            if 'uq_topic_issues_issue_slug' in str(e.orig) or 'issue_slug' in str(e.orig):
                logger.warning(f"Duplicate slug detected: {issue_slug}, generating new one")
                # Generate a new unique slug
                issue_slug = self._generate_issue_slug(topic_key, cluster, session)
                issue.issue_slug = issue_slug
                session.rollback()
                session.add(issue)
                session.flush()
            else:
                raise
        
        # Link mentions to issue FIRST (before calculating metrics)
        for mention in cluster:
            similarity = 1.0  # All mentions in cluster are similar
            if len(cluster) > 1:
                # Calculate average similarity to cluster centroid
                emb = mention.get('embedding')
                if emb and cluster_centroid is not None:
                    similarity = max(0.0, cosine_similarity(emb, cluster_centroid))
            
            issue_mention = IssueMention(
                id=uuid4(),
                issue_id=issue.id,
                mention_id=mention['entry_id'],
                similarity_score=similarity,
                topic_key=topic_key,
                cluster_id=cluster_row.id if cluster_row else None
            )
            session.add(issue_mention)
        
        # Flush to ensure mentions are saved before calculating metrics
        session.flush()
        
        # Generate issue title
        issue.issue_title = self._generate_issue_title(session, issue)
        
        # Calculate initial volume and velocity for new issue (AFTER mentions are linked)
        self._calculate_volume_and_velocity(session, issue, cluster)
        
        # Update metadata and sentiment aggregation (AFTER mentions are linked)
        self._update_issue_metadata(session, issue)
        self._update_issue_sentiment_aggregation(session, issue)
        
        # Create topic-issue links for all topics that mentions in this cluster belong to
        # Get all unique topics from mentions in the cluster
        mention_ids = [mention['entry_id'] for mention in cluster]
        mention_topics = session.query(MentionTopic.topic_key).filter(
            MentionTopic.mention_id.in_(mention_ids)
        ).distinct().all()
        
        topic_keys = {mt[0] for mt in mention_topics}
        # Always include the primary topic_key
        topic_keys.add(topic_key)
        
        # Create links for all topics
        for topic in topic_keys:
            # Check if link already exists (avoid duplicates)
            existing = session.query(TopicIssueLink).filter(
                TopicIssueLink.topic_key == topic,
                TopicIssueLink.issue_id == issue.id
            ).first()
            
            if not existing:
                topic_link = TopicIssueLink(
                    id=uuid4(),
                    topic_key=topic,
                    issue_id=issue.id,
                    mention_count=len(cluster)  # Total mentions, will be recalculated per-topic if needed
                )
                session.add(topic_link)
                logger.debug(f"Linked issue {issue.issue_slug} to topic {topic}")
        
        # Calculate initial priority and update lifecycle
        try:
            # Calculate priority
            priority_result = self.priority_calculator.calculate_priority(issue, session)
            issue.priority_score = priority_result['priority_score']
            issue.priority_band = priority_result['priority_band']
            
            # Update lifecycle state (lifecycle manager only takes issue_id string)
            lifecycle_state = self.lifecycle_manager.update_lifecycle(str(issue.id))
            if lifecycle_state:
                issue.state = lifecycle_state
            
            session.flush()  # Update issue with priority and state
        except Exception as e:
            logger.warning(f"Error calculating priority/lifecycle for new issue: {e}")
            # Continue without priority/lifecycle (will be calculated later)
        
        logger.info(f"Created issue: {issue.issue_slug} with {len(cluster)} mentions")
        
        return issue
    
    def _update_issue_with_mentions(self,
                                    session: Session,
                                    issue: TopicIssue,
                                    cluster: List[Dict[str, Any]],
                                    topic_key: str,
                                    cluster_row: Optional[ProcessingCluster] = None):
        """
        Update existing issue with new mentions from cluster.
        
        Args:
            session: Database session
            issue: Existing issue
            cluster: Cluster of new mentions
            topic_key: Topic key
        """
        logger.info(f"Updating issue {issue.issue_slug} with {len(cluster)} new mentions")
        
        # Get cluster centroid
        cluster_centroid = self.clustering_service._calculate_centroid(cluster)
        
        # Update issue centroid (weighted average with existing)
        if cluster_centroid is not None:
            existing_centroid = self._get_issue_centroid(session, issue)
            if existing_centroid is not None:
                # Weighted average: more weight to existing (larger) cluster
                existing_weight = issue.mention_count
                new_weight = len(cluster)
                total_weight = existing_weight + new_weight
                
                new_centroid = (
                    (existing_centroid * existing_weight + cluster_centroid * new_weight) / total_weight
                )
                issue.cluster_centroid_embedding = new_centroid.tolist()
            else:
                issue.cluster_centroid_embedding = cluster_centroid.tolist()
        
        # Add mentions to issue
        for mention in cluster:
            # Check if mention already linked
            existing = session.query(IssueMention).filter(
                IssueMention.issue_id == issue.id,
                IssueMention.mention_id == mention['entry_id']
            ).first()
            
            if existing:
                continue  # Already linked
            
            # Calculate similarity
            similarity = 1.0
            emb = mention.get('embedding')
            if emb and cluster_centroid is not None:
                similarity = max(0.0, cosine_similarity(emb, cluster_centroid))
            
            issue_mention = IssueMention(
                id=uuid4(),
                issue_id=issue.id,
                mention_id=mention['entry_id'],
                similarity_score=similarity,
                topic_key=topic_key,
                cluster_id=cluster_row.id if cluster_row else None
            )
            session.add(issue_mention)
        
        # Update issue metrics
        old_mention_count = issue.mention_count
        issue.mention_count += len(cluster)
        issue.last_activity = datetime.now()
        
        # Calculate volume and velocity
        self._calculate_volume_and_velocity(session, issue, cluster)
        
        # Update metadata (keywords, sources, regions)
        self._update_issue_metadata(session, issue)
        
        # Update sentiment aggregation
        self._update_issue_sentiment_aggregation(session, issue)
        
        # Regenerate label and summary if cluster has grown significantly
        # Threshold: if cluster size increased by >20% or if this is a major update (>50 new mentions)
        growth_ratio = len(cluster) / old_mention_count if old_mention_count > 0 else 1.0
        should_regenerate = (
            growth_ratio > 0.20 or  # >20% growth
            len(cluster) > 50 or    # Major update (>50 new mentions)
            not issue.issue_label or # No label yet
            not issue.issue_summary  # No summary yet
        )
        
        if should_regenerate and self.openai_client:
            try:
                # Get all mentions for this issue to regenerate label/summary
                all_mentions = self._get_all_issue_mentions(session, issue)
                if all_mentions and len(all_mentions) >= 15:  # Need at least 15 for good representation
                    logger.info(f"Regenerating label and summary for issue {issue.issue_slug} (growth={growth_ratio:.2%}, new_mentions={len(cluster)})")
                    label_result = self._generate_issue_label_and_summary(all_mentions)
                    if label_result.get('title'):
                        issue.issue_label = label_result['title']
                    if label_result.get('statement'):
                        issue.issue_summary = label_result['statement']
            except Exception as e:
                logger.warning(f"Error regenerating label/summary for issue {issue.id}: {e}")
        
        # Update issue title if not set
        if not issue.issue_title:
            issue.issue_title = self._generate_issue_title(session, issue)
        
        # Recalculate priority and update lifecycle
        try:
            # Refresh issue from database to get latest metrics
            session.refresh(issue)
            
            # Calculate priority
            priority_result = self.priority_calculator.calculate_priority(issue, session)
            issue.priority_score = priority_result['priority_score']
            issue.priority_band = priority_result['priority_band']
            
            # Update lifecycle state (lifecycle manager only takes issue_id string)
            lifecycle_state = self.lifecycle_manager.update_lifecycle(str(issue.id))
            if lifecycle_state:
                issue.state = lifecycle_state
            
            session.flush()  # Update issue with priority and state
        except Exception as e:
            logger.warning(f"Error recalculating priority/lifecycle for issue {issue.id}: {e}")
            # Continue without priority/lifecycle update
        
        # Update topic-issue link
        topic_link = session.query(TopicIssueLink).filter(
            TopicIssueLink.topic_key == topic_key,
            TopicIssueLink.issue_id == issue.id
        ).first()
        
        if topic_link:
            topic_link.mention_count = issue.mention_count
            topic_link.last_updated = datetime.now()
        else:
            # Create link if missing
            topic_link = TopicIssueLink(
                id=uuid4(),
                topic_key=topic_key,
                issue_id=issue.id,
                mention_count=issue.mention_count
            )
            session.add(topic_link)
    
    def _get_all_issue_mentions(self, session: Session, issue: TopicIssue) -> List[Dict[str, Any]]:
        """
        Get all mentions for an issue with their embeddings, for label/summary regeneration.
        
        Returns:
            List of mention dictionaries with entry_id, text, embedding, etc.
        """
        # Get all issue mentions
        issue_mentions = session.query(IssueMention).filter(
            IssueMention.issue_id == issue.id
        ).all()
        
        if not issue_mentions:
            return []
        
        mention_ids = [im.mention_id for im in issue_mentions]
        
        # Fetch sentiment data with embeddings
        mentions = session.query(SentimentData, SentimentEmbedding).outerjoin(
            SentimentEmbedding, SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.entry_id.in_(mention_ids)
        ).all()
        
        result = []
        for sd, se in mentions:
            embedding = None
            if se and se.embedding:
                embedding = se.embedding
            elif se and se.embedding_vector:
                embedding = se.embedding_vector
            
            # Skip zero vectors
            if embedding and isinstance(embedding, list):
                if all(abs(x) < 1e-6 for x in embedding):
                    continue
            
            result.append({
                'entry_id': sd.entry_id,
                'text': sd.text or '',
                'embedding': embedding,
                'sentiment_score': sd.sentiment_score,
                'sentiment_label': sd.sentiment_label,
                'emotion_label': sd.emotion_label,
                'source_type': sd.source_type,
                'source': sd.source,
                'platform': sd.platform,
                'created_at': sd.created_at
            })
        
        return result
    
    def _calculate_volume_and_velocity(self, session: Session, issue: TopicIssue, new_cluster: List[Dict[str, Any]]):
        """
        Calculate volume and velocity metrics for an issue.
        
        Volume & Velocity Calculation:
        - volume_current_window: Mentions in last 24 hours
        - volume_previous_window: Mentions in previous 24 hours (24-48 hours ago)
        - velocity_percent: Growth rate ((current - previous) / previous) * 100
        - velocity_score: Normalized velocity score (0-100)
        
        Args:
            session: Database session
            issue: Issue to update
            new_cluster: New mentions being added to the issue
        """
        try:
            # Get time window configuration (default: 24 hours)
            try:
                config = ConfigManager()
                time_window_hours = config.get_int('processing.issue.volume.time_window_hours', 24)
            except:
                time_window_hours = 24
            
            from datetime import timezone
            now = datetime.now(timezone.utc)
            current_window_start = now - timedelta(hours=time_window_hours)
            previous_window_start = current_window_start - timedelta(hours=time_window_hours)
            previous_window_end = current_window_start
            
            # Get all mentions linked to this issue
            issue_mentions = session.query(IssueMention).filter(
                IssueMention.issue_id == issue.id
            ).all()
            
            mention_ids = [im.mention_id for im in issue_mentions]
            
            if not mention_ids:
                # No mentions yet, initialize with zeros
                issue.volume_current_window = 0
                issue.volume_previous_window = 0
                issue.velocity_percent = 0.0
                issue.velocity_score = 0.0
                return
            
            # Query mentions with timestamps
            mentions = session.query(SentimentData).filter(
                SentimentData.entry_id.in_(mention_ids)
            ).all()
            
            # Count mentions in each time window
            current_window_count = 0
            previous_window_count = 0
            
            for mention in mentions:
                # Use published_at, published_date, date, or created_at (in order of preference)
                mention_time = None
                if mention.published_at:
                    mention_time = mention.published_at
                elif mention.published_date:
                    mention_time = mention.published_date
                elif mention.date:
                    mention_time = mention.date
                elif mention.created_at:
                    mention_time = mention.created_at
                
                if not mention_time:
                    continue
                
                # Ensure timezone-aware comparison
                if mention_time.tzinfo is None:
                    # Assume UTC if naive
                    mention_time = mention_time.replace(tzinfo=timezone.utc)
                
                # Normalize reference times to UTC
                current_start_utc = current_window_start.replace(tzinfo=timezone.utc) if current_window_start.tzinfo is None else current_window_start
                prev_start_utc = previous_window_start.replace(tzinfo=timezone.utc) if previous_window_start.tzinfo is None else previous_window_start
                prev_end_utc = previous_window_end.replace(tzinfo=timezone.utc) if previous_window_end.tzinfo is None else previous_window_end
                now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
                
                # Count in current window
                if current_start_utc <= mention_time <= now_utc:
                    current_window_count += 1
                
                # Count in previous window
                if prev_start_utc <= mention_time < prev_end_utc:
                    previous_window_count += 1
            
            # Update volume windows
            issue.volume_current_window = current_window_count
            issue.volume_previous_window = previous_window_count
            
            # Calculate velocity_percent
            if previous_window_count > 0:
                velocity_percent = ((current_window_count - previous_window_count) / previous_window_count) * 100.0
            elif current_window_count > 0:
                # No previous mentions, but current has mentions = infinite growth
                # Cap at 1000% for practical purposes
                velocity_percent = 1000.0
            else:
                # No mentions in either window
                velocity_percent = 0.0
            
            issue.velocity_percent = velocity_percent
            
            # Calculate velocity_score (normalized 0-100)
            # Convert velocity_percent to 0-100 score
            # +100% growth → 100 score
            # 0% growth → 50 score
            # -50% decline → 0 score
            if velocity_percent >= 100:
                velocity_score = 100.0
            elif velocity_percent >= 0:
                # Linear: 0% → 50, 100% → 100
                velocity_score = 50.0 + (velocity_percent / 100.0 * 50.0)
            else:
                # Linear: -100% → 0, 0% → 50
                velocity_score = max(0.0, 50.0 + (velocity_percent / 100.0 * 50.0))
            
            issue.velocity_score = velocity_score
            
            logger.debug(
                f"Issue {issue.issue_slug}: volume_current={current_window_count}, "
                f"volume_previous={previous_window_count}, velocity={velocity_percent:.1f}%, "
                f"velocity_score={velocity_score:.1f}"
            )
            
        except Exception as e:
            logger.warning(f"Error calculating volume/velocity for issue {issue.id}: {e}")
            # Set defaults on error
            issue.volume_current_window = issue.volume_current_window or 0
            issue.volume_previous_window = issue.volume_previous_window or 0
            issue.velocity_percent = issue.velocity_percent or 0.0
            issue.velocity_score = issue.velocity_score or 0.0
    
    def _update_issue_metadata(self, session: Session, issue: TopicIssue):
        """
        Update issue metadata fields: top_keywords, top_sources, regions_impacted.
        
        Args:
            session: Database session
            issue: Issue to update
        """
        try:
            # Get all mentions linked to this issue
            issue_mentions = session.query(IssueMention).filter(
                IssueMention.issue_id == issue.id
            ).all()
            
            mention_ids = [im.mention_id for im in issue_mentions]
            
            if not mention_ids:
                return
            
            # Query mentions
            mentions = session.query(SentimentData).filter(
                SentimentData.entry_id.in_(mention_ids)
            ).all()
            
            # Extract keywords from mention texts
            keywords_counter = {}
            sources_counter = {}
            regions_counter = {}
            
            for mention in mentions:
                # Extract keywords from text
                text = (mention.text or mention.content or mention.title or mention.description or '').lower()
                if text:
                    # Simple keyword extraction (split by spaces, filter common words)
                    words = text.split()
                    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
                    for word in words:
                        # Remove punctuation and filter
                        word = word.strip('.,!?;:"()[]{}')
                        if len(word) > 3 and word not in common_words:
                            keywords_counter[word] = keywords_counter.get(word, 0) + 1
                
                # Extract sources/platforms
                if mention.source:
                    sources_counter[mention.source] = sources_counter.get(mention.source, 0) + 1
                elif mention.platform:
                    sources_counter[mention.platform] = sources_counter.get(mention.platform, 0) + 1
                
                # Extract regions from location_label
                if mention.location_label:
                    regions_counter[mention.location_label] = regions_counter.get(mention.location_label, 0) + 1
            
            # Get top keywords (top 10)
            top_keywords = sorted(keywords_counter.items(), key=lambda x: x[1], reverse=True)[:10]
            issue.top_keywords = [kw[0] for kw in top_keywords] if top_keywords else []
            
            # Get top sources (top 5)
            top_sources = sorted(sources_counter.items(), key=lambda x: x[1], reverse=True)[:5]
            issue.top_sources = [src[0] for src in top_sources] if top_sources else []
            
            # Get regions impacted (all unique regions)
            issue.regions_impacted = list(regions_counter.keys())[:10] if regions_counter else []
            
            logger.debug(
                f"Issue {issue.issue_slug}: keywords={len(issue.top_keywords)}, "
                f"sources={len(issue.top_sources)}, regions={len(issue.regions_impacted)}"
            )
            
        except Exception as e:
            logger.warning(f"Error updating metadata for issue {issue.id}: {e}")
    
    def _update_issue_sentiment_aggregation(self, session: Session, issue: TopicIssue):
        """
        Update sentiment aggregation fields for an issue.
        
        Calculates:
        - sentiment_distribution: Distribution of sentiment labels
        - weighted_sentiment_score: Weighted average sentiment score
        - sentiment_index: Converted sentiment score (0-100)
        - emotion_distribution: Aggregated emotion distribution
        - emotion_adjusted_severity: Severity adjusted by emotions
        
        Args:
            session: Database session
            issue: Issue to update
        """
        try:
            from processing.sentiment_aggregation_service import SentimentAggregationService
            
            # Get aggregation service
            aggregation_service = SentimentAggregationService(db_session=session)
            
            # Aggregate sentiment for this issue (24h window)
            aggregation_result = aggregation_service.aggregate_by_issue(
                str(issue.id),
                time_window='24h',
                session=session
            )
            
            if aggregation_result:
                # Update issue with aggregation results
                issue.sentiment_distribution = aggregation_result.get('sentiment_distribution')
                issue.weighted_sentiment_score = aggregation_result.get('weighted_sentiment_score')
                issue.sentiment_index = aggregation_result.get('sentiment_index')
                issue.emotion_distribution = aggregation_result.get('emotion_distribution')
                issue.emotion_adjusted_severity = aggregation_result.get('emotion_adjusted_severity')
                
                logger.debug(
                    f"Issue {issue.issue_slug}: sentiment_index={issue.sentiment_index:.1f}, "
                    f"weighted_score={issue.weighted_sentiment_score:.2f}"
                )
            else:
                # Initialize with defaults if no aggregation
                if issue.sentiment_distribution is None:
                    issue.sentiment_distribution = {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
                if issue.weighted_sentiment_score is None:
                    issue.weighted_sentiment_score = 0.0
                if issue.sentiment_index is None:
                    issue.sentiment_index = 50.0
                if issue.emotion_distribution is None:
                    issue.emotion_distribution = {}
                if issue.emotion_adjusted_severity is None:
                    issue.emotion_adjusted_severity = 0.0
                    
        except Exception as e:
            logger.warning(f"Error updating sentiment aggregation for issue {issue.id}: {e}")
            # Set defaults on error
            if issue.sentiment_distribution is None:
                issue.sentiment_distribution = {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
            if issue.weighted_sentiment_score is None:
                issue.weighted_sentiment_score = 0.0
            if issue.sentiment_index is None:
                issue.sentiment_index = 50.0
    
    def _generate_issue_title(self, session: Session, issue: TopicIssue) -> str:
        """
        Generate a descriptive title for an issue based on its mentions.
        
        Args:
            session: Database session
            issue: Issue to generate title for
            
        Returns:
            Generated title string
        """
        try:
            # Get issue mentions
            issue_mentions = session.query(IssueMention).filter(
                IssueMention.issue_id == issue.id
            ).limit(5).all()  # Use first 5 mentions
            
            mention_ids = [im.mention_id for im in issue_mentions]
            
            if not mention_ids:
                return issue.issue_label  # Fallback to label
            
            # Get mention texts
            mentions = session.query(SentimentData).filter(
                SentimentData.entry_id.in_(mention_ids)
            ).all()
            
            # Use first mention's text (truncated) as title
            if mentions:
                text = mentions[0].text or mentions[0].content or mentions[0].title or ''
                if text:
                    # Truncate to 100 characters
                    title = text[:100].strip()
                    if len(text) > 100:
                        title += "..."
                    return title
            
            return issue.issue_label  # Fallback to label
            
        except Exception as e:
            logger.warning(f"Error generating title for issue {issue.id}: {e}")
            return issue.issue_label  # Fallback to label
    
    def _recalculate_issue_metrics(self, session: Session, issue: TopicIssue):
        """
        Recalculate all metrics for an existing issue (volume, velocity, sentiment, metadata).
        
        This is called for existing issues that don't have new mentions to ensure
        all calculated fields are up-to-date.
        
        Args:
            session: Database session
            issue: Issue to recalculate metrics for
        """
        try:
            # Get all mentions linked to this issue
            issue_mentions = session.query(IssueMention).filter(
                IssueMention.issue_id == issue.id
            ).all()
            
            if not issue_mentions:
                logger.debug(f"No mentions found for issue {issue.issue_slug}, skipping recalculation")
                return
            
            # Convert to cluster format for recalculation
            mention_ids = [im.mention_id for im in issue_mentions]
            mentions = session.query(SentimentData).filter(
                SentimentData.entry_id.in_(mention_ids)
            ).all()
            
            # Convert to cluster format
            cluster = []
            for mention in mentions:
                # Get embedding if available
                embedding = None
                embedding_record = session.query(SentimentEmbedding).filter(
                    SentimentEmbedding.entry_id == mention.entry_id
                ).first()
                if embedding_record and embedding_record.embedding:
                    embedding = embedding_record.embedding if isinstance(embedding_record.embedding, list) else json.loads(embedding_record.embedding)
                
                cluster.append({
                    'entry_id': mention.entry_id,
                    'text': mention.text or mention.content or mention.title or mention.description,
                    'embedding': embedding
                })
            
            # Recalculate all metrics
            self._calculate_volume_and_velocity(session, issue, cluster)
            self._update_issue_metadata(session, issue)
            self._update_issue_sentiment_aggregation(session, issue)
            
            # Update issue title if not set
            if not issue.issue_title:
                issue.issue_title = self._generate_issue_title(session, issue)
            
            # Recalculate priority and lifecycle
            try:
                priority_result = self.priority_calculator.calculate_priority(issue, session)
                issue.priority_score = priority_result['priority_score']
                issue.priority_band = priority_result['priority_band']
                
                lifecycle_state = self.lifecycle_manager.update_lifecycle(str(issue.id))
                if lifecycle_state:
                    issue.state = lifecycle_state
            except Exception as e:
                logger.warning(f"Error recalculating priority/lifecycle for issue {issue.id}: {e}")
            
            logger.debug(f"Recalculated metrics for issue {issue.issue_slug}")
            
        except Exception as e:
            logger.warning(f"Error recalculating metrics for issue {issue.id}: {e}")
    
    def _generate_issue_slug(self, topic_key: str, cluster: List[Dict[str, Any]], session: Optional[Session] = None) -> str:
        """Generate unique issue slug, checking for duplicates."""
        # Use topic key + timestamp + hash + time component for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Use more mentions for better uniqueness (up to 10)
        mention_ids = [m['entry_id'] for m in cluster[:10]]
        cluster_hash = hash(str(sorted(mention_ids))) % 100000  # Larger range
        base_slug = f"{topic_key}-issue-{timestamp}-{abs(cluster_hash)}"
        
        # Check if slug already exists (if session provided)
        if session:
            counter = 0
            slug = base_slug
            while session.query(TopicIssue).filter(TopicIssue.issue_slug == slug).first():
                counter += 1
                slug = f"{base_slug}-{counter}"
                if counter > 100:  # Safety limit
                    # Fallback to UUID if too many collisions
                    from uuid import uuid4
                    slug = f"{topic_key}-issue-{timestamp}-{str(uuid4())[:8]}"
                    break
            return slug
        
        return base_slug
    
    def _generate_issue_label_and_summary(self, cluster: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        """
        Generate both issue label and summary using LLM from 15 closest mentions to centroid.
        Returns a dict with 'title' and 'statement' keys.
        This is the primary method that makes a single LLM call.
        """
        result = {'title': None, 'statement': None}
        
        if not cluster:
            return result
        
        # Get 15 closest mentions to centroid
        closest_mentions = self._get_closest_mentions_to_centroid(cluster, n=15)
        
        if not closest_mentions:
            return result
        
        # Try LLM generation
        if self.openai_client:
            try:
                # Prepare mention texts
                mention_texts = [m.get('text', '')[:500] for m in closest_mentions if m.get('text')]
                if not mention_texts:
                    return result
                
                # Create prompt
                mentions_text = "\n\n".join([f"Mention {i+1}: {text}" for i, text in enumerate(mention_texts)])
                prompt = f"""Below are {len(mention_texts)} representative social media mentions from a high-density cluster. Based only on these posts:

Create a Short Title (max 5 words) that identifies the specific governance issue.

Write a Statement explaining the situation. Output your response in JSON format with keys "title" and "statement".

Mentions:
{mentions_text}

Output JSON only:"""

                multi_model_limiter = get_multi_model_rate_limiter()
                with multi_model_limiter.acquire(self.llm_model, estimated_tokens=800):
                    response = self.openai_client.responses.create(
                        model=self.llm_model,
                        input=[
                            {"role": "system", "content": "You are a senior analyst for the President's Office."},
                            {"role": "user", "content": prompt}
                        ],
                        store=False
                    )
                    
                    # Parse JSON response
                    response_text = response.output_text.strip()
                    try:
                        # Try to extract JSON if wrapped in markdown code blocks
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                        
                        parsed = json.loads(response_text)
                        title = parsed.get('title', '').strip()
                        statement = parsed.get('statement', '').strip()
                        
                        # Ensure title is max 5 words
                        if title:
                            words = title.split()[:5]
                            result['title'] = " ".join(words)
                        result['statement'] = statement if statement else None
                        
                        return result
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON from LLM response: {response_text[:100]}")
                        # Try to extract using regex
                        import re
                        title_match = re.search(r'["\']title["\']\s*:\s*["\']([^"\']+)["\']', response_text)
                        statement_match = re.search(r'["\']statement["\']\s*:\s*["\']([^"\']+)["\']', response_text)
                        if title_match:
                            words = title_match.group(1).split()[:5]
                            result['title'] = " ".join(words)
                        if statement_match:
                            result['statement'] = statement_match.group(1).strip()
                        return result
                    
            except Exception as e:
                logger.warning(f"Error generating label/summary with LLM: {e}")
                return result
        
        return result
    
    def _generate_issue_label(self, cluster: List[Dict[str, Any]]) -> str:
        """
        Generate issue label using LLM from 15 closest mentions to centroid.
        Returns a short title (max 5 words) in JSON format.
        Falls back to simple text extraction if LLM is unavailable.
        """
        if not cluster:
            return "Issue from clustered mentions"
        
        # Get 15 closest mentions to centroid
        closest_mentions = self._get_closest_mentions_to_centroid(cluster, n=15)
        
        if not closest_mentions:
            # Fallback to first mention
            text = cluster[0].get('text', '')
            words = text.split()[:5]
            return " ".join(words)
        
        # Try LLM generation
        if self.openai_client:
            try:
                # Prepare mention texts
                mention_texts = [m.get('text', '')[:500] for m in closest_mentions if m.get('text')]
                if not mention_texts:
                    return "Issue from clustered mentions"
                
                # Create prompt
                mentions_text = "\n\n".join([f"Mention {i+1}: {text}" for i, text in enumerate(mention_texts)])
                prompt = f"""Below are {len(mention_texts)} representative social media mentions from a high-density cluster. Based only on these posts:

Create a Short Title (max 5 words) that identifies the specific governance issue.

Write a Statement explaining the situation. Output your response in JSON format with keys "title" and "statement".

Mentions:
{mentions_text}

Output JSON only:"""

                multi_model_limiter = get_multi_model_rate_limiter()
                with multi_model_limiter.acquire(self.llm_model, estimated_tokens=800):
                    response = self.openai_client.responses.create(
                        model=self.llm_model,
                        input=[
                            {"role": "system", "content": "You are a senior analyst for the President's Office."},
                            {"role": "user", "content": prompt}
                        ],
                        store=False
                    )
                    
                    # Parse JSON response
                    response_text = response.output_text.strip()
                    try:
                        # Try to extract JSON if wrapped in markdown code blocks
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                        
                        result = json.loads(response_text)
                        title = result.get('title', '').strip()
                        if title:
                            # Ensure max 5 words
                            words = title.split()[:5]
                            return " ".join(words)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON from LLM response: {response_text[:100]}")
                        # Try to extract title from response
                        if '"title"' in response_text or "'title'" in response_text:
                            # Simple extraction attempt
                            import re
                            match = re.search(r'["\']title["\']\s*:\s*["\']([^"\']+)["\']', response_text)
                            if match:
                                words = match.group(1).split()[:5]
                                return " ".join(words)
                    
                    # Fallback: use first line or first 5 words
                    first_line = response_text.split('\n')[0].strip()
                    words = first_line.split()[:5]
                    return " ".join(words) if words else "Issue from clustered mentions"
                    
            except Exception as e:
                logger.warning(f"Error generating label with LLM: {e}, falling back to simple extraction")
        
        # Fallback: use text from closest mention
        if closest_mentions:
            text = closest_mentions[0].get('text', '')
            if text:
                words = text.split()[:5]
                return " ".join(words)
        
        return "Issue from clustered mentions"
    
    def _get_closest_mentions_to_centroid(self, cluster: List[Dict[str, Any]], n: int = 15) -> List[Dict[str, Any]]:
        """Get the N mentions closest to the cluster centroid."""
        if not cluster:
            return []
        
        centroid = self.clustering_service._calculate_centroid(cluster)
        if centroid is None:
            return cluster[:n]  # Fallback to first N
        
        # Calculate similarities
        mentions_with_sim = []
        for mention in cluster:
            emb = mention.get('embedding')
            if emb:
                sim = cosine_similarity(emb, centroid)
                mentions_with_sim.append((mention, sim))
        
        if not mentions_with_sim:
            return cluster[:n]
        
        # Sort by similarity (highest first) and take top N
        mentions_with_sim.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in mentions_with_sim[:n]]
    
    def _generate_issue_summary(self, cluster: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate issue summary using LLM from 15 closest mentions to centroid.
        Returns a statement explaining the situation in JSON format.
        """
        if not cluster:
            return None
        
        # Get 15 closest mentions to centroid (same as label generation)
        closest_mentions = self._get_closest_mentions_to_centroid(cluster, n=15)
        
        if not closest_mentions:
            return None
        
        # Try LLM generation
        if self.openai_client:
            try:
                # Prepare mention texts
                mention_texts = [m.get('text', '')[:500] for m in closest_mentions if m.get('text')]
                if not mention_texts:
                    return None
                
                # Create prompt (same as label generation, but we extract the statement)
                mentions_text = "\n\n".join([f"Mention {i+1}: {text}" for i, text in enumerate(mention_texts)])
                prompt = f"""Below are {len(mention_texts)} representative social media mentions from a high-density cluster. Based only on these posts:

Create a Short Title (max 5 words) that identifies the specific governance issue.

Write a Statement explaining the situation. Output your response in JSON format with keys "title" and "statement".

Mentions:
{mentions_text}

Output JSON only:"""

                multi_model_limiter = get_multi_model_rate_limiter()
                with multi_model_limiter.acquire(self.llm_model, estimated_tokens=800):
                    response = self.openai_client.responses.create(
                        model=self.llm_model,
                        input=[
                            {"role": "system", "content": "You are a senior analyst for the President's Office."},
                            {"role": "user", "content": prompt}
                        ],
                        store=False
                    )
                    
                    # Parse JSON response
                    response_text = response.output_text.strip()
                    try:
                        # Try to extract JSON if wrapped in markdown code blocks
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                        
                        result = json.loads(response_text)
                        statement = result.get('statement', '').strip()
                        return statement if statement else None
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON from LLM response: {response_text[:100]}")
                        # Try to extract statement from response
                        if '"statement"' in response_text or "'statement'" in response_text:
                            import re
                            match = re.search(r'["\']statement["\']\s*:\s*["\']([^"\']+)["\']', response_text)
                            if match:
                                return match.group(1).strip()
                        # Fallback: use the response text as-is
                        return response_text if response_text else None
                    
            except Exception as e:
                logger.warning(f"Error generating summary with LLM: {e}, returning None")
                return None
        
        # Fallback: create simple summary from closest mention
        if closest_mentions:
            text = closest_mentions[0].get('text', '')
            if text:
                # Simple truncation as fallback
                return text[:300] + ("..." if len(text) > 300 else "")
        
        return None

