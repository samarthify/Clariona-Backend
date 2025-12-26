#!/usr/bin/env python3
"""
Script to count records with a specific ministry_hint in the last 24 hours
Run with: python scripts/count_ministry_hint.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, func, or_
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
    # Get the ministry_hint from command line argument or use default
    ministry_hint = sys.argv[1] if len(sys.argv) > 1 else 'non_governance'
    
    # Calculate 24 hours ago
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    print(f"Counting records with ministry_hint = '{ministry_hint}'")
    print(f"Time range: Last 24 hours (from {twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')})\n")
    
    # Count total records in the last 24 hours
    total_count = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago
    ).count()
    
    # Count records with the specified ministry_hint in the last 24 hours
    # Using created_at as the timestamp field
    count = db.query(SentimentData).filter(
        SentimentData.ministry_hint == ministry_hint,
        SentimentData.created_at >= twenty_four_hours_ago
    ).count()
    
    # Also get count using run_timestamp for comparison
    count_run_timestamp = db.query(SentimentData).filter(
        SentimentData.ministry_hint == ministry_hint,
        SentimentData.run_timestamp >= twenty_four_hours_ago
    ).count()
    
    # Calculate percentage
    percentage = (count / total_count * 100) if total_count > 0 else 0
    
    # Count records with published_at populated
    count_with_published_at = db.query(SentimentData).filter(
        SentimentData.ministry_hint == ministry_hint,
        SentimentData.created_at >= twenty_four_hours_ago,
        SentimentData.published_at.isnot(None)
    ).count()
    
    # Count records with published_date populated
    count_with_published_date = db.query(SentimentData).filter(
        SentimentData.ministry_hint == ministry_hint,
        SentimentData.created_at >= twenty_four_hours_ago,
        SentimentData.published_date.isnot(None)
    ).count()
    
    # Count records with either field populated
    count_with_either = db.query(SentimentData).filter(
        SentimentData.ministry_hint == ministry_hint,
        SentimentData.created_at >= twenty_four_hours_ago,
        or_(
            SentimentData.published_at.isnot(None),
            SentimentData.published_date.isnot(None)
        )
    ).count()
    
    # Count records without either field
    count_without_either = count - count_with_either
    published_at_percentage = (count_with_published_at / count * 100) if count > 0 else 0
    published_date_percentage = (count_with_published_date / count * 100) if count > 0 else 0
    either_percentage = (count_with_either / count * 100) if count > 0 else 0
    
    print(f"Results:")
    print(f"Total records in last 24 hours: {total_count:,}")
    print(f"Records with ministry_hint = '{ministry_hint}' in last 24 hours:")
    print(f"  - Using created_at: {count:,} ({percentage:.2f}% of total)")
    print(f"  - Using run_timestamp: {count_run_timestamp:,}")
    print(f"\nPublished date fields status:")
    print(f"  - Records with published_at populated: {count_with_published_at:,} ({published_at_percentage:.2f}%)")
    print(f"  - Records with published_date populated: {count_with_published_date:,} ({published_date_percentage:.2f}%)")
    print(f"  - Records with either field populated: {count_with_either:,} ({either_percentage:.2f}%)")
    print(f"  - Records without either field: {count_without_either:,} ({100 - either_percentage:.2f}%)")
    
    # Show breakdown by platform if there are records
    if count > 0:
        print(f"\nBreakdown by platform (using created_at):")
        platform_counts = db.query(
            SentimentData.platform,
            func.count(SentimentData.entry_id).label('count')
        ).filter(
            SentimentData.ministry_hint == ministry_hint,
            SentimentData.created_at >= twenty_four_hours_ago
        ).group_by(SentimentData.platform).all()
        
        for platform, platform_count in sorted(platform_counts, key=lambda x: x[1], reverse=True):
            platform_name = platform or 'NULL'
            print(f"  {platform_name}: {platform_count:,}")
    
    # Show records with published_date populated
    if count_with_published_date > 0:
        print(f"\n{'='*80}")
        print(f"Records with published_date populated ({count_with_published_date} records):")
        print(f"{'='*80}")
        
        records_with_date = db.query(SentimentData).filter(
            SentimentData.ministry_hint == ministry_hint,
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.published_date.isnot(None)
        ).order_by(SentimentData.published_date.desc()).all()
        
        for idx, record in enumerate(records_with_date, 1):
            print(f"\n[{idx}] Entry ID: {record.entry_id}")
            print(f"    Platform: {record.platform or 'N/A'}")
            print(f"    Published Date: {record.published_date.strftime('%Y-%m-%d %H:%M:%S') if record.published_date else 'N/A'}")
            print(f"    Published At: {record.published_at.strftime('%Y-%m-%d %H:%M:%S') if record.published_at else 'N/A'}")
            print(f"    Created At: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else 'N/A'}")
            print(f"    Title: {record.title[:100] + '...' if record.title and len(record.title) > 100 else record.title or 'N/A'}")
            print(f"    Source: {record.source or 'N/A'}")
            print(f"    URL: {record.url[:80] + '...' if record.url and len(record.url) > 80 else record.url or 'N/A'}")
            if record.description:
                desc = record.description[:150] + '...' if len(record.description) > 150 else record.description
                print(f"    Description: {desc}")
    
    db.close()
    print('\nCheck complete!')
    
except Exception as e:
    print(f'Error counting records: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

