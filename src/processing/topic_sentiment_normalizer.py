"""
Topic Sentiment Normalizer - Normalize sentiment scores against topic baselines.

Week 5: Aggregation & Integration
Calculates baseline sentiment per topic and normalizes current sentiment against baselines.
"""

# Standard library imports
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
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
from processing.sentiment_aggregation_service import SentimentAggregationService

# Local imports - database
from api.database import SessionLocal
from api.models import (
    TopicSentimentBaseline, SentimentAggregation, SentimentData, MentionTopic
)

# Module-level setup
logger = get_logger(__name__)


class TopicSentimentNormalizer:
    """
    Normalizes sentiment scores against topic-specific baselines.
    
    Week 5: Provides normalized sentiment metrics that account for topic-specific variations.
    
    Normalization Process:
    1. Calculate baseline sentiment for each topic (historical average)
    2. Normalize current sentiment against baseline
    3. Store baselines in database
    4. Provide normalized sentiment index (adjusted for topic baseline)
    
    Why Normalize:
    - Different topics have different baseline sentiment levels
    - Healthcare might average 60 (slightly positive)
    - Security might average 40 (slightly negative)
    - Normalization allows fair comparison across topics
    """
    
    # Default lookback period for baseline calculation (days)
    DEFAULT_LOOKBACK_DAYS = 30
    
    # Minimum sample size for reliable baseline
    MIN_SAMPLE_SIZE = 50
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize topic sentiment normalizer.
        
        Args:
            db_session: Optional database session. If None, creates new session per operation.
        """
        # Load configuration
        try:
            config = ConfigManager()
            self.default_lookback_days = config.get_int(
                'processing.normalization.lookback_days', self.DEFAULT_LOOKBACK_DAYS
            )
            self.min_sample_size = config.get_int(
                'processing.normalization.min_sample_size', self.MIN_SAMPLE_SIZE
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for normalization settings: {e}. Using defaults.")
            self.default_lookback_days = self.DEFAULT_LOOKBACK_DAYS
            self.min_sample_size = self.MIN_SAMPLE_SIZE
        
        self.aggregation_service = SentimentAggregationService()
        self.db = db_session
        
        logger.debug("TopicSentimentNormalizer initialized")
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def calculate_baseline_for_topic(
        self,
        topic_key: str,
        lookback_days: Optional[int] = None,
        session: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate baseline sentiment for a topic.
        
        Args:
            topic_key: Topic key to calculate baseline for
            lookback_days: Number of days to look back (default: 30)
            session: Optional database session
        
        Returns:
            Baseline result dictionary or None if insufficient data
        """
        if lookback_days is None:
            lookback_days = self.default_lookback_days
        
        db_session = session or self._get_db_session()
        
        try:
            # Calculate time threshold
            time_threshold = datetime.now() - timedelta(days=lookback_days)
            
            # Get all mentions for this topic in lookback period
            mentions = self._get_topic_mentions_for_baseline(db_session, topic_key, time_threshold)
            
            if len(mentions) < self.min_sample_size:
                logger.debug(
                    f"Insufficient mentions for baseline calculation for topic {topic_key}: "
                    f"{len(mentions)} < {self.min_sample_size}"
                )
                return None
            
            # Calculate baseline sentiment index
            baseline_index = self._calculate_baseline_index(mentions)
            
            # Store baseline
            baseline = {
                'topic_key': topic_key,
                'baseline_sentiment_index': baseline_index,
                'lookback_days': lookback_days,
                'sample_size': len(mentions),
                'baseline_calculated_at': datetime.now()
            }
            
            self._store_baseline(db_session, baseline)
            
            return baseline
            
        except Exception as e:
            logger.error(f"Error calculating baseline for topic {topic_key}: {e}", exc_info=True)
            return None
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def calculate_baselines_for_all_topics(
        self,
        lookback_days: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate baselines for all topics.
        
        Args:
            lookback_days: Number of days to look back (default: 30)
            limit: Optional limit on number of topics to process
        
        Returns:
            Dictionary mapping topic_key to baseline result
        """
        if lookback_days is None:
            lookback_days = self.default_lookback_days
        
        session = self._get_db_session()
        results = {}
        
        try:
            # Get all topics with mentions
            topics_query = session.query(MentionTopic.topic_key).distinct()
            if limit:
                topics_query = topics_query.limit(limit)
            
            topic_keys = [t[0] for t in topics_query.all()]
            
            logger.info(f"Calculating baselines for {len(topic_keys)} topics")
            
            for topic_key in topic_keys:
                try:
                    result = self.calculate_baseline_for_topic(
                        topic_key, lookback_days, session=session
                    )
                    if result:
                        results[topic_key] = result
                except Exception as e:
                    logger.error(f"Error calculating baseline for topic {topic_key}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Completed baseline calculation for {len(results)} topics")
            return results
            
        except Exception as e:
            logger.error(f"Error in calculate_baselines_for_all_topics: {e}", exc_info=True)
            return {}
        finally:
            self._close_db_session(session)
    
    def normalize_sentiment_for_topic(
        self,
        topic_key: str,
        current_sentiment_index: float,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Normalize current sentiment index against topic baseline.
        
        Args:
            topic_key: Topic key
            current_sentiment_index: Current sentiment index (0-100)
            session: Optional database session
        
        Returns:
            Normalized sentiment result:
            {
                'normalized_index': float,  # Adjusted sentiment index
                'baseline_index': float,    # Topic baseline
                'deviation': float,        # Deviation from baseline
                'normalized_score': float   # Normalized score (-1.0 to 1.0)
            }
        """
        db_session = session or self._get_db_session()
        
        try:
            # Get baseline for topic
            baseline = self._get_baseline(db_session, topic_key)
            
            if not baseline:
                logger.debug(f"No baseline found for topic {topic_key}, using default (50.0)")
                baseline_index = 50.0  # Neutral baseline
            else:
                baseline_index = baseline.baseline_sentiment_index or 50.0
            
            # Calculate deviation from baseline
            deviation = current_sentiment_index - baseline_index
            
            # Normalized index: 50 + deviation (centered around 50)
            normalized_index = 50.0 + deviation
            
            # Clamp to 0-100 range
            normalized_index = max(0.0, min(100.0, normalized_index))
            
            # Convert to normalized score (-1.0 to 1.0)
            # normalized_index 0-100 -> normalized_score -1.0 to 1.0
            normalized_score = (normalized_index - 50.0) / 50.0
            
            return {
                'normalized_index': normalized_index,
                'baseline_index': baseline_index,
                'deviation': deviation,
                'normalized_score': normalized_score,
                'current_index': current_sentiment_index
            }
            
        except Exception as e:
            logger.error(f"Error normalizing sentiment for topic {topic_key}: {e}", exc_info=True)
            # Return unnormalized result on error
            return {
                'normalized_index': current_sentiment_index,
                'baseline_index': 50.0,
                'deviation': current_sentiment_index - 50.0,
                'normalized_score': (current_sentiment_index - 50.0) / 50.0,
                'current_index': current_sentiment_index
            }
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def normalize_aggregation(
        self,
        aggregation: Dict[str, Any],
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Normalize a sentiment aggregation result.
        
        Args:
            aggregation: Aggregation result from SentimentAggregationService
            session: Optional database session
        
        Returns:
            Aggregation with normalized fields added
        """
        if aggregation.get('aggregation_type') != 'topic':
            logger.warning("Normalization only supported for topic aggregations")
            return aggregation
        
        topic_key = aggregation.get('aggregation_key')
        current_index = aggregation.get('sentiment_index', 50.0)
        
        normalized = self.normalize_sentiment_for_topic(topic_key, current_index, session=session)
        
        # Add normalized fields to aggregation
        aggregation['normalized_sentiment_index'] = normalized['normalized_index']
        aggregation['baseline_sentiment_index'] = normalized['baseline_index']
        aggregation['deviation_from_baseline'] = normalized['deviation']
        aggregation['normalized_sentiment_score'] = normalized['normalized_score']
        
        return aggregation
    
    def _get_topic_mentions_for_baseline(
        self,
        session: Session,
        topic_key: str,
        time_threshold: datetime
    ) -> List[Dict[str, Any]]:
        """Get mentions for baseline calculation."""
        # Get all mentions for topic in lookback period
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
                'confidence_weight': record.confidence_weight or 1.0
            })
        
        return mentions
    
    def _calculate_baseline_index(self, mentions: List[Dict[str, Any]]) -> float:
        """Calculate baseline sentiment index from mentions."""
        from processing.weighted_sentiment_calculator import WeightedSentimentCalculator
        
        calculator = WeightedSentimentCalculator()
        result = calculator.calculate_weighted_sentiment(mentions)
        
        return result['sentiment_index']
    
    def _get_baseline(
        self,
        session: Session,
        topic_key: str
    ) -> Optional[TopicSentimentBaseline]:
        """Get baseline for topic from database."""
        return session.query(TopicSentimentBaseline).filter(
            TopicSentimentBaseline.topic_key == topic_key
        ).first()
    
    def _store_baseline(
        self,
        session: Session,
        baseline: Dict[str, Any]
    ):
        """Store baseline in database."""
        try:
            # Check if baseline exists
            existing = session.query(TopicSentimentBaseline).filter(
                TopicSentimentBaseline.topic_key == baseline['topic_key']
            ).first()
            
            if existing:
                # Update existing
                existing.baseline_sentiment_index = baseline['baseline_sentiment_index']
                existing.lookback_days = baseline['lookback_days']
                existing.sample_size = baseline['sample_size']
                existing.baseline_calculated_at = baseline['baseline_calculated_at']
                existing.updated_at = datetime.now()
            else:
                # Create new
                new_baseline = TopicSentimentBaseline(
                    topic_key=baseline['topic_key'],
                    baseline_sentiment_index=baseline['baseline_sentiment_index'],
                    lookback_days=baseline['lookback_days'],
                    sample_size=baseline['sample_size'],
                    baseline_calculated_at=baseline['baseline_calculated_at']
                )
                session.add(new_baseline)
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing baseline: {e}", exc_info=True)
            raise





