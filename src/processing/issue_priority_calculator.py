"""
Issue Priority Calculator - Calculates priority scores for issues.

Week 4: Multi-factor priority calculation.
"""

# Standard library imports
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Third-party imports
from sqlalchemy.orm import Session

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - database
from api.database import SessionLocal
from api.models import TopicIssue, IssueMention, SentimentData

# Module-level setup
logger = get_logger(__name__)


class IssuePriorityCalculator:
    """
    Calculates priority scores for issues based on multiple factors.
    
    Priority Formula:
    priority_score = (
        sentiment_weight * sentiment_score +
        volume_weight * volume_score +
        time_weight * time_score +
        velocity_weight * velocity_score
    )
    
    Scores are normalized to 0-100 range.
    
    Week 4: Multi-factor priority calculation.
    """
    
    def __init__(self,
                 sentiment_weight: Optional[float] = None,
                 volume_weight: Optional[float] = None,
                 time_weight: Optional[float] = None,
                 velocity_weight: Optional[float] = None,
                 db_session: Optional[Session] = None):
        """
        Initialize priority calculator.
        
        Args:
            sentiment_weight: Weight for sentiment component (0.0-1.0). 
                             If None, loads from ConfigManager. Default: 0.4
            volume_weight: Weight for volume component (0.0-1.0). 
                          If None, loads from ConfigManager. Default: 0.3
            time_weight: Weight for time/recency component (0.0-1.0). 
                        If None, loads from ConfigManager. Default: 0.2
            velocity_weight: Weight for velocity component (0.0-1.0). 
                            If None, loads from ConfigManager. Default: 0.1
            db_session: Optional database session
        
        Note: Weights should sum to approximately 1.0 for meaningful scores.
        """
        # Load configuration from ConfigManager
        try:
            config = ConfigManager()
            self.sentiment_weight = sentiment_weight or config.get_float(
                'processing.issue.priority.sentiment_weight', 0.4
            )
            self.volume_weight = volume_weight or config.get_float(
                'processing.issue.priority.volume_weight', 0.3
            )
            self.time_weight = time_weight or config.get_float(
                'processing.issue.priority.time_weight', 0.2
            )
            self.velocity_weight = velocity_weight or config.get_float(
                'processing.issue.priority.velocity_weight', 0.1
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for priority weights: {e}. Using defaults.")
            self.sentiment_weight = sentiment_weight or 0.4
            self.volume_weight = volume_weight or 0.3
            self.time_weight = time_weight or 0.2
            self.velocity_weight = velocity_weight or 0.1
        
        # Validate weights
        total_weight = self.sentiment_weight + self.volume_weight + self.time_weight + self.velocity_weight
        if abs(total_weight - 1.0) > 0.1:
            logger.warning(f"Priority weights don't sum to 1.0: {total_weight}")
        
        self.db = db_session
        
        logger.info(
            f"IssuePriorityCalculator initialized: "
            f"sentiment={sentiment_weight}, volume={volume_weight}, "
            f"time={time_weight}, velocity={velocity_weight}"
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
    
    def calculate_priority(self, issue: TopicIssue, session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Calculate priority score for an issue (0-100).
        
        Args:
            issue: Issue object
            session: Optional database session
        
        Returns:
            Dictionary with priority_score and priority_band
        """
        if session is None:
            session = self._get_db_session()
            close_session = True
        else:
            close_session = False
        
        try:
            # Calculate component scores
            sentiment_score = self.calculate_sentiment_score(issue)
            volume_score = self.calculate_volume_score(issue)
            time_score = self.calculate_time_score(issue)
            velocity_score = self.calculate_velocity_score(issue)
            
            # Weighted combination
            priority_score = (
                self.sentiment_weight * sentiment_score +
                self.volume_weight * volume_score +
                self.time_weight * time_score +
                self.velocity_weight * velocity_score
            )
            
            # Clamp to 0-100
            priority_score = max(0.0, min(100.0, priority_score))
            
            # Calculate band
            priority_band = self.calculate_priority_band(priority_score)
            
            logger.debug(
                f"Issue {issue.issue_slug}: priority={priority_score:.2f} ({priority_band}) "
                f"(sentiment={sentiment_score:.1f}, volume={volume_score:.1f}, "
                f"time={time_score:.1f}, velocity={velocity_score:.1f})"
            )
            
            return {
                'priority_score': priority_score,
                'priority_band': priority_band,
                'components': {
                    'sentiment': sentiment_score,
                    'volume': volume_score,
                    'time': time_score,
                    'velocity': velocity_score
                }
            }
        
        finally:
            if close_session:
                self._close_db_session(session)
    
    def calculate_sentiment_score(self, issue: TopicIssue) -> float:
        """
        Calculate sentiment component of priority (0-100).
        
        More negative sentiment = higher priority.
        
        Args:
            issue: Issue object
        
        Returns:
            Sentiment score (0-100)
        """
        # Use sentiment_index if available (0-100, where 0 is most negative)
        if issue.sentiment_index is not None:
            # Invert: lower sentiment_index (more negative) = higher priority
            # 0 (most negative) → 100 priority
            # 50 (neutral) → 50 priority
            # 100 (most positive) → 0 priority
            return 100.0 - issue.sentiment_index
        
        # Fallback to weighted_sentiment_score (-1.0 to 1.0)
        if issue.weighted_sentiment_score is not None:
            # Convert -1.0 to 1.0 range to 0-100
            # -1.0 (most negative) → 100 priority
            # 0.0 (neutral) → 50 priority
            # 1.0 (most positive) → 0 priority
            sentiment = issue.weighted_sentiment_score
            return 50.0 - (sentiment * 50.0)
        
        # Default: neutral priority
        return 50.0
    
    def calculate_volume_score(self, issue: TopicIssue) -> float:
        """
        Calculate volume component of priority (0-100).
        
        More mentions = higher priority (with diminishing returns).
        
        Args:
            issue: Issue object
        
        Returns:
            Volume score (0-100)
        """
        mention_count = issue.mention_count or 0
        
        # Logarithmic scaling for diminishing returns
        # 0 mentions → 0 score
        # 3 mentions → ~30 score
        # 10 mentions → ~60 score
        # 50 mentions → ~90 score
        # 100+ mentions → 100 score
        
        if mention_count == 0:
            return 0.0
        
        import math
        # Logarithmic formula: 100 * (1 - e^(-mention_count/20))
        score = 100.0 * (1.0 - math.exp(-mention_count / 20.0))
        
        return min(100.0, score)
    
    def calculate_time_score(self, issue: TopicIssue) -> float:
        """
        Calculate time/recency component of priority (0-100).
        
        More recent = higher priority.
        
        Args:
            issue: Issue object
        
        Returns:
            Time score (0-100)
        """
        # Use last_activity or start_time
        activity_time = issue.last_activity or issue.start_time or issue.created_at
        
        if not activity_time:
            return 50.0  # Default
        
        from datetime import timezone
        
        # Ensure activity_time is offset-aware (UTC) or normalize both to naive
        current_time = datetime.now(timezone.utc)
        
        # Normalize activity_time to UTC if it has tzinfo, otherwise assume UTC
        if activity_time.tzinfo is None:
             # If naive, assume it's UTC (standard practice for DB)
             activity_time = activity_time.replace(tzinfo=timezone.utc)
        
        # Calculate age
        age = current_time - activity_time
        
        # Recent issues get higher priority
        # 0 hours (just now) → 100 score
        # 24 hours → ~70 score
        # 7 days → ~30 score
        # 30 days → ~10 score
        # 90+ days → 0 score
        
        hours_old = age.total_seconds() / 3600
        
        if hours_old <= 1:
            return 100.0
        elif hours_old <= 24:
            # Linear decay from 100 to 70 over 24 hours
            return 100.0 - (hours_old / 24.0 * 30.0)
        elif hours_old <= 168:  # 7 days
            # Linear decay from 70 to 30 over 7 days
            days_old = hours_old / 24.0
            return 70.0 - ((days_old - 1) / 6.0 * 40.0)
        elif hours_old <= 720:  # 30 days
            # Linear decay from 30 to 10 over 30 days
            days_old = hours_old / 24.0
            return 30.0 - ((days_old - 7) / 23.0 * 20.0)
        else:
            # Very old issues
            return max(0.0, 10.0 - ((hours_old - 720) / 24.0 / 60.0 * 10.0))
    
    def calculate_velocity_score(self, issue: TopicIssue) -> float:
        """
        Calculate velocity component of priority (0-100).
        
        Growing issues = higher priority.
        
        Args:
            issue: Issue object
        
        Returns:
            Velocity score (0-100)
        """
        velocity_percent = issue.velocity_percent or 0.0
        
        # Positive velocity (growing) = higher priority
        # Negative velocity (shrinking) = lower priority
        # 0 velocity (stable) = medium priority
        
        # Convert velocity_percent to 0-100 score
        # +100% growth → 100 score
        # 0% growth → 50 score
        # -50% decline → 0 score
        
        if velocity_percent >= 100:
            return 100.0
        elif velocity_percent >= 0:
            # Linear: 0% → 50, 100% → 100
            return 50.0 + (velocity_percent / 100.0 * 50.0)
        else:
            # Linear: -100% → 0, 0% → 50
            return max(0.0, 50.0 + (velocity_percent / 100.0 * 50.0))
    
    def calculate_priority_band(self, priority_score: float) -> str:
        """
        Convert priority score to priority band.
        
        Args:
            priority_score: Priority score (0-100)
        
        Returns:
            Priority band: 'critical', 'high', 'medium', 'low'
        """
        if priority_score >= 80:
            return 'critical'
        elif priority_score >= 60:
            return 'high'
        elif priority_score >= 40:
            return 'medium'
        else:
            return 'low'
    
    def update_issue_priority(self, issue_id: str) -> Optional[float]:
        """
        Calculate and update priority for an issue.
        
        Args:
            issue_id: Issue UUID (string)
        
        Returns:
            Priority score if updated, None if error
        """
        session = self._get_db_session()
        
        try:
            from uuid import UUID
            issue_uuid = UUID(issue_id)
            issue = session.query(TopicIssue).filter(TopicIssue.id == issue_uuid).first()
            
            if not issue:
                logger.warning(f"Issue not found: {issue_id}")
                return None
            
            priority_score = self.calculate_priority(issue, session)
            priority_band = self.calculate_priority_band(priority_score)
            
            issue.priority_score = priority_score
            issue.priority_band = priority_band
            
            session.commit()
            
            logger.info(f"Updated priority for issue {issue.issue_slug}: {priority_score:.2f} ({priority_band})")
            
            return priority_score
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating priority for issue {issue_id}: {e}", exc_info=True)
            return None
        finally:
            self._close_db_session(session)
    
    def update_all_priorities(self, topic_key: Optional[str] = None, limit: Optional[int] = None) -> int:
        """
        Update priorities for all issues (or for a specific topic).
        
        Args:
            topic_key: Optional topic key to filter by
            limit: Optional limit on number of issues to process
        
        Returns:
            Number of issues updated
        """
        session = self._get_db_session()
        updated_count = 0
        
        try:
            query = session.query(TopicIssue).filter(
                TopicIssue.is_archived == False
            )
            
            if topic_key:
                query = query.filter(TopicIssue.topic_key == topic_key)
            
            if limit:
                query = query.limit(limit)
            
            issues = query.all()
            
            logger.info(f"Updating priorities for {len(issues)} issues")
            
            for issue in issues:
                priority_score = self.calculate_priority(issue, session)
                priority_band = self.calculate_priority_band(priority_score)
                
                issue.priority_score = priority_score
                issue.priority_band = priority_band
                updated_count += 1
            
            session.commit()
            
            logger.info(f"Updated priorities for {updated_count} issues")
            
            return updated_count
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating all priorities: {e}", exc_info=True)
            return updated_count
        finally:
            self._close_db_session(session)

