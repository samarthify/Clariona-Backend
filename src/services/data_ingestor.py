"""
DataIngestor - Unified data ingestion service for streaming collectors.

This module provides the `DataIngestor` class which handles:
1. Normalization: Cleans raw data (NaN handling, type safety, field fallbacks).
2. Upsert: Performs INSERT or UPDATE on conflict, preserving analysis fields.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy import event, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from src.api.models import AnalysisQueue, SentimentData
from src.utils.common import safe_float, safe_int, parse_datetime

# Optional imports for data processing
try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

# Use dedicated logger for data ingestor (writes to logs/data_ingestor.log)
logger = logging.getLogger('services.data_ingestor')

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

# Fields that we should backfill on conflict only if the existing DB value is NULL.
# This avoids overwriting earlier values, while letting late-arriving/previously-missing
# fields (like Apify timestamps) populate the row.
# NOTE: Do not include fields that are in UPDATABLE_FIELDS to avoid conflicts
# NOTE: user_location removed temporarily for debugging
BACKFILL_FIELDS = [
    'date',
    'published_at',
    'published_date',
    'platform',
]

# Fields that should ONLY be backfilled in single-row upserts (text/metadata)
# These are unsafe for batch processing due to SQLAlchemy boundparameter issues
SINGLE_MODE_BACKFILL_FIELDS = [
    'source',
    'source_url',
    'title',
    'description',
    'content',
    'text',
    'user_location',
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
        # Track urls for enqueue when commit=False (before_commit hook enqueues in same transaction)
        if 'pending_enqueue_urls' not in session.info:
            session.info['pending_enqueue_urls'] = set()
        # Register once per session: enqueue before commit so queue never misses records
        if not session.info.get('_enqueue_hook_registered'):
            event.listen(session, 'before_commit', self._flush_and_enqueue_pending)
            session.info['_enqueue_hook_registered'] = True

    def _flush_and_enqueue_pending(self, session: Session) -> None:
        """Before-commit hook: enqueue pending urls in same transaction (queue never misses)."""
        urls = session.info.pop('pending_enqueue_urls', set())
        if not urls:
            return
        try:
            session.flush()
            rows = session.query(SentimentData.entry_id).filter(SentimentData.url.in_(urls)).all()
            entry_ids = [r[0] for r in rows]
            if entry_ids:
                self._enqueue_for_analysis(entry_ids, commit=False)
        except Exception as e:
            logger.warning("Before-commit enqueue failed (non-fatal): %s", e)
            session.info.setdefault('pending_enqueue_urls', set()).update(urls)

    def _enqueue_for_analysis(self, entry_ids: List[int], commit: bool = True) -> None:
        """Enqueue entry_ids to analysis_queue. When commit=False, adds to current transaction (caller commits)."""
        if not entry_ids:
            return
        try:
            for eid in entry_ids:
                stmt = pg_insert(AnalysisQueue).values(entry_id=eid, status='pending')
                stmt = stmt.on_conflict_do_nothing(index_elements=['entry_id'])
                self.session.execute(stmt)
            use_notify = os.getenv("ANALYSIS_USE_NOTIFY", "true").lower() in ("true", "yes", "on", "1")
            if use_notify:
                self.session.execute(text("NOTIFY analysis_pending"))
            if commit:
                self.session.commit()
        except Exception as e:
            logger.warning("Enqueue for analysis failed (non-fatal): %s", e)
            if commit:
                try:
                    self.session.rollback()
                except Exception:
                    pass

    def _extract_twitter_id(self, url_or_id: str) -> Optional[str]:
        """
        Extract Twitter/X tweet ID from URL or return the ID if it's already just an ID.
        
        Examples:
            https://twitter.com/user/status/123456 -> 123456
            https://x.com/user/status/123456 -> 123456
            apify://twitter/123456 -> 123456
            123456 -> 123456
        """
        if not url_or_id:
            return None
        
        url_str = str(url_or_id).strip()
        
        # If it's already just a numeric ID, return it
        if url_str.isdigit():
            return url_str
        
        # Extract from Twitter/X URLs
        import re
        # Pattern: /status/123456 or /status/1234567890123456789
        match = re.search(r'/status/(\d+)', url_str)
        if match:
            return match.group(1)
        
        # Extract from apify://twitter/123456 format
        match = re.search(r'apify://twitter/(\d+)', url_str)
        if match:
            return match.group(1)
        
        # If it contains a long numeric string, try to extract it (tweet IDs are typically 19 digits)
        # SAFEGUARD: only do this when the string looks Twitter/X-related. Other platforms (e.g. TikTok)
        # also use long numeric IDs in their URLs, and we must not convert those to Twitter URLs.
        lowered = url_str.lower()
        if ('twitter.com' in lowered) or ('x.com' in lowered) or lowered.startswith('apify://twitter/'):
            match = re.search(r'(\d{15,})', url_str)
            if match:
                return match.group(1)
        
        return None
    
    def _normalize_url(self, url: str, platform: Optional[str] = None) -> str:
        """
        Normalize URLs to prevent duplicates, especially for Twitter/X.
        
        IMPORTANT: Prefers real Twitter URLs (twitter.com/x.com) over apify:// ones.
        If we have both formats for the same tweet, we want to keep the real URL.
        
        Converts:
        - https://x.com/user/status/123456 -> https://twitter.com/i/web/status/123456
        - https://twitter.com/user/status/123456 -> https://twitter.com/i/web/status/123456
        - apify://twitter/123456 -> https://twitter.com/i/web/status/123456
        
        CRITICAL: Also handles concatenated URLs like:
        - "https://x.com/...https://twitter.com/..." -> extracts first valid tweet ID
        
        Args:
            url: URL to normalize (may contain concatenated URLs)
            platform: Platform name (helps with normalization)
            
        Returns:
            Normalized URL string (always uses twitter.com/i/web/status/ID format for Twitter)
        """
        if not url:
            return url
        
        url_str = str(url).strip()
        
        # CRITICAL FIX: Handle concatenated URLs (e.g., "https://x.com/...https://twitter.com/...")
        # Extract the first valid Twitter URL if multiple are concatenated
        if 'https://' in url_str and url_str.count('https://') > 1:
            # Split by 'https://' and find the first valid Twitter URL
            parts = url_str.split('https://')
            for part in parts[1:]:  # Skip first empty part
                candidate_url = 'https://' + part
                # Check if this looks like a Twitter URL
                if 'twitter.com' in candidate_url or 'x.com' in candidate_url:
                    url_str = candidate_url
                    logger.warning(f"Ingestor: Found concatenated URLs, using first Twitter URL: {url_str[:100]}")
                    break
        
        platform_lower = (platform or '').lower().strip()

        # SAFEGUARD: never "Twitter-normalize" obvious non-Twitter domains even if platform metadata is wrong.
        # This prevents cases like TikTok URLs (which contain long numeric IDs) being converted into
        # https://twitter.com/i/web/status/<id>.
        lowered = url_str.lower()
        if 'tiktok.com' in lowered and platform_lower == 'twitter':
            logger.warning(
                f"Ingestor: Platform said twitter but url looks like TikTok; skipping Twitter normalization: {url_str[:100]}"
            )
            return url_str
        
        # Normalize Twitter/X URLs to a consistent format
        # Check both explicit platform and URL patterns to catch all cases
        is_twitter_url = (
            ('twitter.com' in lowered) or
            ('x.com' in lowered) or
            lowered.startswith('apify://twitter/') or
            # If platform is twitter, only normalize when input still "looks twitter-like"
            # (numeric-only tweet id is allowed).
            (platform_lower == 'twitter' and (url_str.isdigit() or '/status/' in lowered))
        )
        
        if is_twitter_url:
            tweet_id = self._extract_twitter_id(url_str)
            if tweet_id:
                # ALWAYS use consistent Twitter URL format (i/web/status/ID)
                # This ensures all Twitter URLs use the same format, preventing duplicates
                # The format works for both twitter.com and x.com
                normalized = f"https://twitter.com/i/web/status/{tweet_id}"
                if url_str != normalized:
                    logger.debug(f"Ingestor: Normalized Twitter URL: {url_str[:100]} -> {normalized}")
                return normalized
            # If we can't extract ID, return as-is (shouldn't happen for valid Twitter URLs)
            logger.warning(f"Ingestor: Could not extract tweet ID from URL: {url_str[:100]}")
            return url_str
        
        # For other platforms, return as-is
        return url_str

    def _prepare_records_for_insert(
        self,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        - Keeps only valid DB columns
        - Converts string fields safely
        - Removes SQLAlchemy objects
        """
        valid_columns = {c.name for c in SentimentData.__table__.columns}
        string_fields = [
            'user_location', 
            'source', 
            'source_url', 
            'title', 
            'description', 
            'content', 
            'text'
        ]

        def is_sqlalchemy_object(v):
            return isinstance(v, (InstrumentedAttribute, ColumnElement))

        prepared = []

        for r in records:
            filtered = {k: v for k, v in r.items() if k in valid_columns}

            for field in string_fields:
                if field in filtered:
                    v = filtered[field]
                    if is_sqlalchemy_object(v):
                        logger.error(
                            f"🚨 SQLA OBJECT DETECTED: {field}={v} — forcing NULL"
                        )
                        filtered[field] = None
                    elif v is not None:
                        filtered[field] = str(v)

            prepared.append(filtered)

        return prepared

    def _prune_null_only_columns(
        self,
        records: List[Dict[str, Any]],
        fields: List[str],
    ) -> None:
        """
        Removes columns that are None for ALL rows.
        Mutates records in-place.
        """
        null_only_fields = [
            field
            for field in fields
            if all(r.get(field) is None for r in records)
        ]

        if not null_only_fields:
            return

        for r in records:
            for field in null_only_fields:
                r.pop(field, None)

        logger.debug(
            f"Ingestor: Pruned null-only batch fields: {null_only_fields}"
        )
    
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
            # Skip None values
            if value is None:
                record[key] = None
                continue
            
            # Handle scalar NaN values (not lists/dicts/arrays)
            if not isinstance(value, (list, dict, tuple)):
                try:
                    # Check for NaN (float) or pandas NA
                    if np is not None and isinstance(value, float) and np.isnan(value):
                        record[key] = None
                        continue
                    if pd is not None and pd.isna(value) and not isinstance(value, str):
                        record[key] = None
                        continue
                except (TypeError, ValueError):
                    pass
            
            record[key] = value
        
        # Ensure 'text' field exists (fallback to title, content, description)
        if not record.get('text'):
            record['text'] = (
                record.get('title') or 
                record.get('content') or 
                record.get('description') or 
                record.get('caption') or 
                record.get('body') or
                record.get('full_text') or 
                ''
            )
        
        # Add user_id if provided
        if self.user_id:
            record['user_id'] = self.user_id
        
        # Add run_timestamp if not present
        if 'run_timestamp' not in record or record['run_timestamp'] is None:
            record['run_timestamp'] = datetime.now()

        # Promote TikTok-style URL field early (prevents misclassification as Twitter based on numeric `id`)
        # Some TikTok exports use `postPage` (not `url`) for the canonical post link.
        if not record.get('url'):
            post_page = record.get('postPage') or record.get('post_page')
            if post_page and str(post_page).strip().startswith('http'):
                record['url'] = str(post_page).strip()
        
        # Map engagement metrics from various platforms before conversion
        # Twitter/X style
        # Twitter/X style
        if record.get('likes') is None:
            record['likes'] = safe_int(
                record.get('likeCount') or 
                record.get('like_count') or  # YouTube style
                record.get('likesCount') or 
                record.get('favoriteCount') or
                record.get('reactions_count') or
                record.get('likes') or
                record.get('favorites')
            )
        if record.get('retweets') is None:
            record['retweets'] = safe_int(
                record.get('retweetCount') or 
                record.get('reshareCount') or
                record.get('reshare_count') or
                record.get('shareCount') or
                record.get('shares') or
                record.get('retweets')
            )
        if record.get('comments') is None:
            record['comments'] = safe_int(
                record.get('replyCount') or 
                record.get('commentsCount') or
                record.get('comments_count') or
                record.get('commentCount') or
                record.get('comment_count') or  # YouTube style
                record.get('comments') or
                record.get('replies')
            )
        
        # Views / Reach
        if record.get('direct_reach') is None:
            record['direct_reach'] = safe_int(
                record.get('viewCount') or
                record.get('view_count') or  # YouTube style
                record.get('views') or
                record.get('impressions') or
                record.get('direct_reach')
            )
        if record.get('cumulative_reach') is None:
            record['cumulative_reach'] = safe_int(
                record.get('cumulativeReach') or
                record.get('totalReach') or
                record.get('cumulative_reach')
            )
        
        # Quote count (Twitter-specific, add to comments or separate)
        quote_count = safe_int(record.get('quoteCount') or record.get('quotes'))
        if quote_count and record.get('comments'):
            record['comments'] = (record['comments'] or 0) + quote_count
        elif quote_count:
            record['comments'] = quote_count
        
        # Bookmark count (Twitter-specific, can add to likes or track separately)
        bookmark_count = safe_int(record.get('bookmarkCount') or record.get('bookmarks'))
        if bookmark_count and record.get('likes'):
            record['likes'] = (record['likes'] or 0) + bookmark_count
        elif bookmark_count and not record.get('likes'):
            record['likes'] = bookmark_count
        
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
        
        # Parse and map date fields
        # Map 'published' to 'published_date' (common Apify field name)
        if 'published' in record and 'published_date' not in record:
            record['published_date'] = record.pop('published')
        
        # Normalize published_date first if it exists (RSS/news sources provide this)
        if record.get('published_date'):
            parsed_pub_date = parse_datetime(record['published_date'])
            if parsed_pub_date:
                record['published_date'] = parsed_pub_date
        
        # If 'date' is missing, derive it from common incoming fields
        # PRIORITY: published_date should be used first (RSS/news sources)
        if not record.get('date'):
            # Common fields from various platforms/actors
            # IMPORTANT: published_date is first priority for RSS/news sources
            date_candidates = [
                ('published_date', record.get('published_date')),  # RSS/news - HIGHEST PRIORITY
                ('timestamp', record.get('timestamp')),          # Instagram, sometimes epoch
                ('createdAt', record.get('createdAt')),          # X/Twitter style
                ('created_at', record.get('created_at')),        # snake_case variant
                ('uploadedAt', record.get('uploadedAt')),        # TikTok style
                ('postedAt', record.get('postedAt') or record.get('posted_at')),
                ('publicationDate', record.get('publicationDate') or record.get('publishDate') or record.get('pubDate')),
                ('published_time', record.get('published_time')),  # RSS or news
                ('time', record.get('time') or record.get('datetime')),
            ]
            for source_field, cand in date_candidates:
                if cand:
                    # Skip if this is already a datetime object (from published_date normalization above)
                    if isinstance(cand, datetime):
                        record['date'] = cand
                        record['_date_source_field'] = source_field
                        logger.debug(
                            f"Ingestor: Using datetime object from '{source_field}' -> {cand} "
                            f"(url={str(record.get('url'))[:80]})"
                        )
                        break
                    parsed = parse_datetime(cand)
                    if parsed:
                        record['date'] = parsed
                        # Internal-only debug metadata (not persisted)
                        record['_date_source_field'] = source_field
                        record['_date_source_value'] = str(cand)[:120]
                        logger.debug(
                            f"Ingestor: Parsed record date from '{source_field}' -> {parsed} "
                            f"(url={str(record.get('url'))[:80]})"
                        )
                        break
        
        # If 'published_at' missing, map from createdAt/created_at or publication fields
        # PRIORITY: published_date should be used first (RSS/news sources)
        if not record.get('published_at'):
            publish_candidates = [
                record.get('published_at'),       # already set?
                record.get('published_date'),      # RSS/news - HIGHEST PRIORITY
                record.get('createdAt'),
                record.get('created_at'),
                record.get('publicationDate') or record.get('publishDate') or record.get('pubDate'),
                record.get('published_time'),
            ]
            for cand in publish_candidates:
                if cand:
                    # Skip if this is already a datetime object (from published_date normalization above)
                    if isinstance(cand, datetime):
                        record['published_at'] = cand
                        break
                    parsed = parse_datetime(cand)
                    if parsed:
                        record['published_at'] = parsed
                        break
        
        # Normalize any existing date-like fields to datetime objects
        # (Skip if already a datetime object to avoid redundant parsing)
        date_fields = ['published_date', 'date', 'published_at']
        for field in date_fields:
            if field in record and record[field] and not isinstance(record[field], datetime):
                parsed = parse_datetime(record[field])
                if parsed:
                    record[field] = parsed
        
        # Force-fill 'date' with run_timestamp if still NULL (ensures consistent ordering)
        if not record.get('date'):
            record['date'] = record.get('run_timestamp', datetime.now())
            logger.debug(
                f"Ingestor: Set date=run_timestamp fallback for url={str(record.get('url'))[:80]} "
                f"(date={record['date']})"
            )

        # Map user fields from common sources if missing
        # 1) Robustly parse Author object (Twitter/X style) which might be a dict or JSON string
        raw_author = record.get('author') or record.get('Author')
        author = None
        
        if isinstance(raw_author, dict):
            author = raw_author
        elif isinstance(raw_author, str):
            try:
                # Try to parse stringified JSON (common in some Apify actors)
                author = json.loads(raw_author)
            except json.JSONDecodeError:
                pass
        
        user_obj = record.get('user') if isinstance(record.get('user'), dict) else None
        place_obj = record.get('place') if isinstance(record.get('place'), dict) else None
        channel_obj = record.get('channel') if isinstance(record.get('channel'), dict) else None
        
        # Additional platform-specific objects
        # TikTok: poi (Point of Interest)
        poi_obj = record.get('poi') if isinstance(record.get('poi'), dict) else None
        # Twitter: user_info
        user_info_obj = record.get('user_info') if isinstance(record.get('user_info'), dict) else None

        # Helper to get value case-insensitively from a dict
        def get_ci(d, key):
            if not d: return None
            # Direct match first (fast)
            if key in d: return d[key]
            # Case-insensitive match
            key_lower = key.lower()
            for k, v in d.items():
                if k.lower() == key_lower:
                    return v
            return None

        # user_handle
        if not record.get('user_handle'):
            handle_candidates = [
                ('author.username', get_ci(author, 'username') or get_ci(author, 'userName') or get_ci(author, 'screen_name')),
                ('user.username', get_ci(user_obj, 'username') or get_ci(user_obj, 'userName')),
                ('user_info.screen_name', get_ci(user_info_obj, 'screen_name')),
                ('channel.username', get_ci(channel_obj, 'username')),
                ('ownerUsername', record.get('ownerUsername')),
            ]
            for source_field, val in handle_candidates:
                if val:
                    record['user_handle'] = str(val)
                    logger.debug(f"Ingestor: Parsed user_handle from '{source_field}' -> {record['user_handle']} (url={str(record.get('url'))[:80]})")
                    break

        # user_name
        if not record.get('user_name'):
            name_candidates = [
                ('author.name', get_ci(author, 'name')),
                ('user.name', get_ci(user_obj, 'name')),
                ('user_info.name', get_ci(user_info_obj, 'name')),
                ('ownerFullName', record.get('ownerFullName')),
                ('channel', record.get('channel').get('name') if isinstance(record.get('channel'), dict) else record.get('channel')),
                ('author_title', record.get('author_title')),
            ]
            for source_field, val in name_candidates:
                if val:
                    record['user_name'] = str(val)
                    logger.debug(f"Ingestor: Parsed user_name from '{source_field}' -> {record['user_name']} (url={str(record.get('url'))[:80]})")
                    break

        # user_avatar
        if not record.get('user_avatar'):
            avatar_candidates = [
                ('author.profile_image_url', get_ci(author, 'profile_image_url') or get_ci(author, 'profile_image_url_https') or get_ci(author, 'profilePicture')),
                ('user.profile_image_url', get_ci(user_obj, 'profile_image_url') or get_ci(user_obj, 'profilePicture')),
                ('user_info.profile_image_url', get_ci(user_info_obj, 'profile_image_url_https') or get_ci(user_info_obj, 'profile_image_url')),
                ('channel.avatar', get_ci(channel_obj, 'avatar')),
                ('profilePicUrl', record.get('profilePicUrl') or record.get('ownerProfilePicUrl')),
            ]
            for source_field, val in avatar_candidates:
                if val:
                    record['user_avatar'] = str(val)
                    logger.debug(f"Ingestor: Parsed user_avatar from '{source_field}' -> {record['user_avatar'][:80]} (url={str(record.get('url'))[:80]})")
                    break

        # user_location
        if not record.get('user_location'):
            # Try top-level variations first
            top_level_location = record.get('location') or record.get('Location')
            
            location_candidates = [
                ('location (top-level)', top_level_location),
                ('author.location', get_ci(author, 'location')),
                ('user.location', get_ci(user_obj, 'location')),
                ('user_info.location', get_ci(user_info_obj, 'location')),
                ('poi.name', get_ci(poi_obj, 'name')),
                ('poi.address', get_ci(poi_obj, 'address')),
                ('place.full_name', place_obj.get('full_name') if place_obj else None),
                ('place.name', place_obj.get('name') if place_obj else None),
                ('ownerLocation', record.get('ownerLocation')),
            ]
            for source_field, val in location_candidates:
                if val:
                    record['user_location'] = str(val)
                    logger.debug(f"Ingestor: Parsed user_location from '{source_field}' -> {record['user_location']} (url={str(record.get('url'))[:80]})")
                    break
            
            # Log warning if we have author/user but failed to find location (helps debugging data gaps)
            if not record.get('user_location') and (author or user_obj or user_info_obj):
                pass
        
        # Map 'id' from CSV to 'original_id' to avoid conflict with entry_id
        # For Twitter, also check if 'id' is a tweet ID that we can use to normalize URL
        if 'id' in record and 'original_id' not in record:
            id_value = record.pop('id')
            record['original_id'] = str(id_value)
            
            # If we don't have a URL yet, check if this is a Twitter tweet ID
            # Check platform/source hints (avoid guessing purely from long numeric IDs; TikTok uses those too)
            if not record.get('url'):
                platform_hint = str(record.get('platform') or '').lower().strip()
                source_hint = str(record.get('source') or '').lower().strip()
                has_twitter_fields = bool(
                    record.get('twitterUrl') or
                    record.get('inReplyToId') or
                    record.get('retweeted_tweet')
                )
                is_twitter = (
                    platform_hint in ('twitter', 'x', 'x.com') or
                    source_hint in ('twitter', 'x', 'x.com') or
                    ('twitter' in source_hint) or
                    ('x.com' in source_hint) or
                    has_twitter_fields
                )
                if is_twitter:
                    tweet_id = self._extract_twitter_id(str(id_value))
                    if tweet_id:
                        record['url'] = f"https://twitter.com/i/web/status/{tweet_id}"
        
        # Map 'tweet_id' to 'original_id' if present
        if 'tweet_id' in record and 'original_id' not in record:
            tweet_id_value = record.get('tweet_id')
            record['original_id'] = str(tweet_id_value)
            
            # If we don't have a URL yet, generate it from tweet_id
            if not record.get('url'):
                tweet_id = self._extract_twitter_id(str(tweet_id_value))
                if tweet_id:
                    record['url'] = f"https://twitter.com/i/web/status/{tweet_id}"
        
        # Map 'source' to 'data_source' if applicable
        if 'source' in record and 'data_source' not in record:
            record['data_source'] = record.get('source')
        
        # Map 'domain' to help identify source
        if 'domain' in record and not record.get('data_source'):
            record['data_source'] = record.get('domain')
        
        # Derive platform if missing
        if not record.get('platform'):
            # First, try to detect from URL
            url = record.get('url') or record.get('link') or record.get('postUrl') or record.get('postPage') or record.get('pageUrl') or record.get('inputUrl') or ''
            url_lower = str(url).lower()
            
            if 'instagram.com' in url_lower or '/p/' in url_lower and 'instagram' in url_lower:
                record['platform'] = 'instagram'
            elif 'x.com' in url_lower or 'twitter.com' in url_lower:
                record['platform'] = 'twitter'
            elif 'facebook.com' in url_lower:
                record['platform'] = 'facebook'
            elif 'tiktok.com' in url_lower:
                record['platform'] = 'tiktok'
            elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
                record['platform'] = 'youtube'
            elif 'linkedin.com' in url_lower:
                record['platform'] = 'linkedin'
            elif 'reddit.com' in url_lower:
                record['platform'] = 'reddit'
            else:
                # Try common incoming fields
                # NOTE: We check 'source' field but only accept it if it matches known platforms
                # to avoid using keywords (like "tinubu") that might be stored in 'source' field
                platform_candidates = [
                    record.get('platform'),
                    record.get('type'),
                    record.get('inputSource'),
                    record.get('site'),
                ]
                
                # Check 'source' field separately - only use if it matches known platforms
                source_field = record.get('source')
                if source_field:
                    source_str = str(source_field).lower().strip()
                    # Only add source to candidates if it looks like a platform name
                    # Known platform keywords that should be accepted
                    known_platform_keywords = ['instagram', 'twitter', 'facebook', 'tiktok', 'youtube', 
                                              'linkedin', 'reddit', 'ig', 'fb', 'tt', 'yt', 'x.com', 'x']
                    if any(keyword in source_str for keyword in known_platform_keywords):
                        platform_candidates.insert(1, source_field)  # Insert after 'platform' but before others
                
                for cand in platform_candidates:
                    if cand:
                        cand_str = str(cand).lower().strip()
                        # Normalize common variations
                        if 'instagram' in cand_str or 'ig' == cand_str:
                            record['platform'] = 'instagram'
                        elif 'twitter' in cand_str or 'x.com' in cand_str or 'x' == cand_str:
                            record['platform'] = 'twitter'
                        elif 'facebook' in cand_str or 'fb' == cand_str:
                            record['platform'] = 'facebook'
                        elif 'tiktok' in cand_str or 'tt' == cand_str:
                            record['platform'] = 'tiktok'
                        elif 'youtube' in cand_str or 'yt' == cand_str:
                            record['platform'] = 'youtube'
                        elif 'linkedin' in cand_str:
                            record['platform'] = 'linkedin'
                        elif 'reddit' in cand_str:
                            record['platform'] = 'reddit'
                        else:
                            # Only use as-is if it's NOT from the 'source' field (to avoid keywords)
                            # and it looks like a valid platform name
                            is_from_source = cand == source_field
                            if not is_from_source and len(cand_str) < 30 and cand_str.replace('_', '').replace('-', '').isalnum():
                                record['platform'] = cand_str
                                break
                        if record.get('platform'):
                            break
            
            # If still no platform, check for platform-specific field patterns
            if not record.get('platform'):
                if record.get('shortcode') or record.get('shortCode'):
                    record['platform'] = 'instagram'  # shortcode is Instagram-specific
                elif record.get('twitterUrl'):
                    record['platform'] = 'twitter'
                elif record.get('inReplyToId') or record.get('retweeted_tweet'):
                    record['platform'] = 'twitter'
                elif 'ownerUsername' in record or 'ownerFullName' in record:
                    record['platform'] = 'instagram'  # Instagram-specific fields
                elif 'channel' in record and 'collabInfo' in record:
                    record['platform'] = 'tiktok'  # TikTok-specific fields
            
            if record.get('platform'):
                logger.debug(
                    f"Ingestor: Derived platform='{record['platform']}' for url={str(record.get('url'))[:80]}"
                )
        
        # Normalize URL if present (especially for Twitter/X to prevent duplicates)
        if record.get('url'):
            record['url'] = self._normalize_url(record['url'], record.get('platform'))
        
        # Generate URL if missing (required for upsert)
        if not record.get('url'):
            # Try common URL field names from Apify actors
            url_candidates = [
                record.get('link'),
                record.get('postUrl'),
                record.get('postPage'),
                record.get('pageUrl'),
                record.get('videoUrl'),
                record.get('articleUrl'),
            ]
            
            for candidate in url_candidates:
                if candidate:
                    record['url'] = self._normalize_url(candidate, record.get('platform'))
                    break
            
            # If still no URL, generate from other identifiers
            if not record.get('url'):
                # Try to construct URL from platform-specific fields
                shortcode = record.get('shortcode') or record.get('shortCode')
                post_id = record.get('postId') or record.get('original_id') or record.get('inputUrl')
                platform = record.get('platform', '').lower() or record.get('source', '').lower()
                
                if shortcode:
                    # Instagram shortcode
                    record['url'] = f"https://instagram.com/p/{shortcode}"
                elif post_id:
                    # For Twitter, extract tweet ID from post_id if it's a URL
                    if platform == 'twitter' and ('twitter.com' in str(post_id) or 'x.com' in str(post_id)):
                        tweet_id = self._extract_twitter_id(str(post_id))
                        if tweet_id:
                            record['url'] = f"https://twitter.com/i/web/status/{tweet_id}"
                        else:
                            record['url'] = f"apify://{platform or 'unknown'}/{post_id}"
                    else:
                        # Generate a unique URL-like identifier
                        record['url'] = f"apify://{platform or 'unknown'}/{post_id}"
                else:
                    # Last resort: hash the text content to create unique identifier
                    import hashlib
                    text_content = record.get('text') or record.get('content') or ''
                    timestamp = record.get('run_timestamp', datetime.now())
                    # Include platform/source to avoid collisions across different scrapers
                    src_prefix = platform or record.get('source') or 'unknown'
                    unique_str = f"{src_prefix}_{text_content[:200]}_{timestamp}"
                    content_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    record['url'] = f"apify://generated/{content_hash}"
        
        # Set initial processing status
        if record.get('processing_status') is None:
            record['processing_status'] = 'pending'
            
        if not record.get('source_url') and record.get('url') and str(record.get('url')).startswith('http'):
            record['source_url'] = record['url']
        
        return record
    
    def insert_record(self, raw_record: Dict[str, Any], commit: bool = True, log_stored: bool = False) -> str:
        """
        Insert or update a single record using upsert.
        
        Args:
            raw_record: Raw dictionary from collector.
            commit: Whether to commit immediately (True) or buffer for batch (False).
            
        Returns:
            Status string: 'inserted', 'updated', 'skipped', or 'failed'
        """
        try:
            record = self.normalize_record(raw_record)
            
            # Validate required field
            if not record.get('url'):
                # Debug: Log the raw record structure to understand the data format
                sample_keys = list(raw_record.keys())[:15]
                logger.warning(f"Record missing 'url' field. Available keys: {sample_keys}")
                # Log a sample of the raw data for debugging
                if raw_record:
                    sample_data = {k: str(v)[:50] if v else None for k, v in list(raw_record.items())[:5]}
                    logger.debug(f"Sample raw data: {sample_data}")
                return 'failed'
            
            # Check if record already exists (for tracking insert vs update + backfill logging)
            url = record.get('url')
            existing = self.session.query(
                SentimentData.entry_id,
                SentimentData.date,
                SentimentData.published_at,
                SentimentData.published_date,
                SentimentData.platform,
                SentimentData.likes,
                SentimentData.retweets,
                SentimentData.comments,
                SentimentData.direct_reach,
                SentimentData.user_name,
                SentimentData.user_handle,
                SentimentData.user_avatar,
                SentimentData.user_location,
            ).filter(SentimentData.url == url).first()
            exists = existing is not None

            # If this upsert will backfill fields (DB NULL -> incoming non-NULL), log it.
            will_backfill = []
            if exists:
                (
                    _eid,
                    existing_date,
                    existing_published_at,
                    existing_published_date,
                    existing_platform,
                    existing_likes,
                    existing_retweets,
                    existing_comments,
                    existing_direct_reach,
                    existing_user_name,
                    existing_user_handle,
                    existing_user_avatar,
                    existing_user_location,
                ) = existing
                if existing_date is None and record.get('date') is not None:
                    will_backfill.append('date')
                if existing_published_at is None and record.get('published_at') is not None:
                    will_backfill.append('published_at')
                if existing_published_date is None and record.get('published_date') is not None:
                    will_backfill.append('published_date')
                if existing_platform is None and record.get('platform') is not None:
                    will_backfill.append('platform')
                if existing_likes is None and record.get('likes') is not None:
                    will_backfill.append('likes')
                if existing_retweets is None and record.get('retweets') is not None:
                    will_backfill.append('retweets')
                if existing_comments is None and record.get('comments') is not None:
                    will_backfill.append('comments')
                if existing_direct_reach is None and record.get('direct_reach') is not None:
                    will_backfill.append('direct_reach')
                if existing_user_name is None and record.get('user_name') is not None:
                    will_backfill.append('user_name')
                if existing_user_handle is None and record.get('user_handle') is not None:
                    will_backfill.append('user_handle')
                if existing_user_avatar is None and record.get('user_avatar') is not None:
                    will_backfill.append('user_avatar')
                if existing_user_location is None and record.get('user_location') is not None:
                    will_backfill.append('user_location')
            
            # Prepare record (filters columns, sanitizes strings, guards SQLA objects)
            filtered_records = self._prepare_records_for_insert([record])
            filtered_record = filtered_records[0]
            
            # Build upsert statement
            stmt = pg_insert(SentimentData).values(**filtered_record)
            
            # On conflict: update only engagement metrics, preserve analysis
            update_dict = {}
            for field in UPDATABLE_FIELDS:
                if field in filtered_record:
                    update_dict[field] = stmt.excluded[field]

            # Enforce PROTECTED_FIELDS by ensuring they are never in the update_dict
            for field in PROTECTED_FIELDS:
                update_dict.pop(field, None)

            # Backfill important fields only if currently NULL in DB
            # We use COALESCE(current_value, new_value) so that if current_value is NOT NULL, it stays.
            # If current_value IS NULL, it takes new_value (stmt.excluded[field]).
            # Skip fields already handled by UPDATABLE_FIELDS to avoid conflicts.
            # In single mode, we backfill BOTH safe scalars and fragile text fields
            for field in (BACKFILL_FIELDS + SINGLE_MODE_BACKFILL_FIELDS):
                if field in filtered_record and field not in update_dict:
                    # Only add if we actually have a value to backfill
                    if filtered_record[field] is not None:
                        update_dict[field] = func.coalesce(
                            getattr(SentimentData, field),
                            getattr(stmt.excluded, field)
                        )
            

            
            # Log first record for debugging (fixed: removed undefined 'records' check)
            logger.debug(f"Upsert update_dict keys: {list(update_dict.keys())}")
            
            if update_dict:
                stmt = stmt.on_conflict_do_update(
                    index_elements=['url'],
                    set_=update_dict
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=['url'])
            
            result = self.session.execute(stmt)
            
            # Store URL for post-commit logging if requested
            log_url_after_commit = log_stored and url
            
            if commit:
                # Enqueue in same transaction before commit so queue never misses
                self.session.flush()
                row = self.session.query(SentimentData.entry_id).filter(SentimentData.url == url).first()
                if row:
                    self._enqueue_for_analysis([row[0]], commit=False)
                self.session.commit()
                # Log what was actually stored in DB (for debugging coverage gaps)
                # Only log if explicitly requested (e.g., first record of batch)
                if log_url_after_commit:
                    stored = self.session.query(SentimentData).filter(
                        SentimentData.url == url
                    ).first()
                    
                    if stored:
                        stored_values = {
                            'entry_id': stored.entry_id,
                            'url': stored.url[:80] if stored.url else None,
                            'platform': stored.platform,
                            'date': stored.date,
                            'published_at': stored.published_at,
                            'published_date': stored.published_date,
                            'user_name': stored.user_name,
                            'user_handle': stored.user_handle,
                            'user_avatar': stored.user_avatar[:80] if stored.user_avatar else None,
                            'user_location': stored.user_location,
                            'likes': stored.likes,
                            'retweets': stored.retweets,
                            'comments': stored.comments,
                            'direct_reach': stored.direct_reach,
                            'cumulative_reach': stored.cumulative_reach,
                            'text': (stored.text[:100] + '...') if stored.text and len(stored.text) > 100 else stored.text,
                        }
                        logger.info(
                            f"Ingestor: ✓ STORED in DB for url={str(url)[:80]} | "
                            f"platform={stored_values['platform']} | "
                            f"date={stored_values['date']} | "
                            f"user_name={stored_values['user_name']} | "
                            f"user_handle={stored_values['user_handle']} | "
                            f"user_location={stored_values['user_location']} | "
                            f"likes={stored_values['likes']} retweets={stored_values['retweets']} comments={stored_values['comments']} views={stored_values['direct_reach']}"
                        )
                        logger.debug(
                            f"Ingestor: Full stored record (entry_id={stored_values['entry_id']}): {stored_values}"
                        )
            
            # High-signal log: only when we are about to/just did backfill fields
            if will_backfill:
                engagement_str = f"likes={record.get('likes')} retweets={record.get('retweets')} comments={record.get('comments')} views={record.get('direct_reach')}"
                logger.info(
                    f"Ingestor: Backfilled {will_backfill} for url={str(url)[:100]} "
                    f"date={record.get('date')} platform={record.get('platform')} "
                    f"{engagement_str} "
                    f"(source={record.get('_date_source_field')})"
                )

            if not commit:
                # Track for before_commit hook (collectors that batch with commit=False)
                self.session.info.setdefault('pending_enqueue_urls', set()).add(url)
            
            # Determine if it was insert or update
            if exists:
                logger.info(f"Ingestor: insert_record updated | platform={record.get('platform')} | url={str(url)[:70]}")
                return 'updated'
            else:
                logger.info(f"Ingestor: insert_record inserted | platform={record.get('platform')} | url={str(url)[:70]}")
                return 'inserted'
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during upsert: {e}")
            self.session.rollback()
            return 'failed'
        except Exception as e:
            logger.error(f"Error during insert_record: {e}", exc_info=True)
            return 'failed'
    
    def insert_batch(self, records: List[Dict[str, Any]]) -> int:
        """
        Insert multiple records efficiently using batch upsert.
        
        NOTE: Batch upsert only supports backfilling scalar fields (dates, platforms, metrics).
        Textual/metadata fields (title, description, source_url, etc.) are NOT backfilled in batch mode
        to prevent SQLAlchemy boundparameter errors with mixed NULLs. 
        If faithful backfill of text metadata is required, use insert_record (single mode) instead.

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
            
            # Deduplicate records by URL
            # IMPORTANT: After normalization, all Twitter URLs should be in same format
            # However, we prefer real URLs (twitter.com/x.com) over apify:// ones
            # So if we have both formats, keep the real one
            unique_records_map = {}
            for r in valid_records:
                url = r.get('url')
                if not url:
                    continue
                
                # If we already have this URL, prefer the one with real Twitter URL over apify://
                if url in unique_records_map:
                    existing = unique_records_map[url]
                    existing_url = existing.get('url', '')
                    new_url = r.get('url', '')
                    
                    # Prefer real Twitter URLs over apify:// ones
                    if (existing_url.startswith('apify://') and 
                        (new_url.startswith('https://twitter.com') or new_url.startswith('https://x.com'))):
                        unique_records_map[url] = r  # Replace with real URL version
                        logger.debug(f"Ingestor: Replacing apify:// URL with real URL: {url[:80]}")
                else:
                    unique_records_map[url] = r
            
            unique_records = list(unique_records_map.values())
            
            if len(unique_records) < len(valid_records):
                dropped_count = len(valid_records) - len(unique_records)
                logger.info(f"Ingestor: Dropped {dropped_count} duplicate records in batch (after URL normalization).")
                
                # Log sample of what was dropped for debugging
                if dropped_count > 0:
                    dropped_urls = set(r.get('url') for r in valid_records) - set(r.get('url') for r in unique_records)
                    sample_dropped = [r for r in valid_records if r.get('url') in dropped_urls][:3]
                    for dropped in sample_dropped:
                        logger.debug(f"Ingestor: Dropped duplicate - url={dropped.get('url', 'None')[:80]}, platform={dropped.get('platform')}")

            # Filter to only valid SentimentData columns
            valid_columns = {c.name for c in SentimentData.__table__.columns}

            # Prepare records (shared sanitization logic)
            filtered_records = self._prepare_records_for_insert(unique_records)
            
            # CRITICAL: prune null-only columns BEFORE insert to prevent boundparameter errors
            # These are fields that are typically fragile (text/metadata) in mixed batches
            BATCH_UNSAFE_FIELDS = [
                'user_location', 'source', 'source_url', 
                'title', 'description', 'content', 'text'
            ]
            self._prune_null_only_columns(filtered_records, BATCH_UNSAFE_FIELDS)
            
            # Ensure all records have identical keys (SQLAlchemy safety)
            # This prevents "explicitly rendered as a boundparameter" errors if some rows are missing keys
            all_keys = set().union(*(r.keys() for r in filtered_records))
            for r in filtered_records:
                for k in all_keys:
                    r.setdefault(k, None)
            
            # Build batch upsert
            stmt = pg_insert(SentimentData).values(filtered_records)
            
            update_dict = {}
            for field in UPDATABLE_FIELDS:
                if field in valid_columns:
                    update_dict[field] = getattr(stmt.excluded, field)

            # Enforce PROTECTED_FIELDS
            for field in PROTECTED_FIELDS:
                update_dict.pop(field, None)

            # Backfill important fields only if currently NULL in DB
            # Skip fields already handled by UPDATABLE_FIELDS to avoid conflicts
            for field in BACKFILL_FIELDS:
                if field in valid_columns and field not in update_dict:
                    # CRITICAL: only add backfill if at least one row has a real value
                    # Otherwise `stmt.excluded.field` becomes a pure boundparameter (SQLAlchemy edge case)
                    if any(r.get(field) is not None for r in filtered_records):
                        update_dict[field] = func.coalesce(
                            getattr(SentimentData, field),
                            getattr(stmt.excluded, field)
                        )
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['url'],
                set_=update_dict
            )
            
            self.session.execute(stmt)
            # Enqueue in same transaction before commit so queue never misses
            self.session.flush()
            urls = [r.get('url') for r in filtered_records if r.get('url')]
            if urls:
                entry_ids = [r[0] for r in self.session.query(SentimentData.entry_id).filter(SentimentData.url.in_(urls)).all()]
                self._enqueue_for_analysis(entry_ids, commit=False)
            self.session.commit()
            success_count = len(filtered_records)
            logger.info(f"Batch inserted {success_count} records.")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during batch upsert: {e}")
            self.session.rollback()
        except Exception as e:
            logger.error(f"Error during insert_batch: {e}", exc_info=True)
        
        return success_count
    
    def log_stored_record(self, url: str):
        """
        Log what was actually stored in DB for a given URL (for debugging coverage gaps).
        Call this after batch commit to see stored values.
        """
        try:
            stored = self.session.query(SentimentData).filter(
                SentimentData.url == url
            ).first()
            
            if stored:
                stored_values = {
                    'entry_id': stored.entry_id,
                    'url': stored.url[:80] if stored.url else None,
                    'platform': stored.platform,
                    'date': stored.date,
                    'published_at': stored.published_at,
                    'published_date': stored.published_date,
                    'user_name': stored.user_name,
                    'user_handle': stored.user_handle,
                    'user_avatar': stored.user_avatar[:80] if stored.user_avatar else None,
                    'user_location': stored.user_location,
                    'likes': stored.likes,
                    'retweets': stored.retweets,
                    'comments': stored.comments,
                    'direct_reach': stored.direct_reach,
                    'cumulative_reach': stored.cumulative_reach,
                    'text': (stored.text[:100] + '...') if stored.text and len(stored.text) > 100 else stored.text,
                }
                logger.info(
                    f"Ingestor: ✓ STORED in DB for url={str(url)[:80]} | "
                    f"platform={stored_values['platform']} | "
                    f"date={stored_values['date']} | "
                    f"user_name={stored_values['user_name']} | "
                    f"user_handle={stored_values['user_handle']} | "
                    f"user_location={stored_values['user_location']} | "
                    f"likes={stored_values['likes']} retweets={stored_values['retweets']} comments={stored_values['comments']} views={stored_values['direct_reach']}"
                )
                logger.debug(
                    f"Ingestor: Full stored record (entry_id={stored_values['entry_id']}): {stored_values}"
                )
        except Exception as e:
            logger.debug(f"Ingestor: Could not log stored record for url={url[:80]}: {e}")
