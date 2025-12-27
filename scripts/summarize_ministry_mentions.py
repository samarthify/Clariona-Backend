#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to show a summary of all mentions for a specific ministry_hint
"""

import sys
import io
from pathlib import Path
from collections import Counter

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SentimentData

def summarize_ministry_mentions(ministry_hint, limit=1000):
    """Show summary of records for a specific ministry_hint."""
    db = SessionLocal()
    try:
        records = db.query(SentimentData).filter(
            SentimentData.ministry_hint == ministry_hint
        ).order_by(SentimentData.created_at.desc()).limit(limit).all()
        
        if not records:
            print(f"No records found with ministry_hint: {ministry_hint}")
            return
        
        print("=" * 100)
        print(f"SUMMARY OF MENTIONS FOR MINISTRY: {ministry_hint.upper()}")
        print("=" * 100)
        print(f"\nTotal Records: {len(records)}\n")
        
        # Sentiment breakdown
        sentiment_counts = Counter([r.sentiment_label or 'None' for r in records])
        print("SENTIMENT BREAKDOWN:")
        for sentiment, count in sentiment_counts.most_common():
            print(f"  {sentiment}: {count} ({count/len(records)*100:.1f}%)")
        
        # Platform breakdown
        platform_counts = Counter([r.platform or 'Unknown' for r in records])
        print(f"\nPLATFORM BREAKDOWN:")
        for platform, count in platform_counts.most_common():
            print(f"  {platform}: {count} ({count/len(records)*100:.1f}%)")
        
        # Issue labels
        issue_counts = Counter([r.issue_label or 'None' for r in records])
        print(f"\nTOP ISSUE LABELS:")
        for issue, count in issue_counts.most_common(10):
            print(f"  {issue}: {count}")
        
        # Countries
        country_counts = Counter([r.country or 'Unknown' for r in records])
        print(f"\nTOP COUNTRIES:")
        for country, count in country_counts.most_common(10):
            print(f"  {country}: {count}")
        
        # Engagement stats
        total_likes = sum([r.likes or 0 for r in records])
        total_comments = sum([r.comments or 0 for r in records])
        total_retweets = sum([r.retweets or 0 for r in records])
        records_with_engagement = sum([1 for r in records if (r.likes or 0) > 0 or (r.comments or 0) > 0])
        
        print(f"\nENGAGEMENT SUMMARY:")
        print(f"  Total Likes: {total_likes:,}")
        print(f"  Total Comments: {total_comments:,}")
        print(f"  Total Retweets: {total_retweets:,}")
        print(f"  Records with Engagement: {records_with_engagement} ({records_with_engagement/len(records)*100:.1f}%)")
        
        # Date range
        dates = [r.date for r in records if r.date]
        if dates:
            print(f"\nDATE RANGE:")
            print(f"  Earliest: {min(dates)}")
            print(f"  Latest: {max(dates)}")
        
        print("\n" + "=" * 100)
        print("RECENT RECORDS (Last 10):")
        print("=" * 100)
        
        for i, record in enumerate(records[:10], 1):
            print(f"\n[{i}] Entry ID: {record.entry_id} | Platform: {record.platform}")
            print(f"    User: {record.user_name or 'N/A'}")
            print(f"    Date: {record.date}")
            print(f"    Sentiment: {record.sentiment_label or 'N/A'} | Issue: {record.issue_label or 'N/A'}")
            if record.text:
                text_preview = record.text[:150].replace('\n', ' ')
                print(f"    Text: {text_preview}{'...' if len(record.text) > 150 else ''}")
            if record.url:
                print(f"    URL: {record.url}")
        
        print("\n" + "=" * 100)
        
    except Exception as e:
        print(f"Error retrieving records: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python summarize_ministry_mentions.py <ministry_hint> [limit]")
        print("Example: python summarize_ministry_mentions.py youth_development")
        sys.exit(1)
    
    ministry_hint = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    summarize_ministry_mentions(ministry_hint, limit)

