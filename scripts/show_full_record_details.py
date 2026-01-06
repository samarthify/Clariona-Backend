#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to show full details of a specific record by entry_id
"""

import sys
import io
import json
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import SessionLocal
from src.api.models import SentimentData

def show_full_record(entry_id):
    """Show full details of a record by entry_id."""
    db = SessionLocal()
    try:
        record = db.query(SentimentData).filter(SentimentData.entry_id == entry_id).first()
        
        if not record:
            print(f"Record with entry_id {entry_id} not found.")
            return
        
        print("=" * 100)
        print("FULL RECORD DETAILS")
        print("=" * 100)
        
        print(f"\nBASIC INFORMATION:")
        print(f"  Entry ID: {record.entry_id}")
        print(f"  Post ID: {record.post_id}")
        print(f"  Original ID: {record.original_id}")
        print(f"  Platform: {record.platform}")
        print(f"  URL: {record.url}")
        print(f"  Source: {record.source}")
        print(f"  Source URL: {record.source_url}")
        print(f"  Source Name: {record.source_name}")
        print(f"  Source Type: {record.source_type}")
        
        print(f"\nUSER INFORMATION:")
        print(f"  User Name: {record.user_name}")
        print(f"  User Handle: {record.user_handle}")
        print(f"  User Avatar: {record.user_avatar}")
        print(f"  User Location: {record.user_location}")
        print(f"  User ID: {record.user_id}")
        
        print(f"\nCONTENT:")
        print(f"  Title: {record.title}")
        print(f"  Description: {record.description}")
        print(f"  Text: {record.text}")
        print(f"  Content: {record.content}")
        print(f"  Query: {record.query}")
        print(f"  Language: {record.language}")
        print(f"  Tags: {record.tags}")
        
        print(f"\nDATES & TIMESTAMPS:")
        print(f"  Published Date: {record.published_date}")
        print(f"  Published At: {record.published_at}")
        print(f"  Date: {record.date}")
        print(f"  Created At: {record.created_at}")
        print(f"  Run Timestamp: {record.run_timestamp}")
        
        print(f"\nENGAGEMENT METRICS:")
        print(f"  Likes: {record.likes}")
        print(f"  Comments: {record.comments}")
        print(f"  Retweets: {record.retweets}")
        print(f"  Direct Reach: {record.direct_reach}")
        print(f"  Cumulative Reach: {record.cumulative_reach}")
        print(f"  Domain Reach: {record.domain_reach}")
        print(f"  Children: {record.children}")
        print(f"  Score: {record.score}")
        print(f"  Favorite: {record.favorite}")
        
        print(f"\nSENTIMENT ANALYSIS:")
        print(f"  Sentiment Label: {record.sentiment_label}")
        print(f"  Sentiment Score: {record.sentiment_score}")
        print(f"  Sentiment Justification: {record.sentiment_justification}")
        print(f"  Tone: {record.tone}")
        
        print(f"\nLOCATION CLASSIFICATION:")
        print(f"  Location Label: {record.location_label}")
        print(f"  Location Confidence: {record.location_confidence}")
        print(f"  Country: {record.country}")
        print(f"  User Location: {record.user_location}")
        
        print(f"\nISSUE MAPPING:")
        print(f"  Issue Label: {record.issue_label}")
        print(f"  Issue Slug: {record.issue_slug}")
        print(f"  Issue Confidence: {record.issue_confidence}")
        print(f"  Issue Keywords: {json.dumps(record.issue_keywords, indent=2) if record.issue_keywords else None}")
        print(f"  Ministry Hint: {record.ministry_hint}")
        
        print(f"\nOTHER METADATA:")
        print(f"  Alert ID: {record.alert_id}")
        print(f"  Alert Name: {record.alert_name}")
        print(f"  Type: {record.type}")
        print(f"  Parent URL: {record.parent_url}")
        print(f"  Parent ID: {record.parent_id}")
        print(f"  File Source: {record.file_source}")
        
        print("\n" + "=" * 100)
        
    except Exception as e:
        print(f"Error retrieving record: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python show_full_record_details.py <entry_id>")
        print("Example: python show_full_record_details.py 179986")
        sys.exit(1)
    
    try:
        entry_id = int(sys.argv[1])
        show_full_record(entry_id)
    except ValueError:
        print("Error: entry_id must be an integer")
        sys.exit(1)

