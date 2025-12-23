"""
Centralized Data Cache System for Sentiment Analysis API
Provides efficient data access and caching for all endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from threading import Lock
import json

from sqlalchemy.orm import Session
from sqlalchemy import text, or_

from . import models
from .database import get_db

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Represents a cached data entry with metadata"""
    data: Any
    timestamp: datetime
    ttl_minutes: int = 15
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.now() > (self.timestamp + timedelta(minutes=self.ttl_minutes))

@dataclass
class DataCacheStats:
    """Statistics about cached data"""
    total_records: int = 0
    last_updated: Optional[datetime] = None
    ai_processed_count: int = 0
    platforms: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    date_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)

class SentimentDataCache:
    """Centralized cache for sentiment data with intelligent refresh"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = DataCacheStats()
        
        # Cache keys
        self.ALL_DATA_KEY = "all_sentiment_data"
        self.AI_PROCESSED_KEY = "ai_processed_data"
        self.STATS_KEY = "data_stats"
        
    def _load_all_data_from_db(self, db: Session) -> List[models.SentimentData]:
        """Load all sentiment data from database"""
        try:
            logger.info("Loading all sentiment data from database...")
            results = db.query(models.SentimentData).order_by(models.SentimentData.date.desc()).all()
            logger.info(f"Loaded {len(results)} records from database")
            return results
        except Exception as e:
            logger.error(f"Error loading data from database: {e}")
            return []
    
    def _load_ai_processed_data_from_db(self, db: Session) -> List[models.SentimentData]:
        """Load only AI processed data (with justification)"""
        try:
            logger.info("Loading AI processed data from database...")
            results = db.query(models.SentimentData)\
                        .filter(models.SentimentData.sentiment_justification.isnot(None))\
                        .filter(models.SentimentData.sentiment_justification != "")\
                        .order_by(models.SentimentData.date.desc()).all()
            logger.info(f"Loaded {len(results)} AI processed records from database")
            return results
        except Exception as e:
            logger.error(f"Error loading AI processed data: {e}")
            return []
    
    def _generate_stats(self, data: List[models.SentimentData]) -> DataCacheStats:
        """Generate statistics from data"""
        if not data:
            return DataCacheStats()
        
        platforms = list(set(record.platform for record in data if record.platform))
        sources = list(set(record.source_name for record in data if record.source_name))
        
        dates = [record.date for record in data if record.date]
        date_range = (min(dates), max(dates)) if dates else (None, None)
        
        ai_processed_count = sum(1 for record in data 
                               if record.sentiment_justification and record.sentiment_justification.strip())
        
        return DataCacheStats(
            total_records=len(data),
            last_updated=datetime.now(),
            ai_processed_count=ai_processed_count,
            platforms=platforms,
            sources=sources,
            date_range=date_range
        )
    
    def refresh_cache(self, db: Session, force: bool = False) -> bool:
        """Refresh cache data from database"""
        with self._lock:
            try:
                # Check if refresh is needed
                if not force:
                    all_data_entry = self._cache.get(self.ALL_DATA_KEY)
                    if all_data_entry and not all_data_entry.is_expired():
                        logger.debug("Cache is still fresh, skipping refresh")
                        return True
                
                logger.info("Refreshing sentiment data cache...")
                start_time = datetime.now()
                
                # Load all data
                all_data = self._load_all_data_from_db(db)
                if not all_data:
                    logger.warning("No data loaded from database")
                    return False
                
                # Load AI processed data subset
                ai_processed_data = [record for record in all_data 
                                   if record.sentiment_justification and record.sentiment_justification.strip()]
                
                # Generate statistics
                stats = self._generate_stats(all_data)
                
                # Update cache
                self._cache[self.ALL_DATA_KEY] = CacheEntry(
                    data=all_data, 
                    timestamp=datetime.now(),
                    ttl_minutes=15
                )
                
                self._cache[self.AI_PROCESSED_KEY] = CacheEntry(
                    data=ai_processed_data,
                    timestamp=datetime.now(),
                    ttl_minutes=15
                )
                
                self._cache[self.STATS_KEY] = CacheEntry(
                    data=stats,
                    timestamp=datetime.now(),
                    ttl_minutes=30
                )
                
                self._stats = stats
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Cache refresh completed in {duration:.2f}s - {len(all_data)} total, {len(ai_processed_data)} AI processed")
                
                return True
                
            except Exception as e:
                logger.error(f"Error refreshing cache: {e}")
                return False
    
    def get_all_data(self, db: Session, force_refresh: bool = False) -> List[models.SentimentData]:
        """Get all sentiment data with caching"""
        entry = self._cache.get(self.ALL_DATA_KEY)
        
        if not entry or entry.is_expired() or force_refresh:
            if not self.refresh_cache(db, force=force_refresh):
                # Fallback to direct database query
                logger.warning("Cache refresh failed, falling back to direct database query")
                return self._load_all_data_from_db(db)
            entry = self._cache.get(self.ALL_DATA_KEY)
        
        return entry.data if entry else []
    
    def get_ai_processed_data(self, db: Session, force_refresh: bool = False) -> List[models.SentimentData]:
        """Get AI processed data with caching"""
        entry = self._cache.get(self.AI_PROCESSED_KEY)
        
        if not entry or entry.is_expired() or force_refresh:
            if not self.refresh_cache(db, force=force_refresh):
                # Fallback to direct database query
                logger.warning("Cache refresh failed, falling back to direct database query")
                return self._load_ai_processed_data_from_db(db)
            entry = self._cache.get(self.AI_PROCESSED_KEY)
        
        return entry.data if entry else []
    
    def get_stats(self, db: Session) -> DataCacheStats:
        """Get data statistics"""
        entry = self._cache.get(self.STATS_KEY)
        
        if not entry or entry.is_expired():
            self.refresh_cache(db)
            entry = self._cache.get(self.STATS_KEY)
        
        return entry.data if entry else DataCacheStats()
    
    def filter_by_target_config(self, data: List[models.SentimentData], 
                               target_config: models.TargetIndividualConfiguration) -> List[models.SentimentData]:
        """Filter data by target individual configuration - matches if ANY word from search terms is found"""
        if not target_config or not data:
            return data
        
        search_terms = [target_config.individual_name] + target_config.query_variations
        
        # Extract all individual words from search terms (filtering out very short words)
        search_words = set()
        for term in search_terms:
            if term and term.strip():
                # Split by whitespace and filter words that are at least 3 characters
                words = [word.strip().lower() for word in term.split() if len(word.strip()) >= 3]
                search_words.update(words)
        
        logger.info(f"Searching for any of these words: {search_words}")
        
        filtered_data = []
        for record in data:
            text_content = ((record.text or "") + " " + (record.title or "") + " " + (record.content or "")).lower()
            
            # Check if any search word appears in the content
            for word in search_words:
                if word in text_content:
                    filtered_data.append(record)
                    break
        
        logger.info(f"Filtered {len(data)} records to {len(filtered_data)} for target: {target_config.individual_name}")
        return filtered_data
    
    def filter_by_platform_keywords(self, data: List[models.SentimentData], 
                                   keywords: List[str], 
                                   exclude_keywords: List[str] = None) -> List[models.SentimentData]:
        """Filter data by platform/source keywords"""
        if not keywords or not data:
            return data
        
        filtered_data = []
        exclude_keywords = exclude_keywords or []
        
        for record in data:
            source_text = (record.source_name or "") + (record.source or "") + (record.platform or "")
            source_text_lower = source_text.lower()
            
            # Check for inclusion keywords
            has_keyword = any(keyword.lower() in source_text_lower for keyword in keywords)
            
            # Check for exclusion keywords
            has_exclude = any(exclude.lower() in source_text_lower for exclude in exclude_keywords)
            
            if has_keyword and not has_exclude:
                filtered_data.append(record)
        
        logger.info(f"Platform filtered {len(data)} records to {len(filtered_data)}")
        return filtered_data
    
    def deduplicate_data(self, data: List[models.SentimentData]) -> List[models.SentimentData]:
        """Remove duplicate records based on content similarity"""
        if not data:
            return data
        
        # TEMPORARILY DISABLED - returning all records without deduplication
        logger.info(f"Deduplication DISABLED - returning all {len(data)} records")
        return data
        
        # This is a simplified deduplication - could be enhanced
        # seen_content = set()
        # unique_data = []
        # 
        # for record in data:
        #     content_key = (record.title or "") + (record.url or "")
        #     content_hash = hash(content_key.lower())
        #     
        #     if content_hash not in seen_content:
        #         seen_content.add(content_hash)
        #         unique_data.append(record)
        # 
        # logger.info(f"Deduplicated {len(data)} records to {len(unique_data)}")
        # return unique_data
    
    def clear_cache(self):
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
            self._stats = DataCacheStats()
            logger.info("Cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about current cache state"""
        with self._lock:
            info = {
                "cached_entries": len(self._cache),
                "stats": {
                    "total_records": self._stats.total_records,
                    "last_updated": self._stats.last_updated.isoformat() if self._stats.last_updated else None,
                    "ai_processed_count": self._stats.ai_processed_count,
                    "platforms_count": len(self._stats.platforms),
                    "sources_count": len(self._stats.sources)
                },
                "entries": {}
            }
            
            for key, entry in self._cache.items():
                info["entries"][key] = {
                    "timestamp": entry.timestamp.isoformat(),
                    "expired": entry.is_expired(),
                    "ttl_minutes": entry.ttl_minutes,
                    "data_size": len(entry.data) if isinstance(entry.data, list) else 1
                }
            
            return info

# Global cache instance
sentiment_cache = SentimentDataCache()

def get_cached_data(data_type: str = "ai_processed", db: Session = None, 
                   force_refresh: bool = False) -> List[models.SentimentData]:
    """Convenience function to get cached data"""
    if db is None:
        # This should be called from an endpoint with dependency injection
        raise ValueError("Database session is required")
    
    if data_type == "all":
        return sentiment_cache.get_all_data(db, force_refresh)
    elif data_type == "ai_processed":
        return sentiment_cache.get_ai_processed_data(db, force_refresh)
    else:
        raise ValueError(f"Unknown data type: {data_type}")

def invalidate_cache():
    """Invalidate cache (to be called when new data is added)"""
    sentiment_cache.clear_cache()
    logger.info("Cache invalidated due to new data")

