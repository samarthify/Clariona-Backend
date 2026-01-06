"""
Sentiment Trend Calculator - Calculate sentiment trends over time.

Week 5: Aggregation & Integration
Calculates trends by comparing current vs previous periods.
"""

# Standard library imports
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import sys
from pathlib import Path

# Third-party imports
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - processing
from processing.sentiment_aggregation_service import SentimentAggregationService

# Local imports - database
from api.database import SessionLocal
from api.models import SentimentTrend, SentimentAggregation

# Module-level setup
logger = get_logger(__name__)


class SentimentTrendCalculator:
    """
    Calculates sentiment trends by comparing current vs previous periods.
    
    Week 5: Provides trend analysis (improving/deteriorating/stable) for topics and issues.
    
    Trend Calculation:
    - Compares current period sentiment index with previous period
    - Determines direction: 'improving', 'deteriorating', or 'stable'
    - Calculates magnitude of change
    - Stores trend data in database
    """
    
    # Trend thresholds
    IMPROVEMENT_THRESHOLD = 5.0  # Points improvement to be considered "improving"
    DETERIORATION_THRESHOLD = -5.0  # Points decline to be considered "deteriorating"
    STABLE_THRESHOLD = 2.0  # Points within this range = "stable"
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize sentiment trend calculator.
        
        Args:
            db_session: Optional database session. If None, creates new session per operation.
        """
        # Load configuration
        try:
            config = ConfigManager()
            self.improvement_threshold = config.get_float(
                'processing.trends.improvement_threshold', 5.0
            )
            self.deterioration_threshold = config.get_float(
                'processing.trends.deterioration_threshold', -5.0
            )
            self.stable_threshold = config.get_float(
                'processing.trends.stable_threshold', 2.0
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for trend settings: {e}. Using defaults.")
            self.improvement_threshold = self.IMPROVEMENT_THRESHOLD
            self.deterioration_threshold = self.DETERIORATION_THRESHOLD
            self.stable_threshold = self.STABLE_THRESHOLD
        
        self.aggregation_service = SentimentAggregationService()
        self.db = db_session
        
        logger.debug("SentimentTrendCalculator initialized")
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def calculate_trend_for_topic(
        self,
        topic_key: str,
        time_window: str = '24h',
        session: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate sentiment trend for a topic.
        
        Args:
            topic_key: Topic key to calculate trend for
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            session: Optional database session
        
        Returns:
            Trend result dictionary or None if insufficient data
        """
        db_session = session or self._get_db_session()
        
        try:
            # Get current period aggregation
            current_aggregation = self.aggregation_service.aggregate_by_topic(
                topic_key, time_window, session=db_session
            )
            
            if not current_aggregation:
                logger.debug(f"No current aggregation for topic {topic_key}")
                return None
            
            # Get previous period aggregation
            previous_aggregation = self._get_previous_aggregation(
                db_session, 'topic', topic_key, time_window
            )
            
            if not previous_aggregation:
                logger.debug(f"No previous aggregation for topic {topic_key}, creating baseline")
                # Create baseline trend (stable, no change)
                return self._create_baseline_trend(
                    current_aggregation, 'topic', topic_key, time_window
                )
            
            # Calculate trend
            trend = self._calculate_trend(
                current_aggregation,
                previous_aggregation,
                'topic',
                topic_key,
                time_window
            )
            
            # Store in database
            self._store_trend(db_session, trend)
            
            return trend
            
        except Exception as e:
            logger.error(f"Error calculating trend for topic {topic_key}: {e}", exc_info=True)
            return None
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def calculate_trend_for_issue(
        self,
        issue_id: str,
        time_window: str = '24h',
        session: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate sentiment trend for an issue.
        
        Args:
            issue_id: Issue UUID to calculate trend for
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            session: Optional database session
        
        Returns:
            Trend result dictionary or None if insufficient data
        """
        db_session = session or self._get_db_session()
        
        try:
            # Get current period aggregation
            current_aggregation = self.aggregation_service.aggregate_by_issue(
                issue_id, time_window, session=db_session
            )
            
            if not current_aggregation:
                logger.debug(f"No current aggregation for issue {issue_id}")
                return None
            
            # Get previous period aggregation
            previous_aggregation = self._get_previous_aggregation(
                db_session, 'issue', issue_id, time_window
            )
            
            if not previous_aggregation:
                logger.debug(f"No previous aggregation for issue {issue_id}, creating baseline")
                # Create baseline trend (stable, no change)
                return self._create_baseline_trend(
                    current_aggregation, 'issue', issue_id, time_window
                )
            
            # Calculate trend
            trend = self._calculate_trend(
                current_aggregation,
                previous_aggregation,
                'issue',
                issue_id,
                time_window
            )
            
            # Store in database
            self._store_trend(db_session, trend)
            
            return trend
            
        except Exception as e:
            logger.error(f"Error calculating trend for issue {issue_id}: {e}", exc_info=True)
            return None
        finally:
            if not session:
                self._close_db_session(db_session)
    
    def calculate_trends_for_all_topics(
        self,
        time_window: str = '24h',
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate trends for all topics.
        
        Args:
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            limit: Optional limit on number of topics to process
        
        Returns:
            Dictionary mapping topic_key to trend result
        """
        session = self._get_db_session()
        results = {}
        
        try:
            # Get all topics with aggregations
            aggregations = session.query(SentimentAggregation).filter(
                SentimentAggregation.aggregation_type == 'topic',
                SentimentAggregation.time_window == time_window
            )
            
            if limit:
                aggregations = aggregations.limit(limit)
            
            topic_keys = [agg.aggregation_key for agg in aggregations.distinct().all()]
            
            logger.info(f"Calculating trends for {len(topic_keys)} topics")
            
            for topic_key in topic_keys:
                try:
                    result = self.calculate_trend_for_topic(topic_key, time_window, session=session)
                    if result:
                        results[topic_key] = result
                except Exception as e:
                    logger.error(f"Error calculating trend for topic {topic_key}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Completed trend calculation for {len(results)} topics")
            return results
            
        except Exception as e:
            logger.error(f"Error in calculate_trends_for_all_topics: {e}", exc_info=True)
            return {}
        finally:
            self._close_db_session(session)
    
    def _get_previous_aggregation(
        self,
        session: Session,
        aggregation_type: str,
        aggregation_key: str,
        time_window: str
    ) -> Optional[Dict[str, Any]]:
        """Get previous period aggregation from database."""
        # Look for most recent aggregation before current period
        aggregation = session.query(SentimentAggregation).filter(
            SentimentAggregation.aggregation_type == aggregation_type,
            SentimentAggregation.aggregation_key == aggregation_key,
            SentimentAggregation.time_window == time_window
        ).order_by(SentimentAggregation.calculated_at.desc()).offset(1).first()
        
        if not aggregation:
            return None
        
        return {
            'sentiment_index': aggregation.sentiment_index,
            'calculated_at': aggregation.calculated_at
        }
    
    def _calculate_trend(
        self,
        current_aggregation: Dict[str, Any],
        previous_aggregation: Dict[str, Any],
        aggregation_type: str,
        aggregation_key: str,
        time_window: str
    ) -> Dict[str, Any]:
        """Calculate trend from current and previous aggregations."""
        current_index = current_aggregation.get('sentiment_index', 50.0)
        previous_index = previous_aggregation.get('sentiment_index', 50.0)
        
        # Calculate change
        change = current_index - previous_index
        magnitude = abs(change)
        
        # Determine direction
        if change >= self.improvement_threshold:
            direction = 'improving'
        elif change <= self.deterioration_threshold:
            direction = 'deteriorating'
        elif magnitude <= self.stable_threshold:
            direction = 'stable'
        else:
            # Small change, determine by sign
            direction = 'improving' if change > 0 else 'deteriorating'
        
        # Calculate period boundaries
        current_time = current_aggregation.get('calculated_at', datetime.now())
        period_end = current_time
        period_start = self._calculate_period_start(time_window, period_end)
        
        previous_time = previous_aggregation.get('calculated_at', period_start - timedelta(hours=24))
        previous_period_end = previous_time
        previous_period_start = self._calculate_period_start(time_window, previous_period_end)
        
        return {
            'aggregation_type': aggregation_type,
            'aggregation_key': aggregation_key,
            'time_window': time_window,
            'current_sentiment_index': current_index,
            'previous_sentiment_index': previous_index,
            'trend_direction': direction,
            'trend_magnitude': magnitude,
            'period_start': period_start,
            'period_end': period_end,
            'previous_period_start': previous_period_start,
            'previous_period_end': previous_period_end,
            'calculated_at': datetime.now()
        }
    
    def _create_baseline_trend(
        self,
        current_aggregation: Dict[str, Any],
        aggregation_type: str,
        aggregation_key: str,
        time_window: str
    ) -> Dict[str, Any]:
        """Create baseline trend when no previous data exists."""
        current_index = current_aggregation.get('sentiment_index', 50.0)
        current_time = current_aggregation.get('calculated_at', datetime.now())
        
        period_end = current_time
        period_start = self._calculate_period_start(time_window, period_end)
        
        return {
            'aggregation_type': aggregation_type,
            'aggregation_key': aggregation_key,
            'time_window': time_window,
            'current_sentiment_index': current_index,
            'previous_sentiment_index': current_index,  # Same as current (baseline)
            'trend_direction': 'stable',
            'trend_magnitude': 0.0,
            'period_start': period_start,
            'period_end': period_end,
            'previous_period_start': period_start - timedelta(hours=24),  # Placeholder
            'previous_period_end': period_start,  # Placeholder
            'calculated_at': datetime.now()
        }
    
    def _calculate_period_start(self, time_window: str, period_end: datetime) -> datetime:
        """Calculate period start time from time window."""
        hours = SentimentAggregationService.TIME_WINDOWS.get(time_window, 24.0)
        return period_end - timedelta(hours=hours)
    
    def _store_trend(
        self,
        session: Session,
        trend: Dict[str, Any]
    ):
        """Store trend in database."""
        try:
            # Check if trend already exists (update most recent)
            existing = session.query(SentimentTrend).filter(
                SentimentTrend.aggregation_type == trend['aggregation_type'],
                SentimentTrend.aggregation_key == trend['aggregation_key'],
                SentimentTrend.time_window == trend['time_window']
            ).order_by(SentimentTrend.calculated_at.desc()).first()
            
            if existing:
                # Update existing
                existing.current_sentiment_index = trend['current_sentiment_index']
                existing.previous_sentiment_index = trend['previous_sentiment_index']
                existing.trend_direction = trend['trend_direction']
                existing.trend_magnitude = trend['trend_magnitude']
                existing.period_start = trend['period_start']
                existing.period_end = trend['period_end']
                existing.previous_period_start = trend['previous_period_start']
                existing.previous_period_end = trend['previous_period_end']
                existing.calculated_at = trend['calculated_at']
            else:
                # Create new
                new_trend = SentimentTrend(
                    id=uuid4(),
                    aggregation_type=trend['aggregation_type'],
                    aggregation_key=trend['aggregation_key'],
                    time_window=trend['time_window'],
                    current_sentiment_index=trend['current_sentiment_index'],
                    previous_sentiment_index=trend['previous_sentiment_index'],
                    trend_direction=trend['trend_direction'],
                    trend_magnitude=trend['trend_magnitude'],
                    period_start=trend['period_start'],
                    period_end=trend['period_end'],
                    previous_period_start=trend['previous_period_start'],
                    previous_period_end=trend['previous_period_end'],
                    calculated_at=trend['calculated_at']
                )
                session.add(new_trend)
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing trend: {e}", exc_info=True)
            raise





