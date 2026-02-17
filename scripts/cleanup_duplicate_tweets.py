"""
Cleanup script to remove duplicate Twitter/X records using URL normalization.

This script uses the same URL normalization logic as DataIngestor to:
1. Find duplicate tweets (same tweet ID, different URL formats)
2. Normalize all URLs to consistent format
3. Keep the best record (most complete data) and delete duplicates
"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import func, and_
from src.api.database import SessionLocal
from src.api.models import SentimentData, SentimentEmbedding
from src.services.data_ingestor import DataIngestor
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_twitter_id(url_or_id: str) -> str:
    """Extract Twitter/X tweet ID from URL (same logic as DataIngestor)."""
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
    match = re.search(r'(\d{15,})', url_str)
    if match:
        return match.group(1)
    
    return None


def normalize_twitter_url(url: str) -> str:
    """Normalize Twitter/X URL to consistent format (same logic as DataIngestor)."""
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
                print(f"  Fixed concatenated URL, using: {url_str[:100]}")
                break
    
    # Check if it's a Twitter/X URL
    is_twitter_url = (
        'twitter.com' in url_str.lower() or 
        'x.com' in url_str.lower() or 
        url_str.startswith('apify://twitter/')
    )
    
    if is_twitter_url:
        tweet_id = extract_twitter_id(url_str)
        if tweet_id:
            # Use consistent Twitter URL format
            return f"https://twitter.com/i/web/status/{tweet_id}"
    
    return url_str


def find_duplicate_tweets(session) -> Dict[str, List[SentimentData]]:
    """Find duplicate tweets by normalized URL."""
    logger.info("Finding duplicate tweets...")
    
    # Get all Twitter records
    twitter_records = session.query(SentimentData).filter(
        SentimentData.platform == 'twitter'
    ).all()
    
    logger.info(f"Found {len(twitter_records)} Twitter records")
    
    # Group by normalized URL
    normalized_groups: Dict[str, List[SentimentData]] = {}
    
    for record in twitter_records:
        if not record.url:
            continue
        
        normalized_url = normalize_twitter_url(record.url)
        
        if normalized_url not in normalized_groups:
            normalized_groups[normalized_url] = []
        
        normalized_groups[normalized_url].append(record)
    
    # Find groups with duplicates
    duplicates = {url: records for url, records in normalized_groups.items() if len(records) > 1}
    
    logger.info(f"Found {len(duplicates)} groups with duplicates")
    total_duplicates = sum(len(records) - 1 for records in duplicates.values())
    logger.info(f"Total duplicate records to remove: {total_duplicates}")
    
    return duplicates


def select_best_record(records: List[SentimentData]) -> SentimentData:
    """Select the best record to keep (most complete data, prefer real URLs over apify://)."""
    if len(records) == 1:
        return records[0]
    
    # Score records based on completeness and URL quality
    def score_record(record: SentimentData) -> int:
        score = 0
        
        # CRITICAL: Prefer real Twitter URLs (twitter.com/x.com) over apify:// ones
        url = record.url or ''
        if url.startswith('https://twitter.com') or url.startswith('https://x.com'):
            score += 50  # Big bonus for real URLs
        elif url.startswith('apify://twitter/'):
            score -= 20  # Penalty for apify URLs
        
        # Prefer records with more data
        if record.text and len(record.text) > 50:
            score += 10
        if record.user_name:
            score += 5
        if record.user_handle:
            score += 5
        if record.likes is not None:
            score += 3
        if record.comments is not None:
            score += 3
        if record.direct_reach is not None:
            score += 3
        if record.sentiment_label:
            score += 5  # Prefer analyzed records
        if record.published_at:
            score += 2
        if record.created_at:
            # Prefer newer records (more recent collection)
            score += 1
        
        return score
    
    # Sort by score (highest first), then by created_at (newest first)
    sorted_records = sorted(records, key=lambda r: (score_record(r), r.created_at or r.run_timestamp), reverse=True)
    
    return sorted_records[0]


def cleanup_duplicates(dry_run: bool = True) -> Tuple[int, int]:
    """
    Clean up duplicate tweets.
    
    Args:
        dry_run: If True, only report what would be deleted without actually deleting
        
    Returns:
        Tuple of (records_updated, records_deleted)
    """
    session = SessionLocal()
    
    try:
        # First, fix concatenated URLs in the database
        logger.info("Step 1: Fixing concatenated URLs...")
        twitter_records = session.query(SentimentData).filter(
            SentimentData.platform == 'twitter',
            SentimentData.url.isnot(None)
        ).all()
        
        fixed_urls = 0
        for record in twitter_records:
            if not record.url:
                continue
            
            # Check if URL is concatenated (has multiple https://)
            if 'https://' in record.url and record.url.count('https://') > 1:
                normalized = normalize_twitter_url(record.url)
                if normalized != record.url:
                    logger.info(f"  Fixing concatenated URL: {record.url[:100]} -> {normalized}")
                    fixed_urls += 1
                    if not dry_run:
                        record.url = normalized
        
        if fixed_urls > 0 and not dry_run:
            session.commit()
            logger.info(f"  Fixed {fixed_urls} concatenated URLs")
        
        # Now find duplicates by normalized URL
        logger.info("\nStep 2: Finding duplicates by normalized URL...")
        duplicates = find_duplicate_tweets(session)
        
        records_updated = 0
        records_deleted = 0
        batch_size = 100  # Commit every 100 operations
        processed = 0
        total_groups = len(duplicates)
        
        for idx, (normalized_url, records) in enumerate(duplicates.items(), 1):
            if len(records) <= 1:
                continue
            
            # Select best record to keep
            best_record = select_best_record(records)
            records_to_delete = [r for r in records if r.entry_id != best_record.entry_id]
            
            if idx % 10 == 0 or idx == 1:  # Log every 10th group or first
                logger.info(f"\n[{idx}/{total_groups}] Normalized URL: {normalized_url}")
                logger.info(f"  Total records: {len(records)}")
                logger.info(f"  Keeping: entry_id={best_record.entry_id}, url={best_record.url}")
                logger.info(f"  Deleting: {len(records_to_delete)} records")
            
            # Update best record's URL to normalized format if different
            if best_record.url != normalized_url:
                if idx % 10 == 0 or idx == 1:
                    logger.info(f"  Updating URL: {best_record.url[:100]} -> {normalized_url}")
                records_updated += 1
                if not dry_run:
                    best_record.url = normalized_url
                processed += 1
            
            # Delete duplicates (first delete related embeddings, then the sentiment data)
            for dup_record in records_to_delete:
                if idx % 10 == 0 or idx == 1:
                    logger.info(f"    - entry_id={dup_record.entry_id}, url={dup_record.url[:100]}")
                records_deleted += 1
                if not dry_run:
                    # Delete related embedding first to avoid foreign key constraint issues
                    embedding = session.query(SentimentEmbedding).filter(
                        SentimentEmbedding.entry_id == dup_record.entry_id
                    ).first()
                    if embedding:
                        session.delete(embedding)
                    # Then delete the sentiment data record
                    session.delete(dup_record)
                processed += 1
                
                # Commit in batches to avoid long transactions
                if not dry_run and processed % batch_size == 0:
                    try:
                        session.commit()
                        logger.info(f"  ✓ Committed batch ({processed} operations so far)")
                    except Exception as e:
                        logger.error(f"  ✗ Error committing batch: {e}")
                        session.rollback()
                        raise
        
        # Final commit for any remaining changes
        if not dry_run and processed % batch_size != 0:
            try:
                session.commit()
                logger.info(f"  ✓ Committed final batch")
            except Exception as e:
                logger.error(f"  ✗ Error committing final batch: {e}")
                session.rollback()
                raise
        
        if not dry_run:
            logger.info(f"\n✅ Cleanup complete: Fixed {fixed_urls} concatenated URLs, Updated {records_updated} URLs, Deleted {records_deleted} duplicates")
        else:
            logger.info(f"\n🔍 DRY RUN: Would fix {fixed_urls} concatenated URLs, Would update {records_updated} URLs, Would delete {records_deleted} duplicates")
            logger.info("Run with --execute to perform the cleanup")
        
        return records_updated, records_deleted
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up duplicate Twitter/X records')
    parser.add_argument('--execute', action='store_true', help='Actually perform the cleanup (default is dry-run)')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 80)
    else:
        logger.info("=" * 80)
        logger.info("EXECUTION MODE - Changes will be committed to database")
        logger.info("=" * 80)
    
    try:
        updated, deleted = cleanup_duplicates(dry_run=dry_run)
        
        if dry_run:
            print(f"\n🔍 DRY RUN RESULTS:")
            print(f"   Would update {updated} URLs")
            print(f"   Would delete {deleted} duplicate records")
            print(f"\n   Run with --execute to perform the cleanup")
        else:
            print(f"\n✅ CLEANUP COMPLETE:")
            print(f"   Updated {updated} URLs")
            print(f"   Deleted {deleted} duplicate records")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
