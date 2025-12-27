#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to show all mentions for a specific ministry_hint
"""

import sys
import io
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SentimentData

def show_ministry_mentions(ministry_hint, limit=100):
    """Show all records for a specific ministry_hint."""
    db = SessionLocal()
    try:
        records = db.query(SentimentData).filter(
            SentimentData.ministry_hint == ministry_hint
        ).order_by(SentimentData.created_at.desc()).limit(limit).all()
        
        if not records:
            print(f"No records found with ministry_hint: {ministry_hint}")
            return
        
        print("=" * 100)
        print(f"ALL MENTIONS FOR MINISTRY: {ministry_hint.upper()}")
        print("=" * 100)
        print(f"\nFound {len(records)} record(s):\n")
        
        for i, record in enumerate(records, 1):
            print(f"\n{'='*100}")
            print(f"RECORD #{i}")
            print(f"{'='*100}")
            
            print(f"\nBASIC INFO:")
            print(f"  Entry ID: {record.entry_id}")
            print(f"  Platform: {record.platform}")
            print(f"  URL: {record.url}")
            print(f"  Post ID: {record.post_id}")
            
            print(f"\nUSER INFO:")
            print(f"  User Name: {record.user_name or 'N/A'}")
            print(f"  User Handle: {record.user_handle or 'N/A'}")
            
            print(f"\nCONTENT:")
            if record.title:
                print(f"  Title: {record.title[:200]}")
            if record.text:
                print(f"  Text: {record.text[:500]}{'...' if record.text and len(record.text) > 500 else ''}")
            if record.description:
                print(f"  Description: {record.description[:500]}{'...' if record.description and len(record.description) > 500 else ''}")
            
            print(f"\nDATES:")
            print(f"  Date: {record.date}")
            print(f"  Published At: {record.published_at}")
            print(f"  Created At: {record.created_at}")
            
            print(f"\nENGAGEMENT:")
            print(f"  Likes: {record.likes or 'N/A'}")
            print(f"  Comments: {record.comments or 'N/A'}")
            print(f"  Retweets: {record.retweets or 'N/A'}")
            
            print(f"\nSENTIMENT:")
            print(f"  Sentiment Label: {record.sentiment_label or 'N/A'}")
            print(f"  Sentiment Score: {record.sentiment_score or 'N/A'}")
            if record.sentiment_justification:
                print(f"  Justification: {record.sentiment_justification[:300]}{'...' if record.sentiment_justification and len(record.sentiment_justification) > 300 else ''}")
            
            print(f"\nISSUE MAPPING:")
            print(f"  Issue Label: {record.issue_label or 'N/A'}")
            print(f"  Issue Slug: {record.issue_slug or 'N/A'}")
            print(f"  Issue Confidence: {record.issue_confidence or 'N/A'}")
            
            print(f"\nLOCATION:")
            print(f"  Country: {record.country or 'N/A'}")
            print(f"  Location Label: {record.location_label or 'N/A'}")
            
            print()
        
        print("\n" + "=" * 100)
        print(f"SUMMARY: Found {len(records)} total records for {ministry_hint}")
        print("=" * 100)
        
    except Exception as e:
        print(f"Error retrieving records: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python show_ministry_mentions.py <ministry_hint> [limit]")
        print("Example: python show_ministry_mentions.py youth_development")
        print("Example: python show_ministry_mentions.py youth_development 50")
        sys.exit(1)
    
    ministry_hint = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    show_ministry_mentions(ministry_hint, limit)

