"""
Issue Lifecycle Manager - Manages issue states and transitions.

Week 4: Automatic issue lifecycle management.
"""

# Standard library imports
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Third-party imports
from sqlalchemy.orm import Session
from sqlalchemy import func

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - database
from api.database import SessionLocal
from api.models import TopicIssue, IssueMention

# Module-level setup
logger = get_logger(__name__)


class IssueLifecycleManager:
    """
    Manages issue lifecycle states and automatic transitions.
    
    States:
    - emerging: New issue (< 3 mentions or < 24 hours)
    - active: Growing issue (3+ mentions, increasing)
    - escalated: High priority (negative sentiment, high volume)
    - stabilizing: Slowing down (decreasing mentions)
    - resolved: No new mentions (7+ days inactive)
    - archived: Manually archived
    
    Week 4: Automatic state management for issues.
    """
    
    def __init__(self,
                 emerging_threshold_hours: Optional[int] = None,
                 resolved_threshold_days: Optional[int] = None,
                 db_session: Optional[Session] = None):
        """
        Initialize lifecycle manager.
        
        Args:
            emerging_threshold_hours: Hours before issue can transition from emerging. 
                                     If None, loads from ConfigManager. Default: 24
            resolved_threshold_days: Days of inactivity before marking resolved. 
                                    If None, loads from ConfigManager. Default: 7
            db_session: Optional database session
        """
        # Load configuration from ConfigManager
        try:
            config = ConfigManager()
            self.emerging_threshold_hours = emerging_threshold_hours or config.get_int(
                'processing.issue.lifecycle.emerging_threshold_hours', 24
            )
            self.resolved_threshold_days = resolved_threshold_days or config.get_int(
                'processing.issue.lifecycle.resolved_threshold_days', 7
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for lifecycle settings: {e}. Using defaults.")
            self.emerging_threshold_hours = emerging_threshold_hours or 24
            self.resolved_threshold_days = resolved_threshold_days or 7
        
        self.db = db_session
        
        logger.info(
            f"IssueLifecycleManager initialized: "
            f"emerging_threshold={emerging_threshold_hours}h, "
            f"resolved_threshold={resolved_threshold_days}d"
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
    
    def update_lifecycle(self, issue_id: str) -> Optional[str]:
        """
        Update issue lifecycle state based on current metrics.
        
        Args:
            issue_id: Issue UUID (string)
        
        Returns:
            New state if changed, None if unchanged
        """
        session = self._get_db_session()
        
        try:
            from uuid import UUID
            issue_uuid = UUID(issue_id)
            issue = session.query(TopicIssue).filter(TopicIssue.id == issue_uuid).first()
            
            if not issue:
                logger.warning(f"Issue not found: {issue_id}")
                return None
            
            old_state = issue.state
            new_state = self.calculate_state(issue, session)
            
            if new_state != old_state:
                self.transition_state(issue, new_state, session)
                session.commit()
                logger.info(f"Issue {issue.issue_slug}: {old_state} → {new_state}")
                return new_state
            else:
                return None
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating lifecycle for issue {issue_id}: {e}", exc_info=True)
            return None
        finally:
            self._close_db_session(session)
    
    def calculate_state(self, issue: TopicIssue, session: Session) -> str:
        """
        Calculate appropriate state for an issue based on metrics.
        
        Args:
            issue: Issue object
            session: Database session
        
        Returns:
            State string
        """
        # Don't change archived issues
        if issue.is_archived or issue.state == 'archived':
            return 'archived'
        
        # Calculate metrics
        age = datetime.now() - (issue.start_time or issue.created_at)
        time_since_activity = datetime.now() - (issue.last_activity or issue.created_at)
        
        mention_count = issue.mention_count
        velocity = issue.velocity_percent or 0.0
        
        # Get sentiment metrics
        sentiment_index = issue.sentiment_index or 50.0  # Default to neutral
        weighted_sentiment = issue.weighted_sentiment_score or 0.0
        
        # State logic
        
        # 1. Resolved: No activity for threshold days
        if time_since_activity >= timedelta(days=self.resolved_threshold_days):
            return 'resolved'
        
        # 2. Emerging: New issue (< threshold hours OR < 3 mentions)
        if (age < timedelta(hours=self.emerging_threshold_hours) or 
            mention_count < 3):
            return 'emerging'
        
        # 3. Escalated: High negative sentiment + high volume
        if (sentiment_index < 30.0 and  # Very negative
            mention_count >= 10 and  # High volume
            velocity > 0):  # Growing
            return 'escalated'
        
        # 4. Stabilizing: Decreasing velocity (negative growth)
        if velocity < -20.0 and mention_count >= 5:
            return 'stabilizing'
        
        # 5. Active: Default for growing issues
        if mention_count >= 3 and velocity >= 0:
            return 'active'
        
        # Default: emerging
        return 'emerging'
    
    def transition_state(self, issue: TopicIssue, new_state: str, session: Session):
        """
        Handle state transition with side effects.
        
        Args:
            issue: Issue object
            new_state: New state to transition to
            session: Database session
        """
        old_state = issue.state
        
        # Update state
        issue.state = new_state
        issue.last_activity = datetime.now()
        
        # Handle state-specific side effects
        if new_state == 'resolved':
            issue.resolved_at = datetime.now()
            issue.is_active = False
        elif new_state == 'archived':
            issue.is_active = False
            issue.is_archived = True
        elif new_state in ['active', 'escalated']:
            # Reactivate if was resolved
            if old_state == 'resolved':
                issue.resolved_at = None
                issue.is_active = True
        
        # Log transition
        logger.debug(
            f"Issue {issue.issue_slug}: {old_state} → {new_state} "
            f"(mentions: {issue.mention_count}, sentiment: {issue.sentiment_index})"
        )
    
    def update_all_issues(self, topic_key: Optional[str] = None, limit: Optional[int] = None):
        """
        Update lifecycle for all issues (or for a specific topic).
        
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
            
            logger.info(f"Updating lifecycle for {len(issues)} issues")
            
            for issue in issues:
                old_state = issue.state
                new_state = self.calculate_state(issue, session)
                
                if new_state != old_state:
                    self.transition_state(issue, new_state, session)
                    updated_count += 1
            
            session.commit()
            
            logger.info(f"Updated lifecycle for {updated_count} issues")
            
            return updated_count
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating all issues: {e}", exc_info=True)
            return updated_count
        finally:
            self._close_db_session(session)
    
    def get_state_summary(self, topic_key: Optional[str] = None) -> Dict[str, int]:
        """
        Get summary of issue states.
        
        Args:
            topic_key: Optional topic key to filter by
        
        Returns:
            Dictionary mapping state to count
        """
        session = self._get_db_session()
        
        try:
            query = session.query(TopicIssue.state, func.count(TopicIssue.id)).group_by(TopicIssue.state)
            
            if topic_key:
                query = query.filter(TopicIssue.topic_key == topic_key)
            
            results = query.all()
            
            summary = {state: count for state, count in results}
            
            # Ensure all states are present
            all_states = ['emerging', 'active', 'escalated', 'stabilizing', 'resolved', 'archived']
            for state in all_states:
                if state not in summary:
                    summary[state] = 0
            
            return summary
        
        finally:
            self._close_db_session(session)

