#!/usr/bin/env python3
"""
Script to check ministry_hint for specific Instagram records
Run with: python scripts/check_instagram_ministry.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, or_, func
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
    # Calculate 24 hours ago
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    # Search keywords from the provided records
    search_keywords = [
        'Adebayo',
        'Luton Town',
        'De Zerbi',
        'Brighton',
        'Premier League',
        'Robert Downey Jr',
        'Gwyneth Paltrow',
        'Marvel',
        'Narnia',
        'calciatoribrutti',
        'skysport',
        'postunited',
        'movietitan',
        'polymarketsports',
        'david_denman',
        '90svibes_and_edits'
    ]
    
    print("Searching for Instagram records with these keywords...")
    print(f"Time range: Last 24 hours (from {twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')})\n")
    
    # Build search conditions
    conditions = []
    for keyword in search_keywords:
        conditions.append(SentimentData.title.ilike(f'%{keyword}%'))
        conditions.append(SentimentData.description.ilike(f'%{keyword}%'))
        conditions.append(SentimentData.content.ilike(f'%{keyword}%'))
        conditions.append(SentimentData.text.ilike(f'%{keyword}%'))
    
    # Search for Instagram records with these keywords
    records = db.query(SentimentData).filter(
        SentimentData.platform == 'Instagram',
        SentimentData.created_at >= twenty_four_hours_ago,
        or_(*conditions)
    ).order_by(SentimentData.created_at.desc()).limit(50).all()
    
    print(f"Found {len(records)} matching Instagram records:\n")
    print("="*80)
    
    if records:
        # Group by ministry_hint
        ministry_counts = {}
        for record in records:
            ministry = record.ministry_hint or 'NULL'
            if ministry not in ministry_counts:
                ministry_counts[ministry] = []
            ministry_counts[ministry].append(record)
        
        print(f"\nMinistry distribution:")
        for ministry, recs in sorted(ministry_counts.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {ministry}: {len(recs)} records")
        
        print(f"\n{'='*80}")
        print("Detailed records:")
        print(f"{'='*80}\n")
        
        for idx, record in enumerate(records, 1):
            print(f"[{idx}] Entry ID: {record.entry_id}")
            print(f"    Ministry Hint: {record.ministry_hint or 'NULL'}")
            print(f"    Platform: {record.platform}")
            print(f"    Created At: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else 'N/A'}")
            print(f"    Source: {record.source or 'N/A'}")
            title = record.title or 'N/A'
            if title != 'N/A' and len(title) > 100:
                title = title[:100] + '...'
            try:
                print(f"    Title: {title}")
            except UnicodeEncodeError:
                print(f"    Title: {title.encode('ascii', 'ignore').decode('ascii')}")
            if record.description:
                desc = record.description[:150] + '...' if len(record.description) > 150 else record.description
                try:
                    print(f"    Description: {desc}")
                except UnicodeEncodeError:
                    print(f"    Description: {desc.encode('ascii', 'ignore').decode('ascii')}")
            print(f"    URL: {record.url[:80] + '...' if record.url and len(record.url) > 80 else record.url or 'N/A'}")
            print()
    else:
        print("No matching records found.")
        print("\nTrying broader search (last 48 hours)...")
        
        forty_eight_hours_ago = now - timedelta(hours=48)
        records = db.query(SentimentData).filter(
            SentimentData.platform == 'Instagram',
            SentimentData.created_at >= forty_eight_hours_ago,
            or_(*conditions)
        ).order_by(SentimentData.created_at.desc()).limit(50).all()
        
        if records:
            print(f"Found {len(records)} matching Instagram records in last 48 hours:\n")
            ministry_counts = {}
            for record in records:
                ministry = record.ministry_hint or 'NULL'
                if ministry not in ministry_counts:
                    ministry_counts[ministry] = []
                ministry_counts[ministry].append(record)
            
            print(f"\nMinistry distribution:")
            for ministry, recs in sorted(ministry_counts.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"  {ministry}: {len(recs)} records")
            
            print(f"\n{'='*80}")
            print("Sample records:")
            print(f"{'='*80}\n")
            
            for idx, record in enumerate(records[:10], 1):
                print(f"[{idx}] Entry ID: {record.entry_id}")
                print(f"    Ministry Hint: {record.ministry_hint or 'NULL'}")
                print(f"    Platform: {record.platform}")
                print(f"    Created At: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else 'N/A'}")
                title = record.title or 'N/A'
                if title != 'N/A' and len(title) > 100:
                    title = title[:100] + '...'
                try:
                    print(f"    Title: {title}")
                except UnicodeEncodeError:
                    print(f"    Title: {title.encode('ascii', 'ignore').decode('ascii')}")
                print()
        else:
            print("Still no matching records found.")
    
    db.close()
    print('\nCheck complete!')
    
except Exception as e:
    print(f'Error searching records: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

