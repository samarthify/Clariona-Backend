import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import re
from difflib import SequenceMatcher
from datetime import datetime, timedelta

logger = logging.getLogger('DeduplicationService')

class DeduplicationService:
    """
    Service for deduplicating sentiment data by comparing newly collected data
    against existing data in the database.
    """
    
    def __init__(self):
        # Load similarity threshold from ConfigManager
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            self.similarity_threshold = config.get_float("deduplication.similarity_threshold", 0.85)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load ConfigManager for similarity threshold, using default 0.85: {e}")
            self.similarity_threshold = 0.85
        self.text_fields = ['text', 'content', 'title', 'description']
        
    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent duplicate detection"""
        if not text or pd.isna(text):
            return ""
        
        # Convert to lowercase
        text = str(text).lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,?!-]', '', text)
        
        return text
    
    def is_similar_text(self, text1: str, text2: str, threshold: Optional[float] = None) -> bool:
        """Check if two texts are similar using sequence matcher"""
        if threshold is None:
            threshold = self.similarity_threshold
            
        if pd.isna(text1) or pd.isna(text2):
            return False
        
        # For very short texts, require exact match
        if len(text1) < 10 or len(text2) < 10:
            return text1 == text2
        
        # For longer texts, use sequence matcher
        similarity = SequenceMatcher(None, text1, text2).ratio()
        return similarity >= threshold
    
    def get_text_content(self, record: Dict[str, Any]) -> str:
        """Extract the main text content from a record"""
        for field in self.text_fields:
            if field in record and record[field] and not pd.isna(record[field]):
                return str(record[field])
        return ""
    
    def find_existing_duplicates(self, new_records: List[Dict[str, Any]], db: Session, user_id: str) -> Dict[str, List[int]]:
        """
        Find existing duplicates in the database for the new records.
        FAST VERSION: Only checks text similarity, no URL or date matching.
        
        Args:
            new_records: List of new records to check
            db: Database session
            user_id: User ID to filter by
            
        Returns:
            Dictionary mapping new record index to list of existing duplicate entry_ids
        """
        import logging
        from src.api.models import SentimentData
        
        logger = logging.getLogger(__name__)
        duplicates_map: Dict[str, List[int]] = {}
        
        logger.info(f"🔍 Starting deduplication for {len(new_records)} new records...")
        
        # Get all existing records for this user in one query (much faster)
        logger.info(f"📊 Fetching existing records from database for user {user_id}...")
        
        # Convert user_id to UUID if it's a string
        from uuid import UUID
        if isinstance(user_id, str):
            try:
                user_id_uuid = UUID(user_id)
            except (ValueError, AttributeError):
                logger.error(f"Invalid user_id format: {user_id}")
                return duplicates_map
        else:
            user_id_uuid = user_id
        
        # Optimize query: Only fetch entry_id and text fields we need for deduplication
        # This is much faster than loading all columns
        import time
        query_start_time = time.time()
        total_query_duration = 0  # Initialize for scope
        try:
            logger.info("📊 Executing optimized query (entry_id + text fields only)...")
            logger.info(f"📊 Query filter: user_id == {user_id_uuid}")
            logger.info("📊 Starting database query execution...")
            
            # First, let's check how many records exist (fast count query)
            count_start = time.time()
            record_count = db.query(SentimentData).filter(
                SentimentData.user_id == user_id_uuid
            ).count()
            count_duration = time.time() - count_start
            logger.info(f"📊 Count query completed in {count_duration:.2f}s: {record_count} total records for this user")
            
            if record_count > 100000:
                logger.warning(f"⚠️ WARNING: Very large number of records ({record_count}). This query may take a long time!")
            
            # Now execute the actual query
            query_exec_start = time.time()
            logger.info("📊 Executing main query to fetch records...")
            existing_records = db.query(
                SentimentData.entry_id,
                SentimentData.text,
                SentimentData.content,
                SentimentData.title,
                SentimentData.description
            ).filter(
                SentimentData.user_id == user_id_uuid
            ).all()
            query_exec_duration = time.time() - query_exec_start
            total_query_duration = time.time() - query_start_time
            logger.info(f"📊 Query execution completed in {query_exec_duration:.2f}s (total: {total_query_duration:.2f}s)")
            logger.info(f"📊 Found {len(existing_records)} existing records in database")
        except Exception as e:
            query_duration = time.time() - query_start_time
            total_query_duration = query_duration
            logger.error(f"❌ Error fetching existing records after {query_duration:.2f}s: {e}", exc_info=True)
            # Fallback to full query if optimized query fails
            logger.warning("⚠️ Falling back to full record query...")
            fallback_start = time.time()
            existing_records = db.query(SentimentData).filter(
                SentimentData.user_id == user_id_uuid
            ).all()
            fallback_duration = time.time() - fallback_start
            total_query_duration += fallback_duration
            logger.info(f"📊 Found {len(existing_records)} existing records in database (fallback, took {fallback_duration:.2f}s)")
        
        # Create a lookup map of normalized text -> entry_ids for fast comparison
        map_build_start = time.time()
        logger.info("🔄 Building text lookup map from existing records...")
        existing_text_map = {}
        record_count = 0
        for record in existing_records:
            record_count += 1
            if record_count % 1000 == 0:  # Log progress every 1000 records
                logger.info(f"🔄 Processed {record_count}/{len(existing_records)} existing records...")
            
            # Handle both Row objects (from optimized query) and model objects (from fallback)
            # SQLAlchemy Row objects support both attribute and index access
            try:
                # Try attribute access first (works for both Row objects and model objects)
                entry_id = record.entry_id
                record_dict = {
                    'text': getattr(record, 'text', None),
                    'content': getattr(record, 'content', None),
                    'title': getattr(record, 'title', None),
                    'description': getattr(record, 'description', None)
                }
            except AttributeError:
                # Fallback to index access for tuple-like results
                entry_id = record[0]
                record_dict = {
                    'text': record[1] if len(record) > 1 else None,
                    'content': record[2] if len(record) > 2 else None,
                    'title': record[3] if len(record) > 3 else None,
                    'description': record[4] if len(record) > 4 else None
                }
            
            text_content = self.get_text_content(record_dict)
            if text_content:
                normalized_text = self.normalize_text(text_content)
                if normalized_text:
                    if normalized_text not in existing_text_map:
                        existing_text_map[normalized_text] = []
                    existing_text_map[normalized_text].append(entry_id)
        
        map_build_duration = time.time() - map_build_start
        logger.info(f"🔄 Built lookup map with {len(existing_text_map)} unique text entries in {map_build_duration:.2f}s")
        
        # Check each new record against existing ones
        comparison_start = time.time()
        logger.info("🔍 Comparing new records against existing ones...")
        for i, new_record in enumerate(new_records):
            if i % 100 == 0:  # Log progress every 100 records
                logger.info(f"🔍 Processed {i}/{len(new_records)} records...")
                
            text_content = self.get_text_content(new_record)
            if not text_content:
                continue
                
            normalized_text = self.normalize_text(text_content)
            if not normalized_text:
                continue
            
            # Check for exact matches first
            if normalized_text in existing_text_map:
                duplicates_map[i] = existing_text_map[normalized_text]
                continue
            
            # Check for similar content using text similarity only
            # COMMENTED OUT FOR SIMPLER DEDUPLICATION - ONLY EXACT MATCHES
            # text_length = len(normalized_text)
            # min_length = int(text_length * 0.8)
            # max_length = int(text_length * 1.2)
            # 
            # similar_matches = []
            # for existing_normalized, entry_ids in existing_text_map.items():
            #     if (min_length <= len(existing_normalized) <= max_length and 
            #         self.is_similar_text(normalized_text, existing_normalized)):
            #         similar_matches.extend(entry_ids)
            # 
            # if similar_matches:
            #     duplicates_map[i] = similar_matches
        
        comparison_duration = time.time() - comparison_start
        logger.info(f"✅ Deduplication complete! Found {len(duplicates_map)} duplicate records out of {len(new_records)} new records")
        logger.info(f"⏱️ Timing breakdown: Query={total_query_duration:.2f}s, Map Build={map_build_duration:.2f}s, Comparison={comparison_duration:.2f}s")
        return duplicates_map
    
    def deduplicate_new_data(self, new_records: List[Dict[str, Any]], db: Session, user_id: str) -> Dict[str, Any]:
        """
        Deduplicate new records against existing database records.
        
        Args:
            new_records: List of new records to deduplicate
            db: Database session
            user_id: User ID to filter by
            
        Returns:
            Dictionary with deduplication results:
            - unique_records: List of records that are not duplicates
            - duplicate_records: List of records that are duplicates
            - duplicate_map: Mapping of new record indices to existing duplicate IDs
            - stats: Deduplication statistics
        """
        logger.info(f"Starting deduplication of {len(new_records)} new records for user {user_id}")
        
        if not new_records:
            return {
                'unique_records': [],
                'duplicate_records': [],
                'duplicate_map': {},
                'stats': {'total': 0, 'unique': 0, 'duplicates': 0}
            }
        
        # Find existing duplicates
        duplicate_map = self.find_existing_duplicates(new_records, db, user_id)
        
        # Separate unique and duplicate records
        unique_records = []
        duplicate_records = []
        
        for i, record in enumerate(new_records):
            if i in duplicate_map:
                duplicate_records.append(record)
            else:
                unique_records.append(record)
        
        # Additional deduplication within new records (remove internal duplicates)
        internal_duplicates = self._remove_internal_duplicates(unique_records)
        final_unique = internal_duplicates['unique']
        internal_duplicate_count = internal_duplicates['duplicate_count']
        
        stats = {
            'total': len(new_records),
            'unique': len(final_unique),
            'duplicates': len(duplicate_records) + internal_duplicate_count,
            'external_duplicates': len(duplicate_records),
            'internal_duplicates': internal_duplicate_count
        }
        
        logger.info(f"Deduplication completed: {stats['unique']} unique, {stats['duplicates']} duplicates")
        
        return {
            'unique_records': final_unique,
            'duplicate_records': duplicate_records,
            'duplicate_map': duplicate_map,
            'stats': stats
        }
    
    def _remove_internal_duplicates(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Remove duplicates within the new records themselves"""
        if len(records) <= 1:
            return {'unique': records, 'duplicate_count': 0}
        
        seen_texts = set()
        unique_records = []
        duplicate_count = 0
        
        for record in records:
            text_content = self.get_text_content(record)
            normalized_text = self.normalize_text(text_content)
            
            if normalized_text and normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                unique_records.append(record)
            else:
                duplicate_count += 1
        
        return {'unique': unique_records, 'duplicate_count': duplicate_count}
    
    def get_deduplication_summary(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable summary of deduplication results"""
        stats = results['stats']
        
        summary = f"""
Deduplication Summary:
=====================
Total Records: {stats['total']}
Unique Records: {stats['unique']}
Duplicate Records: {stats['duplicates']}
  - External Duplicates (vs existing DB): {stats['external_duplicates']}
  - Internal Duplicates (within new data): {stats['internal_duplicates']}
Duplicate Rate: {(stats['duplicates'] / stats['total'] * 100):.1f}%
        """.strip()
        
        return summary
