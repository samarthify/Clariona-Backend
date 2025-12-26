#!/usr/bin/env python3
"""
Script to find a record by URL and show its created_at timestamp
Run with: python scripts/find_record_by_url.py <url>
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in environment variables")
    print("Please check your .env file")
    sys.exit(1)

print("Connecting to database...\n")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
except Exception as e:
    print(f"Error connecting to database: {e}")
    sys.exit(1)

try:
    # Get URL from command line argument
    if len(sys.argv) < 2:
        print("Usage: python scripts/find_record_by_url.py <url>")
        sys.exit(1)
    
    search_url = sys.argv[1]
    print(f"Searching for URL: {search_url}\n")
    
    # Extract status ID from URL if it's a Twitter/X URL
    status_id = None
    if 'status/' in search_url:
        status_id = search_url.split('status/')[-1].split('?')[0].split('/')[0]
        print(f"Extracted status ID: {status_id}\n")
    
    # Search by URL
    records = db.query(SentimentData).filter(
        or_(
            SentimentData.url == search_url,
            SentimentData.url.like(f'%{status_id}%') if status_id else False,
            SentimentData.url.like(f'%{search_url}%')
        )
    ).all()
    
    # Also try searching by post_id if it's a Twitter status ID
    if status_id:
        records_by_post_id = db.query(SentimentData).filter(
            SentimentData.post_id == status_id
        ).all()
        records.extend(records_by_post_id)
    
    # Remove duplicates
    seen_ids = set()
    unique_records = []
    for record in records:
        if record.entry_id not in seen_ids:
            seen_ids.add(record.entry_id)
            unique_records.append(record)
    
    if unique_records:
        print(f"Found {len(unique_records)} record(s):\n")
        print("="*80)
        
        for idx, record in enumerate(unique_records, 1):
            print(f"\n[{idx}] Entry ID: {record.entry_id}")
            print(f"    URL: {record.url}")
            print(f"    Post ID: {record.post_id or 'N/A'}")
            print(f"    Platform: {record.platform or 'N/A'}")
            print(f"    Created At: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else 'N/A'}")
            print(f"    Run Timestamp: {record.run_timestamp.strftime('%Y-%m-%d %H:%M:%S') if record.run_timestamp else 'N/A'}")
            print(f"    Date: {record.date.strftime('%Y-%m-%d %H:%M:%S') if record.date else 'N/A'}")
            print(f"    Published At: {record.published_at.strftime('%Y-%m-%d %H:%M:%S') if record.published_at else 'N/A'}")
            print(f"    Published Date: {record.published_date.strftime('%Y-%m-%d %H:%M:%S') if record.published_date else 'N/A'}")
            print(f"    Source: {record.source or 'N/A'}")
            print(f"    Title: {record.title[:100] + '...' if record.title and len(record.title) > 100 else record.title or 'N/A'}")
            print(f"    Ministry Hint: {record.ministry_hint or 'N/A'}")
            print(f"    Sentiment: {record.sentiment_label or 'N/A'}")
    else:
        print("No records found with that URL.")
        print("\nTrying broader search...")
        
        # Try searching by just the status ID in various fields
        if status_id:
            print(f"Searching for status ID '{status_id}' in various fields...\n")
            broader_records = db.query(SentimentData).filter(
                or_(
                    SentimentData.post_id == status_id,
                    SentimentData.url.like(f'%{status_id}%'),
                    SentimentData.original_id == status_id
                )
            ).all()
            
            if broader_records:
                print(f"Found {len(broader_records)} record(s) with status ID:\n")
                for idx, record in enumerate(broader_records, 1):
                    print(f"\n[{idx}] Entry ID: {record.entry_id}")
                    print(f"    URL: {record.url}")
                    print(f"    Post ID: {record.post_id or 'N/A'}")
                    print(f"    Created At: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else 'N/A'}")
            else:
                print("Still no records found.")
    
    db.close()
    print('\nSearch complete!')
    
except Exception as e:
    print(f'Error searching records: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

