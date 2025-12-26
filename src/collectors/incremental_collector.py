"""
Incremental Collector Wrapper
Wraps existing collectors to enable incremental collection with date tracking
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
import inspect

from src.utils.collection_tracker import get_collection_tracker

logger = logging.getLogger(__name__)


class IncrementalCollector:
    """
    Wrapper for existing collectors that adds incremental collection capability.
    Tracks collection timestamps and passes smart date ranges to collectors.
    """
    
    def __init__(self):
        self.tracker = get_collection_tracker()
        
        # Default settings per source type
        self.source_config = {
            'twitter': {
                'default_lookback_days': 3,   # Twitter: 3 days default
                'max_lookback_days': 14,       # Twitter: Max 2 weeks
                'overlap_hours': 2,            # 2-hour overlap for safety
            },
            'news': {
                'default_lookback_days': 7,   # News: 7 days default
                'max_lookback_days': 30,       # News: Max 1 month
                'overlap_hours': 6,            # 6-hour overlap for news
            },
            'facebook': {
                'default_lookback_days': 3,   # Facebook: 3 days default
                'max_lookback_days': 14,       # Facebook: Max 2 weeks
                'overlap_hours': 2,
            },
            'instagram': {
                'default_lookback_days': 3,   # Instagram: 3 days default
                'max_lookback_days': 14,       # Instagram: Max 2 weeks
                'overlap_hours': 2,
            },
            'tiktok': {
                'default_lookback_days': 3,   # TikTok: 3 days default
                'max_lookback_days': 14,       # TikTok: Max 2 weeks
                'overlap_hours': 2,
            },
            'reddit': {
                'default_lookback_days': 3,   # Reddit: 3 days default
                'max_lookback_days': 14,       # Reddit: Max 2 weeks
                'overlap_hours': 2,
            },
            'radio': {
                'default_lookback_days': 7,   # Radio: 7 days default
                'max_lookback_days': 30,       # Radio: Max 1 month
                'overlap_hours': 6,
            },
            'youtube': {
                'default_lookback_days': 7,   # YouTube: 7 days default
                'max_lookback_days': 30,       # YouTube: Max 1 month
                'overlap_hours': 6,
            },
            'rss': {
                'default_lookback_days': 7,   # RSS: 7 days default
                'max_lookback_days': 30,       # RSS: Max 1 month
                'overlap_hours': 6,
            }
        }
    
    def get_date_range(self, user_id: str, source: str) -> Dict[str, str]:
        """
        Get incremental date range for a source.
        
        Args:
            user_id: User ID
            source: Data source name (lowercase)
            
        Returns:
            Dictionary with date range parameters
        """
        config = self.source_config.get(source, {
            'default_lookback_days': 7,
            'max_lookback_days': 30,
            'overlap_hours': 2
        })
        
        date_range = self.tracker.get_incremental_date_range(
            user_id=user_id,
            source=source,
            default_lookback_days=config['default_lookback_days'],
            max_lookback_days=config['max_lookback_days'],
            overlap_hours=config['overlap_hours']
        )
        
        logger.info(f"📅 Incremental date range for {source}: {date_range['since_date_iso']} to {date_range['until_date_iso']}")
        
        return date_range
    
    def collect_twitter_incremental(self, user_id: str, queries: List[str], 
                                    output_file: Optional[str] = None,
                                    max_items: int = 100,
                                    **kwargs) -> int:
        """
        Collect Twitter data incrementally.
        
        Args:
            user_id: User ID for tracking
            queries: Search queries
            output_file: Output file path
            max_items: Maximum items to collect
            
        Returns:
            Number of records collected
        """
        from src.collectors.collect_twitter_apify import collect_twitter_apify_with_dates
        
        try:
            # Get incremental date range
            date_range = self.get_date_range(user_id, 'twitter')
            
            logger.info(f"🐦 Starting incremental Twitter collection for user {user_id}")
            logger.info(f"   Date range: {date_range['since_date']} to {date_range['until_date']}")
            
            # Call collector with custom date range
            records_count = collect_twitter_apify_with_dates(
                queries=queries,
                output_file=output_file,
                max_items=max_items,
                since_date=date_range['since_date'],
                until_date=date_range['until_date'],
                **kwargs
            )
            
            # Update tracker on success
            if records_count >= 0:  # Even 0 records is a successful collection
                self.tracker.update_collection_time(
                    user_id=user_id,
                    source='twitter',
                    timestamp=datetime.utcnow(),
                    records_collected=records_count,
                    status='success'
                )
                logger.info(f"✅ Twitter collection complete: {records_count} records")
            
            return records_count
            
        except Exception as e:
            logger.error(f"❌ Twitter incremental collection failed: {e}", exc_info=True)
            self.tracker.update_collection_time(
                user_id=user_id,
                source='twitter',
                timestamp=datetime.utcnow(),
                records_collected=0,
                status='failed'
            )
            return 0
    
    def collect_news_incremental(self, user_id: str, queries: List[str],
                                 output_file: Optional[str] = None,
                                 **kwargs) -> int:
        """
        Collect news data incrementally.
        
        Args:
            user_id: User ID for tracking
            queries: Search queries
            output_file: Output file path
            
        Returns:
            Number of records collected
        """
        from src.collectors.collect_news_apify import collect_news_apify_with_dates
        
        try:
            # Get incremental date range
            date_range = self.get_date_range(user_id, 'news')
            
            logger.info(f"📰 Starting incremental news collection for user {user_id}")
            logger.info(f"   Date range: {date_range['since_date']} to {date_range['until_date']}")
            
            # Call collector with custom date range
            records_count = collect_news_apify_with_dates(
                queries=queries,
                output_file=output_file,
                since_date=date_range['since_date_iso'],  # News uses ISO format
                until_date=date_range['until_date_iso'],
                **kwargs
            )
            
            # Update tracker on success
            if records_count >= 0:
                self.tracker.update_collection_time(
                    user_id=user_id,
                    source='news',
                    timestamp=datetime.utcnow(),
                    records_collected=records_count,
                    status='success'
                )
                logger.info(f"✅ News collection complete: {records_count} records")
            
            return records_count
            
        except Exception as e:
            logger.error(f"❌ News incremental collection failed: {e}", exc_info=True)
            self.tracker.update_collection_time(
                user_id=user_id,
                source='news',
                timestamp=datetime.utcnow(),
                records_collected=0,
                status='failed'
            )
            return 0
    
    def collect_facebook_incremental(self, user_id: str, queries: List[str],
                                     output_file: Optional[str] = None,
                                     **kwargs) -> int:
        """Collect Facebook data incrementally"""
        from src.collectors.collect_facebook_apify import collect_facebook_apify
        
        try:
            date_range = self.get_date_range(user_id, 'facebook')
            logger.info(f"📘 Starting incremental Facebook collection for user {user_id}")
            
            # Note: Facebook collector may not support date filters - collect all and rely on dedup
            records_count = collect_facebook_apify(queries=queries, output_file=output_file, **kwargs)
            
            if records_count >= 0:
                self.tracker.update_collection_time(user_id, 'facebook', datetime.utcnow(), records_count, 'success')
                logger.info(f"✅ Facebook collection complete: {records_count} records")
            
            return records_count
        except Exception as e:
            logger.error(f"❌ Facebook collection failed: {e}", exc_info=True)
            self.tracker.update_collection_time(user_id, 'facebook', datetime.utcnow(), 0, 'failed')
            return 0
    
    def collect_instagram_incremental(self, user_id: str, queries: List[str],
                                      output_file: Optional[str] = None,
                                      **kwargs) -> int:
        """Collect Instagram data incrementally"""
        from src.collectors.collect_instagram_apify import collect_instagram_apify
        
        try:
            date_range = self.get_date_range(user_id, 'instagram')
            logger.info(f"📷 Starting incremental Instagram collection for user {user_id}")
            
            records_count = collect_instagram_apify(queries=queries, output_file=output_file, **kwargs)
            
            if records_count >= 0:
                self.tracker.update_collection_time(user_id, 'instagram', datetime.utcnow(), records_count, 'success')
                logger.info(f"✅ Instagram collection complete: {records_count} records")
            
            return records_count
        except Exception as e:
            logger.error(f"❌ Instagram collection failed: {e}", exc_info=True)
            self.tracker.update_collection_time(user_id, 'instagram', datetime.utcnow(), 0, 'failed')
            return 0
    
    def get_collection_stats(self, user_id: str) -> Dict[str, Any]:
        """Get collection statistics for a user"""
        return self.tracker.get_collection_stats(user_id)


# Global singleton
_incremental_collector = None

def get_incremental_collector() -> IncrementalCollector:
    """Get the global incremental collector instance"""
    global _incremental_collector
    if _incremental_collector is None:
        _incremental_collector = IncrementalCollector()
    return _incremental_collector








