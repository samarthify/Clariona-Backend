"""
Issue Detection Engine - Detects and manages issues from clustered mentions.

Week 4: Clustering-based issue detection and management.
"""

# Standard library imports
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import json
import sys
from pathlib import Path

# Third-party imports
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

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

# Local imports - database
from api.database import SessionLocal
from api.models import (
    SentimentData, SentimentEmbedding, MentionTopic,
    TopicIssue, IssueMention, TopicIssueLink
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
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for detection settings: {e}. Using defaults.")
            self.issue_similarity_threshold = issue_similarity_threshold or 0.70
        
        self.clustering_service = IssueClusteringService(
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size,
            time_window_hours=time_window_hours,
            db_session=db_session
        )
        
        # Initialize lifecycle manager and priority calculator
        self.lifecycle_manager = IssueLifecycleManager()
        self.priority_calculator = IssuePriorityCalculator()
        
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
            
            # Get mentions for this topic that don't have issues yet
            mentions = self._get_unprocessed_mentions(session, topic_key, limit)
            
            if not mentions:
                logger.info(f"No unprocessed mentions for topic: {topic_key}")
                return []
            
            logger.info(f"Found {len(mentions)} unprocessed mentions for topic: {topic_key}")
            
            # Cluster mentions
            clusters = self.clustering_service.cluster_mentions(mentions, topic_key)
            
            if not clusters:
                logger.info(f"No valid clusters found for topic: {topic_key}")
                return []
            
            logger.info(f"Found {len(clusters)} clusters for topic: {topic_key}")
            
            # Get existing issues for this topic
            existing_issues = self._get_existing_issues(session, topic_key)
            
            # Process each cluster
            created_issues = []
            updated_issue_ids = set()  # Track which issues were updated
            
            for cluster in clusters:
                # Check if cluster matches existing issue
                matched_issue = self._find_similar_issue(session, cluster, existing_issues, topic_key)
                
                if matched_issue:
                    # Update existing issue
                    logger.info(f"Updating existing issue: {matched_issue.issue_slug}")
                    self._update_issue_with_mentions(session, matched_issue, cluster, topic_key)
                    updated_issue_ids.add(matched_issue.id)
                    created_issues.append({
                        'issue_id': str(matched_issue.id),
                        'issue_slug': matched_issue.issue_slug,
                        'action': 'updated',
                        'mentions_added': len(cluster)
                    })
                else:
                    # Create new issue (if conditions met)
                    if self._check_issue_conditions(cluster):
                        new_issue = self._create_issue_from_cluster(session, cluster, topic_key)
                        if new_issue:
                            updated_issue_ids.add(new_issue.id)
                            created_issues.append({
                                'issue_id': str(new_issue.id),
                                'issue_slug': new_issue.issue_slug,
                                'action': 'created',
                                'mentions_count': len(cluster)
                            })
                            existing_issues.append(new_issue)  # Add to list for future matching
                    else:
                        logger.debug(f"Cluster does not meet issue conditions, skipping")
            
            # Recalculate all existing issues for this topic (even if no new mentions)
            # This ensures volume/velocity, sentiment aggregation, and metadata are up-to-date
            recalculated_count = 0
            for existing_issue in existing_issues:
                if existing_issue.id not in updated_issue_ids:
                    logger.debug(f"Recalculating metrics for existing issue: {existing_issue.issue_slug}")
                    self._recalculate_issue_metrics(session, existing_issue)
                    recalculated_count += 1
            
            session.commit()
            
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
    
    def _get_unprocessed_mentions(self, session: Session, topic_key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get mentions for a topic that don't have issues yet.
        
        Args:
            session: Database session
            topic_key: Topic key
            limit: Optional limit
        
        Returns:
            List of mention dictionaries with embeddings
        """
        # Get mentions with this topic that don't have issues
        query = session.query(SentimentData, MentionTopic).join(
            MentionTopic, SentimentData.entry_id == MentionTopic.mention_id
        ).filter(
            MentionTopic.topic_key == topic_key,
            ~SentimentData.entry_id.in_(
                session.query(IssueMention.mention_id).subquery()
            )
        )
        
        if limit:
            query = query.limit(limit)
        
        results = query.all()
        
        mentions = []
        for sentiment_data, mention_topic in results:
            mention_dict = {
                'entry_id': sentiment_data.entry_id,
                'text': sentiment_data.text or sentiment_data.content or sentiment_data.title or '',
                'run_timestamp': sentiment_data.run_timestamp or sentiment_data.created_at,
                'sentiment_label': sentiment_data.sentiment_label,
                'sentiment_score': sentiment_data.sentiment_score,
                'emotion_label': sentiment_data.emotion_label,
                'source_type': sentiment_data.source_type,
                'topic_key': topic_key,
                'topic_confidence': mention_topic.topic_confidence
            }
            
            # Try to get embedding
            embedding_record = session.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id == sentiment_data.entry_id
            ).first()
            
            if embedding_record and embedding_record.embedding:
                if isinstance(embedding_record.embedding, str):
                    mention_dict['embedding'] = json.loads(embedding_record.embedding)
                else:
                    mention_dict['embedding'] = embedding_record.embedding
            
            mentions.append(mention_dict)
        
        return mentions
    
    def _get_existing_issues(self, session: Session, topic_key: str) -> List[TopicIssue]:
        """Get existing active issues for a topic."""
        return session.query(TopicIssue).filter(
            TopicIssue.topic_key == topic_key,
            TopicIssue.is_active == True,
            TopicIssue.is_archived == False
        ).all()
    
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
            logger.debug(f"Found matching issue: {best_match.issue_slug} (similarity: {best_similarity:.3f})")
        
        return best_match
    
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
        
        Conditions (from master plan):
        1. Minimum cluster size (handled by clustering service)
        2. Temporal proximity (handled by time window)
        3. Volume/velocity thresholds (optional - can be added)
        
        Args:
            cluster: Cluster of mentions
        
        Returns:
            True if conditions met
        """
        # Condition 1: Minimum size (already filtered by clustering service)
        if len(cluster) < self.clustering_service.min_cluster_size:
            return False
        
        # Condition 2: Temporal proximity (already handled by time window grouping)
        # Additional check: ensure mentions are within reasonable time range
        timestamps = [
            self.clustering_service._get_timestamp(m) 
            for m in cluster
        ]
        
        if timestamps:
            time_span = max(timestamps) - min(timestamps)
            if time_span > timedelta(hours=self.clustering_service.time_window_hours * 2):
                logger.debug(f"Cluster time span too large: {time_span}")
                return False
        
        # Condition 3: Volume/velocity (optional - can be enhanced)
        # For now, minimum size is sufficient
        
        return True
    
    def _create_issue_from_cluster(self,
                                   session: Session,
                                   cluster: List[Dict[str, Any]],
                                   topic_key: str) -> Optional[TopicIssue]:
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
        
        logger.info(f"Creating new issue from cluster with {len(cluster)} mentions")
        
        # Generate issue slug and label
        issue_slug = self._generate_issue_slug(topic_key, cluster)
        issue_label = self._generate_issue_label(cluster)
        
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
        
        session.add(issue)
        session.flush()  # Get issue.id
        
        # Generate issue title
        issue.issue_title = self._generate_issue_title(session, issue)
        
        # Calculate initial volume and velocity for new issue
        self._calculate_volume_and_velocity(session, issue, cluster)
        
        # Update metadata and sentiment aggregation
        self._update_issue_metadata(session, issue)
        self._update_issue_sentiment_aggregation(session, issue)
        
        # Link mentions to issue
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
                topic_key=topic_key
            )
            session.add(issue_mention)
        
        # Create topic-issue link
        topic_link = TopicIssueLink(
            id=uuid4(),
            topic_key=topic_key,
            issue_id=issue.id,
            mention_count=len(cluster)
        )
        session.add(topic_link)
        
        # Calculate initial priority and update lifecycle
        try:
            # Calculate priority
            priority_result = self.priority_calculator.calculate_priority(issue, session)
            issue.priority_score = priority_result['priority_score']
            issue.priority_band = priority_result['priority_band']
            
            # Update lifecycle state
            lifecycle_result = self.lifecycle_manager.update_lifecycle(issue, session)
            issue.state = lifecycle_result['state']
            issue.state_reason = lifecycle_result.get('reason')
            
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
                                    topic_key: str):
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
                topic_key=topic_key
            )
            session.add(issue_mention)
        
        # Update issue metrics
        issue.mention_count += len(cluster)
        issue.last_activity = datetime.now()
        
        # Calculate volume and velocity
        self._calculate_volume_and_velocity(session, issue, cluster)
        
        # Update metadata (keywords, sources, regions)
        self._update_issue_metadata(session, issue)
        
        # Update sentiment aggregation
        self._update_issue_sentiment_aggregation(session, issue)
        
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
            
            # Update lifecycle state
            lifecycle_result = self.lifecycle_manager.update_lifecycle(issue, session)
            issue.state = lifecycle_result['state']
            issue.state_reason = lifecycle_result.get('reason')
            
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
                
                lifecycle_result = self.lifecycle_manager.update_lifecycle(issue, session)
                issue.state = lifecycle_result['state']
                issue.state_reason = lifecycle_result.get('reason')
            except Exception as e:
                logger.warning(f"Error recalculating priority/lifecycle for issue {issue.id}: {e}")
            
            logger.debug(f"Recalculated metrics for issue {issue.issue_slug}")
            
        except Exception as e:
            logger.warning(f"Error recalculating metrics for issue {issue.id}: {e}")
    
    def _generate_issue_slug(self, topic_key: str, cluster: List[Dict[str, Any]]) -> str:
        """Generate unique issue slug."""
        # Use topic key + timestamp + hash
        timestamp = datetime.now().strftime("%Y%m%d")
        cluster_hash = hash(str([m['entry_id'] for m in cluster[:3]])) % 10000
        return f"{topic_key}-issue-{timestamp}-{abs(cluster_hash)}"
    
    def _generate_issue_label(self, cluster: List[Dict[str, Any]]) -> str:
        """
        Generate issue label from cluster mentions.
        Attempts to find the most representative mention (closest to centroid).
        """
        if not cluster:
            return "Issue from clustered mentions"
            
        try:
            # 1. Calculate centroid
            centroid = self.clustering_service._calculate_centroid(cluster)
            
            selected_text = ""
            
            if centroid is not None:
                # 2. Find mention closest to centroid
                best_sim = -1.0
                best_mention = None
                
                for mention in cluster:
                    emb = mention.get('embedding')
                    if emb:
                        sim = cosine_similarity(emb, centroid)
                        if sim > best_sim:
                            best_sim = sim
                            best_mention = mention
                            
                if best_mention:
                    selected_text = best_mention.get('text', '')
            
            # Fallback to first mention if no embedding matching
            if not selected_text and cluster:
                selected_text = cluster[0].get('text', '')
                
            if selected_text:
                # Truncate and clean
                # Use a cleaner cutoff
                label = selected_text[:80].strip()
                if len(selected_text) > 80:
                    label += "..."
                return label
                
        except Exception as e:
            logger.warning(f"Error generating label: {e}")
            if cluster:
                return cluster[0].get('text', '')[:100]
        
        return "Issue from clustered mentions"

