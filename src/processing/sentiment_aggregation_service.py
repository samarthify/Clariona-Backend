"""
Sentiment Aggregation Service - Aggregate sentiment by topic/issue/entity.

Week 5: Aggregation & Integration
Aggregates sentiment data across multiple time windows and dimensions.
"""

# Standard library imports
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import sys
from pathlib import Path
import json

# Third-party imports
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - processing
from processing.weighted_sentiment_calculator import WeightedSentimentCalculator

# Local imports - database
from api.database import SessionLocal
from api.models import (
    SentimentData, SentimentAggregation, MentionTopic, IssueMention, TopicIssue
)

# Module-level setup
logger = get_logger(__name__)


class SentimentAggregationService:
    """
    Aggregates sentiment data by topic, issue, or entity across time windows.
    
    Week 5: Provides aggregated sentiment metrics for analysis and reporting.
    
    Aggregation Types:
    - 'topic': Aggregate by topic_key
    - 'issue': Aggregate by issue_id
    - 'entity': Aggregate by entity_name (future)
    
    Time Windows:
    - '15m': Last 15 minutes
    - '1h': Last 1 hour
    - '24h': Last 24 hours
    - '7d': Last 7 days
    - '30d': Last 30 days
    """
    
    # Time window definitions (in hours)
    TIME_WINDOWS = {
        '15m': 0.25,
        '1h': 1.0,
        '24h': 24.0,
        '7d': 168.0,  # 7 * 24
        '30d': 720.0  # 30 * 24
    }
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize sentiment aggregation service.
        
        Args:
            db_session: Optional database session. If None, creates new session per operation.
        """
        # Load configuration
        try:
            config = ConfigManager()
            self.min_mentions_for_aggregation = config.get_int(
                'processing.aggregation.min_mentions', 3
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for aggregation settings: {e}. Using defaults.")
            self.min_mentions_for_aggregation = 3
        
        self.weighted_calculator = WeightedSentimentCalculator()
        self.db = db_session
        
        logger.debug("SentimentAggregationService initialized")
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def aggregate_by_topic(
        self,
        topic_key: str,
        time_window: str = '24h',
        session: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate sentiment for a specific topic.
        
        Args:
            topic_key: Topic key to aggregate
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            session: Optional database session
        
        Returns:
            Aggregation result dictionary or None if insufficient data
        """
        if time_window not in self.TIME_WINDOWS:
            logger.error(f"Invalid time window: {time_window}")
            return None
        
        db_session = session or self._get_db_session()
        
        try:
            # Calculate time threshold
            hours = self.TIME_WINDOWS[time_window]
            time_threshold = datetime.now() - timedelta(hours=hours)
            
            # Get mentions for this topic within time window
            mentions = self._get_topic_mentions(db_session, topic_key, time_threshold)
            
            if len(mentions) < self.min_mentions_for_aggregation:
                logger.debug(
                    f"Insufficient mentions for topic {topic_key} in {time_window}: "
                    f"{len(mentions)} < {self.min_mentions_for_aggregation}"
                )
                return None
            
            # Calculate aggregation
            result = self._calculate_aggregation(mentions, 'topic', topic_key, time_window)
            
            # Store in database
            self._store_aggregation(db_session, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error aggregating sentiment for topic {topic_key}: {e}", exc_info=True)
            return None
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def aggregate_by_issue(
        self,
        issue_id: str,
        time_window: str = '24h',
        session: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate sentiment for a specific issue.
        
        Args:
            issue_id: Issue UUID to aggregate
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            session: Optional database session
        
        Returns:
            Aggregation result dictionary or None if insufficient data
        """
        if time_window not in self.TIME_WINDOWS:
            logger.error(f"Invalid time window: {time_window}")
            return None
        
        db_session = session or self._get_db_session()
        
        try:
            # Calculate time threshold
            hours = self.TIME_WINDOWS[time_window]
            time_threshold = datetime.now() - timedelta(hours=hours)
            
            # Get mentions for this issue within time window
            mentions = self._get_issue_mentions(db_session, issue_id, time_threshold)
            
            if len(mentions) < self.min_mentions_for_aggregation:
                logger.debug(
                    f"Insufficient mentions for issue {issue_id} in {time_window}: "
                    f"{len(mentions)} < {self.min_mentions_for_aggregation}"
                )
                return None
            
            # Calculate aggregation
            result = self._calculate_aggregation(mentions, 'issue', issue_id, time_window)
            
            # Store in database
            self._store_aggregation(db_session, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error aggregating sentiment for issue {issue_id}: {e}", exc_info=True)
            return None
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def aggregate_all_topics(
        self,
        time_window: str = '24h',
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate sentiment for all topics.
        
        Args:
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            limit: Optional limit on number of topics to process
        
        Returns:
            Dictionary mapping topic_key to aggregation result
        """
        session = self._get_db_session()
        results = {}
        
        try:
            # Get all topics with mentions
            topics_query = session.query(MentionTopic.topic_key).distinct()
            if limit:
                topics_query = topics_query.limit(limit)
            
            topic_keys = [t[0] for t in topics_query.all()]
            
            logger.info(f"Aggregating sentiment for {len(topic_keys)} topics")
            
            for topic_key in topic_keys:
                try:
                    result = self.aggregate_by_topic(topic_key, time_window, session=session)
                    if result:
                        results[topic_key] = result
                except Exception as e:
                    logger.error(f"Error aggregating topic {topic_key}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Completed aggregation for {len(results)} topics")
            return results
            
        except Exception as e:
            logger.error(f"Error in aggregate_all_topics: {e}", exc_info=True)
            return {}
        finally:
            self._close_db_session(session)
    
    def _get_topic_mentions(
        self,
        session: Session,
        topic_key: str,
        time_threshold: datetime
    ) -> List[Dict[str, Any]]:
        """Get mentions for a topic within time window."""
        # Join sentiment_data with mention_topics
        query = session.query(SentimentData).join(
            MentionTopic,
            SentimentData.entry_id == MentionTopic.mention_id
        ).filter(
            and_(
                MentionTopic.topic_key == topic_key,
                SentimentData.created_at >= time_threshold,
                SentimentData.sentiment_score.isnot(None),
                SentimentData.influence_weight.isnot(None)
            )
        )
        
        records = query.all()
        
        # Convert to mention dictionaries
        mentions = []
        for record in records:
            mentions.append({
                'sentiment_score': record.sentiment_score or 0.0,
                'influence_weight': record.influence_weight or 1.0,
                'confidence_weight': record.confidence_weight or 1.0,
                'sentiment_label': record.sentiment_label,
                'emotion_label': record.emotion_label,
                'emotion_distribution': json.loads(record.emotion_distribution) if record.emotion_distribution else None
            })
        
        return mentions
    
    def _get_issue_mentions(
        self,
        session: Session,
        issue_id: str,
        time_threshold: datetime
    ) -> List[Dict[str, Any]]:
        """Get mentions for an issue within time window."""
        # Join sentiment_data with issue_mentions
        query = session.query(SentimentData).join(
            IssueMention,
            SentimentData.entry_id == IssueMention.mention_id
        ).filter(
            and_(
                IssueMention.issue_id == issue_id,
                SentimentData.created_at >= time_threshold,
                SentimentData.sentiment_score.isnot(None),
                SentimentData.influence_weight.isnot(None)
            )
        )
        
        records = query.all()
        
        # Convert to mention dictionaries
        mentions = []
        for record in records:
            mentions.append({
                'sentiment_score': record.sentiment_score or 0.0,
                'influence_weight': record.influence_weight or 1.0,
                'confidence_weight': record.confidence_weight or 1.0,
                'sentiment_label': record.sentiment_label,
                'emotion_label': record.emotion_label,
                'emotion_distribution': json.loads(record.emotion_distribution) if record.emotion_distribution else None
            })
        
        return mentions
    
    def _calculate_aggregation(
        self,
        mentions: List[Dict[str, Any]],
        aggregation_type: str,
        aggregation_key: str,
        time_window: str
    ) -> Dict[str, Any]:
        """Calculate aggregation metrics from mentions."""
        # Calculate weighted sentiment
        weighted_result = self.weighted_calculator.calculate_weighted_sentiment(mentions)
        
        # Calculate sentiment distribution
        sentiment_distribution = self._calculate_sentiment_distribution(mentions)
        
        # Calculate emotion distribution
        emotion_distribution = self._calculate_emotion_distribution(mentions)
        
        # Calculate emotion-adjusted severity
        emotion_adjusted_severity = self._calculate_emotion_adjusted_severity(
            weighted_result['weighted_sentiment_score'],
            emotion_distribution
        )
        
        # Calculate total influence weight
        total_influence_weight = sum(m.get('influence_weight', 1.0) for m in mentions)
        
        return {
            'aggregation_type': aggregation_type,
            'aggregation_key': aggregation_key,
            'time_window': time_window,
            'weighted_sentiment_score': weighted_result['weighted_sentiment_score'],
            'sentiment_index': weighted_result['sentiment_index'],
            'sentiment_distribution': sentiment_distribution,
            'emotion_distribution': emotion_distribution,
            'emotion_adjusted_severity': emotion_adjusted_severity,
            'mention_count': len(mentions),
            'total_influence_weight': total_influence_weight,
            'calculated_at': datetime.now()
        }
    
    def _calculate_sentiment_distribution(
        self,
        mentions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate distribution of sentiment labels."""
        distribution = {'positive': 0, 'negative': 0, 'neutral': 0}
        total = len(mentions)
        
        if total == 0:
            return {k: 0.0 for k in distribution.keys()}
        
        for mention in mentions:
            label = mention.get('sentiment_label', 'neutral')
            if label in distribution:
                distribution[label] += 1
        
        # Convert to proportions
        return {k: v / total for k, v in distribution.items()}
    
    def _calculate_emotion_distribution(
        self,
        mentions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate distribution of emotions."""
        emotion_counts = {}
        total_mentions = 0
        
        for mention in mentions:
            # Try to get emotion from distribution first
            emotion_dist = mention.get('emotion_distribution')
            if emotion_dist and isinstance(emotion_dist, dict):
                for emotion, score in emotion_dist.items():
                    emotion_counts[emotion] = emotion_counts.get(emotion, 0) + score
                total_mentions += 1
            elif mention.get('emotion_label'):
                # Fallback to single emotion label
                emotion = mention.get('emotion_label')
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                total_mentions += 1
        
        if total_mentions == 0:
            return {}
        
        # Normalize to proportions
        return {k: v / total_mentions for k, v in emotion_counts.items()}
    
    def _calculate_emotion_adjusted_severity(
        self,
        sentiment_score: float,
        emotion_distribution: Dict[str, float]
    ) -> float:
        """
        Calculate emotion-adjusted severity score.
        
        Negative emotions (anger, fear, sadness, disgust) increase severity.
        Positive emotions (joy, trust) decrease severity.
        """
        # Base severity from sentiment (0-1, where 1 = most negative)
        base_severity = (1.0 - sentiment_score) / 2.0  # Convert -1 to 1 range to 0-1
        
        # Emotion adjustments
        negative_emotions = ['anger', 'fear', 'sadness', 'disgust']
        positive_emotions = ['joy', 'trust']
        
        emotion_adjustment = 0.0
        
        for emotion, proportion in emotion_distribution.items():
            if emotion in negative_emotions:
                emotion_adjustment += proportion * 0.2  # Increase severity
            elif emotion in positive_emotions:
                emotion_adjustment -= proportion * 0.1  # Decrease severity
        
        # Combine base severity with emotion adjustment
        adjusted_severity = base_severity + emotion_adjustment
        
        # Clamp to 0-1 range
        return max(0.0, min(1.0, adjusted_severity))
    
    def _store_aggregation(
        self,
        session: Session,
        aggregation: Dict[str, Any]
    ):
        """Store aggregation in database."""
        try:
            # Check if aggregation already exists
            existing = session.query(SentimentAggregation).filter(
                SentimentAggregation.aggregation_type == aggregation['aggregation_type'],
                SentimentAggregation.aggregation_key == aggregation['aggregation_key'],
                SentimentAggregation.time_window == aggregation['time_window']
            ).first()
            
            if existing:
                # Update existing
                existing.weighted_sentiment_score = aggregation['weighted_sentiment_score']
                existing.sentiment_index = aggregation['sentiment_index']
                existing.sentiment_distribution = aggregation['sentiment_distribution']
                existing.emotion_distribution = aggregation['emotion_distribution']
                existing.emotion_adjusted_severity = aggregation['emotion_adjusted_severity']
                existing.mention_count = aggregation['mention_count']
                existing.total_influence_weight = aggregation['total_influence_weight']
                existing.calculated_at = aggregation['calculated_at']
            else:
                # Create new
                new_aggregation = SentimentAggregation(
                    id=uuid4(),
                    aggregation_type=aggregation['aggregation_type'],
                    aggregation_key=aggregation['aggregation_key'],
                    time_window=aggregation['time_window'],
                    weighted_sentiment_score=aggregation['weighted_sentiment_score'],
                    sentiment_index=aggregation['sentiment_index'],
                    sentiment_distribution=aggregation['sentiment_distribution'],
                    emotion_distribution=aggregation['emotion_distribution'],
                    emotion_adjusted_severity=aggregation['emotion_adjusted_severity'],
                    mention_count=aggregation['mention_count'],
                    total_influence_weight=aggregation['total_influence_weight'],
                    calculated_at=aggregation['calculated_at']
                )
                session.add(new_aggregation)
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing aggregation: {e}", exc_info=True)
            raise





