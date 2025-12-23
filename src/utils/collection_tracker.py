"""
Collection Tracker - Tracks last successful collection timestamps per source
Enables incremental data collection to avoid re-collecting the same data
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from threading import Lock

logger = logging.getLogger(__name__)


class CollectionTracker:
    """
    Tracks collection timestamps and metadata to enable incremental collection.
    Prevents wasteful re-collection of the same data across cycles.
    """
    
    def __init__(self, tracker_file: str = "data/collection_tracker.json"):
        """
        Initialize the collection tracker.
        
        Args:
            tracker_file: Path to the JSON file storing collection timestamps
        """
        self.tracker_file = Path(tracker_file)
        self.lock = Lock()
        self._ensure_tracker_file()
        
    def _ensure_tracker_file(self):
        """Ensure the tracker file and directory exist"""
        try:
            self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.tracker_file.exists():
                self._save_tracker_data({})
                logger.info(f"Created new collection tracker file: {self.tracker_file}")
        except Exception as e:
            logger.error(f"Failed to create tracker file: {e}")
    
    def _load_tracker_data(self) -> Dict[str, Any]:
        """Load tracker data from file"""
        try:
            if self.tracker_file.exists():
                with open(self.tracker_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load tracker data: {e}")
            return {}
    
    def _save_tracker_data(self, data: Dict[str, Any]):
        """Save tracker data to file"""
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save tracker data: {e}")
    
    def get_last_collection_time(self, user_id: str, source: str) -> Optional[datetime]:
        """
        Get the last successful collection timestamp for a user/source combination.
        
        Args:
            user_id: User ID
            source: Data source name (e.g., 'twitter', 'news', 'facebook')
            
        Returns:
            datetime of last collection or None if never collected
        """
        with self.lock:
            data = self._load_tracker_data()
            
            user_key = str(user_id)
            if user_key not in data:
                return None
            
            if source not in data[user_key]:
                return None
            
            timestamp_str = data[user_key][source].get('last_collection_time')
            if timestamp_str:
                try:
                    return datetime.fromisoformat(timestamp_str)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid timestamp format for {user_id}/{source}: {timestamp_str}")
                    return None
            
            return None
    
    def update_collection_time(self, user_id: str, source: str, 
                              timestamp: Optional[datetime] = None,
                              records_collected: int = 0,
                              status: str = "success") -> bool:
        """
        Update the last collection timestamp for a user/source.
        
        Args:
            user_id: User ID
            source: Data source name
            timestamp: Collection timestamp (defaults to now)
            records_collected: Number of records collected
            status: Collection status ('success', 'partial', 'failed')
            
        Returns:
            True if update successful, False otherwise
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.lock:
            try:
                data = self._load_tracker_data()
                
                user_key = str(user_id)
                if user_key not in data:
                    data[user_key] = {}
                
                data[user_key][source] = {
                    'last_collection_time': timestamp.isoformat(),
                    'records_collected': records_collected,
                    'status': status,
                    'updated_at': datetime.utcnow().isoformat()
                }
                
                self._save_tracker_data(data)
                logger.info(f"Updated collection tracker for {user_id}/{source}: {records_collected} records at {timestamp.isoformat()}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to update collection time: {e}")
                return False
    
    def get_incremental_date_range(self, user_id: str, source: str, 
                                   default_lookback_days: int = 7,
                                   max_lookback_days: int = 30,
                                   overlap_hours: int = 2) -> Dict[str, str]:
        """
        Get the optimal date range for incremental collection.
        
        Args:
            user_id: User ID
            source: Data source name
            default_lookback_days: Default lookback if no previous collection
            max_lookback_days: Maximum lookback period
            overlap_hours: Hours to overlap with previous collection (for safety)
            
        Returns:
            Dictionary with 'since_date' and 'until_date' strings
        """
        last_collection = self.get_last_collection_time(user_id, source)
        until_date = datetime.utcnow()
        
        if last_collection is None:
            # First collection: use default lookback
            since_date = until_date - timedelta(days=default_lookback_days)
            logger.info(f"First collection for {user_id}/{source}: using {default_lookback_days} day lookback")
        else:
            # Incremental collection: start from last collection minus overlap
            since_date = last_collection - timedelta(hours=overlap_hours)
            
            # Ensure we don't go back too far (safety limit)
            max_lookback = until_date - timedelta(days=max_lookback_days)
            if since_date < max_lookback:
                since_date = max_lookback
                logger.warning(f"Last collection for {user_id}/{source} was too old, limiting to {max_lookback_days} days")
            else:
                logger.info(f"Incremental collection for {user_id}/{source}: from {since_date.isoformat()} ({overlap_hours}h overlap)")
        
        return {
            'since_date': since_date.strftime("%Y-%m-%d_%H:%M:%S_UTC"),
            'until_date': until_date.strftime("%Y-%m-%d_%H:%M:%S_UTC"),
            'since_date_iso': since_date.isoformat(),
            'until_date_iso': until_date.isoformat()
        }
    
    def get_collection_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get collection statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with collection stats per source
        """
        with self.lock:
            data = self._load_tracker_data()
            user_key = str(user_id)
            
            if user_key not in data:
                return {}
            
            stats = {}
            for source, info in data[user_key].items():
                last_time = info.get('last_collection_time')
                if last_time:
                    try:
                        dt = datetime.fromisoformat(last_time)
                        hours_ago = (datetime.utcnow() - dt).total_seconds() / 3600
                        stats[source] = {
                            'last_collection': last_time,
                            'hours_ago': round(hours_ago, 2),
                            'records_collected': info.get('records_collected', 0),
                            'status': info.get('status', 'unknown')
                        }
                    except (ValueError, TypeError):
                        pass
            
            return stats
    
    def reset_source(self, user_id: str, source: str) -> bool:
        """
        Reset tracking for a specific source (useful for troubleshooting).
        
        Args:
            user_id: User ID
            source: Data source name
            
        Returns:
            True if reset successful
        """
        with self.lock:
            try:
                data = self._load_tracker_data()
                user_key = str(user_id)
                
                if user_key in data and source in data[user_key]:
                    del data[user_key][source]
                    self._save_tracker_data(data)
                    logger.info(f"Reset collection tracker for {user_id}/{source}")
                    return True
                
                return False
                
            except Exception as e:
                logger.error(f"Failed to reset source: {e}")
                return False
    
    def reset_user(self, user_id: str) -> bool:
        """
        Reset all tracking for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if reset successful
        """
        with self.lock:
            try:
                data = self._load_tracker_data()
                user_key = str(user_id)
                
                if user_key in data:
                    del data[user_key]
                    self._save_tracker_data(data)
                    logger.info(f"Reset all collection tracking for user {user_id}")
                    return True
                
                return False
                
            except Exception as e:
                logger.error(f"Failed to reset user: {e}")
                return False


# Global singleton instance
_tracker_instance = None
_tracker_lock = Lock()


def get_collection_tracker() -> CollectionTracker:
    """Get the global collection tracker instance"""
    global _tracker_instance
    
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = CollectionTracker()
    
    return _tracker_instance








