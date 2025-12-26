#!/usr/bin/env python3
"""
Script to check issue_slug values for records with specific ministry_hint values
Run with: python scripts/check_ministry_issue_slugs.py
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
    # Get all records (no time restriction)
    print(f"Checking issue_slug for records with ministry_hint = 'sports_development' and 'art_culture_creative'")
    print(f"Checking all records in database (no time restriction)\n")
    
    # Get records with sports_development
    sports_records = db.query(SentimentData).filter(
        SentimentData.ministry_hint == 'sports_development'
    ).limit(1000).all()
    
    # Get records with art_culture_creative
    art_records = db.query(SentimentData).filter(
        SentimentData.ministry_hint == 'art_culture_creative'
    ).limit(1000).all()
    
    print(f"Found {len(sports_records)} records with ministry_hint = 'sports_development'")
    print(f"Found {len(art_records)} records with ministry_hint = 'art_culture_creative'\n")
    
    # Analyze issue_slug distribution for sports_development
    if sports_records:
        print("="*80)
        print("SPORTS_DEVELOPMENT - Issue Slug Distribution:")
        print("="*80)
        
        issue_slug_counts = {}
        for record in sports_records:
            issue_slug = record.issue_slug or 'NULL'
            if issue_slug not in issue_slug_counts:
                issue_slug_counts[issue_slug] = 0
            issue_slug_counts[issue_slug] += 1
        
        for issue_slug, count in sorted(issue_slug_counts.items(), key=lambda x: x[1], reverse=True):
            try:
                print(f"  {issue_slug}: {count:,} records")
            except UnicodeEncodeError:
                print(f"  {issue_slug.encode('ascii', 'ignore').decode('ascii')}: {count:,} records")
        
        # Show sample records
        print(f"\nSample records (first 10):")
        print("-"*80)
        for idx, record in enumerate(sports_records[:10], 1):
            print(f"\n[{idx}] Entry ID: {record.entry_id}")
            print(f"    Platform: {record.platform or 'N/A'}")
            print(f"    Issue Slug: {record.issue_slug or 'NULL'}")
            print(f"    Issue Label: {record.issue_label or 'NULL'}")
            print(f"    Issue Confidence: {record.issue_confidence or 'N/A'}")
            title = record.title or record.text or 'N/A'
            if title != 'N/A' and len(title) > 100:
                title = title[:100] + '...'
            try:
                print(f"    Title/Text: {title}")
            except UnicodeEncodeError:
                print(f"    Title/Text: {title.encode('ascii', 'ignore').decode('ascii')}")
    
    # Analyze issue_slug distribution for art_culture_creative
    if art_records:
        print(f"\n{'='*80}")
        print("ART_CULTURE_CREATIVE - Issue Slug Distribution:")
        print("="*80)
        
        issue_slug_counts = {}
        for record in art_records:
            issue_slug = record.issue_slug or 'NULL'
            if issue_slug not in issue_slug_counts:
                issue_slug_counts[issue_slug] = 0
            issue_slug_counts[issue_slug] += 1
        
        for issue_slug, count in sorted(issue_slug_counts.items(), key=lambda x: x[1], reverse=True):
            try:
                print(f"  {issue_slug}: {count:,} records")
            except UnicodeEncodeError:
                print(f"  {issue_slug.encode('ascii', 'ignore').decode('ascii')}: {count:,} records")
        
        # Show sample records
        print(f"\nSample records (first 10):")
        print("-"*80)
        for idx, record in enumerate(art_records[:10], 1):
            print(f"\n[{idx}] Entry ID: {record.entry_id}")
            print(f"    Platform: {record.platform or 'N/A'}")
            print(f"    Issue Slug: {record.issue_slug or 'NULL'}")
            print(f"    Issue Label: {record.issue_label or 'NULL'}")
            print(f"    Issue Confidence: {record.issue_confidence or 'N/A'}")
            title = record.title or record.text or 'N/A'
            if title != 'N/A' and len(title) > 100:
                title = title[:100] + '...'
            try:
                print(f"    Title/Text: {title}")
            except UnicodeEncodeError:
                print(f"    Title/Text: {title.encode('ascii', 'ignore').decode('ascii')}")
    
    # Summary statistics
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print("="*80)
    
    sports_with_issue = sum(1 for r in sports_records if r.issue_slug)
    sports_without_issue = len(sports_records) - sports_with_issue
    art_with_issue = sum(1 for r in art_records if r.issue_slug)
    art_without_issue = len(art_records) - art_with_issue
    
    print(f"\nSports Development:")
    print(f"  Total records: {len(sports_records):,}")
    print(f"  Records with issue_slug: {sports_with_issue:,} ({sports_with_issue/len(sports_records)*100 if sports_records else 0:.2f}%)")
    print(f"  Records without issue_slug: {sports_without_issue:,} ({sports_without_issue/len(sports_records)*100 if sports_records else 0:.2f}%)")
    
    print(f"\nArt Culture Creative:")
    print(f"  Total records: {len(art_records):,}")
    print(f"  Records with issue_slug: {art_with_issue:,} ({art_with_issue/len(art_records)*100 if art_records else 0:.2f}%)")
    print(f"  Records without issue_slug: {art_without_issue:,} ({art_without_issue/len(art_records)*100 if art_records else 0:.2f}%)")
    
    db.close()
    print('\nCheck complete!')
    
except Exception as e:
    print(f'Error checking records: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

