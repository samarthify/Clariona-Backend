"""
DataIngestor - Unified data ingestion service for streaming collectors.

This module provides the `DataIngestor` class which handles:
1. Normalization: Cleans raw data (NaN handling, type safety, field fallbacks).
2. Upsert: Performs INSERT or UPDATE on conflict, preserving analysis fields.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.api.models import SentimentData
from src.utils.common import safe_float, safe_int, parse_datetime

logger = logging.getLogger(__name__)

# Fields that should be updated on conflict (engagement metrics)
UPDATABLE_FIELDS = [
    'likes', 'retweets', 'comments',
    'direct_reach', 'cumulative_reach', 'domain_reach',
    'user_avatar', 'user_name', 'user_handle',
]

# Fields that should NEVER be overwritten if already set (analysis results)
PROTECTED_FIELDS = [
    'sentiment_label', 'sentiment_score', 'sentiment_justification',
    'emotion_label', 'emotion_score', 'emotion_distribution',
    'location_label', 'location_confidence',
    'issue_label', 'issue_slug', 'issue_confidence', 'issue_keywords',
    'processing_status', 'processing_completed_at',
]


class DataIngestor:
    """
    Handles normalization and upsert of raw collected data into SentimentData table.
    
    Usage:
        ingestor = DataIngestor(db_session, user_id="...")
        ingestor.insert_record({"url": "...", "text": "...", ...})
    """
    
    def __init__(self, session: Session, user_id: Optional[str] = None):
        """
        Initialize the DataIngestor.
        
        Args:
            session: SQLAlchemy database session.
            user_id: Optional user ID to associate with inserted records.
        """
        self.session = session
        self.user_id = user_id
        self._batch_buffer: List[Dict[str, Any]] = []
        self._batch_size = 50
    
    def normalize_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a raw record to match SentimentData schema.
        
        Replicates the logic from `_push_raw_data_to_db`:
        - Converts NaN/None values
        - Ensures 'text' field exists
        - Safely converts numeric fields
        - Parses date fields
        
        Args:
            raw_record: Raw dictionary from collector.
            
        Returns:
            Normalized dictionary ready for DB insertion.
        """
        record = {}
        
        # Copy all fields, converting NaN to None
        for key, value in raw_record.items():
            try:
                import pandas as pd
                if pd.isna(value):
                    record[key] = None
                    continue
            except (ImportError, TypeError):
                pass
            record[key] = value
        
        # Ensure 'text' field exists (fallback to content or description)
        if not record.get('text'):
            record['text'] = record.get('content') or record.get('description') or ''
        
        # Add user_id if provided
        if self.user_id:
            record['user_id'] = self.user_id
        
        # Add run_timestamp if not present
        if 'run_timestamp' not in record or record['run_timestamp'] is None:
            record['run_timestamp'] = datetime.now()
        
        # Safely convert numeric fields
        numeric_float_fields = ['sentiment_score', 'location_confidence', 'issue_confidence']
        numeric_int_fields = ['direct_reach', 'cumulative_reach', 
                              'domain_reach', 'retweets', 'likes', 'comments']
        
        for field in numeric_float_fields:
            if field in record:
                record[field] = safe_float(record[field])
        
        for field in numeric_int_fields:
            if field in record:
                record[field] = safe_int(record[field])
        
        # Parse date fields
        date_fields = ['published_date', 'date', 'published_at']
        for field in date_fields:
            if field in record and record[field]:
                record[field] = parse_datetime(record[field])
        
        # Map 'id' from CSV to 'original_id' to avoid conflict with entry_id
        if 'id' in record and 'original_id' not in record:
            record['original_id'] = str(record.pop('id'))
        
        # Set initial processing status
        if 'processing_status' not in record:
            record['processing_status'] = 'pending'
        
        return record
    
    def insert_record(self, raw_record: Dict[str, Any], commit: bool = True) -> bool:
        """
        Insert or update a single record using upsert.
        
        Args:
            raw_record: Raw dictionary from collector.
            commit: Whether to commit immediately (True) or buffer for batch (False).
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            record = self.normalize_record(raw_record)
            
            # Validate required field
            if not record.get('url'):
                logger.warning("Record missing 'url' field, skipping upsert.")
                return False
            
            # Filter to only valid SentimentData columns
            valid_columns = {c.name for c in SentimentData.__table__.columns}
            filtered_record = {k: v for k, v in record.items() if k in valid_columns}
            
            # Build upsert statement
            stmt = pg_insert(SentimentData).values(**filtered_record)
            
            # On conflict: update only engagement metrics, preserve analysis
            update_dict = {}
            for field in UPDATABLE_FIELDS:
                if field in filtered_record:
                    update_dict[field] = stmt.excluded[field]
            
            if update_dict:
                stmt = stmt.on_conflict_do_update(
                    index_elements=['url'],
                    set_=update_dict
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=['url'])
            
            self.session.execute(stmt)
            
            if commit:
                self.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during upsert: {e}")
            self.session.rollback()
            return False
        except Exception as e:
            logger.error(f"Error during insert_record: {e}", exc_info=True)
            return False
    
    def insert_batch(self, records: List[Dict[str, Any]]) -> int:
        """
        Insert multiple records efficiently using batch upsert.
        
        Args:
            records: List of raw dictionaries from collector.
            
        Returns:
            Number of successfully processed records.
        """
        success_count = 0
        
        try:
            normalized_records = [self.normalize_record(r) for r in records]
            
            # Filter valid records (must have url)
            valid_records = [r for r in normalized_records if r.get('url')]
            
            if not valid_records:
                return 0
            
            # Filter to only valid SentimentData columns
            valid_columns = {c.name for c in SentimentData.__table__.columns}
            filtered_records = [
                {k: v for k, v in r.items() if k in valid_columns}
                for r in valid_records
            ]
            
            # Build batch upsert
            stmt = pg_insert(SentimentData).values(filtered_records)
            
            update_dict = {}
            for field in UPDATABLE_FIELDS:
                update_dict[field] = stmt.excluded[field]
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['url'],
                set_=update_dict
            )
            
            self.session.execute(stmt)
            self.session.commit()
            
            success_count = len(filtered_records)
            logger.info(f"Batch inserted {success_count} records.")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during batch upsert: {e}")
            self.session.rollback()
        except Exception as e:
            logger.error(f"Error during insert_batch: {e}", exc_info=True)
        
        return success_count
