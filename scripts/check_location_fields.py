#!/usr/bin/env python3
"""
Script to check how many records have country/region/location information populated
Run with: python scripts/check_location_fields.py
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
    # Calculate 24 hours ago
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    print(f"Checking location fields for records in last 24 hours")
    print(f"Time range: {twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Count total records in last 24 hours
    total_count = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago
    ).count()
    
    # Count records with country populated
    count_with_country = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago,
        SentimentData.country.isnot(None)
    ).count()
    
    # Count records with user_location populated
    count_with_user_location = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago,
        SentimentData.user_location.isnot(None)
    ).count()
    
    # Count records with location_label populated (enhanced location classification)
    count_with_location_label = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago,
        SentimentData.location_label.isnot(None)
    ).count()
    
    # Count records with any location field populated
    count_with_any_location = db.query(SentimentData).filter(
        SentimentData.created_at >= twenty_four_hours_ago,
        or_(
            SentimentData.country.isnot(None),
            SentimentData.user_location.isnot(None),
            SentimentData.location_label.isnot(None)
        )
    ).count()
    
    # Count records without any location field
    count_without_location = total_count - count_with_any_location
    
    # Calculate percentages
    country_percentage = (count_with_country / total_count * 100) if total_count > 0 else 0
    user_location_percentage = (count_with_user_location / total_count * 100) if total_count > 0 else 0
    location_label_percentage = (count_with_location_label / total_count * 100) if total_count > 0 else 0
    any_location_percentage = (count_with_any_location / total_count * 100) if total_count > 0 else 0
    
    print(f"Results:")
    print(f"{'='*80}")
    print(f"Total records in last 24 hours: {total_count:,}\n")
    
    print(f"Location field breakdown:")
    print(f"  - Records with 'country' populated: {count_with_country:,} ({country_percentage:.2f}%)")
    print(f"  - Records with 'user_location' populated: {count_with_user_location:,} ({user_location_percentage:.2f}%)")
    print(f"  - Records with 'location_label' populated: {count_with_location_label:,} ({location_label_percentage:.2f}%)")
    print(f"  - Records with ANY location field: {count_with_any_location:,} ({any_location_percentage:.2f}%)")
    print(f"  - Records without ANY location field: {count_without_location:,} ({100 - any_location_percentage:.2f}%)")
    
    # Show unique values for country field
    if count_with_country > 0:
        print(f"\n{'='*80}")
        print(f"Unique country values (top 20):")
        country_counts = db.query(
            SentimentData.country,
            func.count(SentimentData.entry_id).label('count')
        ).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.country.isnot(None)
        ).group_by(SentimentData.country).order_by(func.count(SentimentData.entry_id).desc()).limit(20).all()
        
        for country, count in country_counts:
            print(f"  {country or 'NULL'}: {count:,}")
    
    # Show unique values for location_label field
    if count_with_location_label > 0:
        print(f"\n{'='*80}")
        print(f"Unique location_label values (top 20):")
        location_counts = db.query(
            SentimentData.location_label,
            func.count(SentimentData.entry_id).label('count')
        ).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.location_label.isnot(None)
        ).group_by(SentimentData.location_label).order_by(func.count(SentimentData.entry_id).desc()).limit(20).all()
        
        for location, count in location_counts:
            print(f"  {location or 'NULL'}: {count:,}")
    
    # Breakdown by platform - get all platforms first, then count for each
    print(f"\n{'='*80}")
    print(f"Location data by platform:")
    platforms = db.query(SentimentData.platform).filter(
        SentimentData.created_at >= twenty_four_hours_ago
    ).distinct().all()
    
    print(f"\n{'Platform':<20} {'Total':<12} {'Country':<12} {'User Loc':<12} {'Loc Label':<12} {'Any Loc':<12}")
    print("-" * 80)
    
    for platform_tuple in platforms:
        platform = platform_tuple[0]
        platform_name = platform or 'NULL'
        
        # Count total for this platform
        total = db.query(SentimentData).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.platform == platform
        ).count()
        
        # Count with country
        with_country = db.query(SentimentData).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.platform == platform,
            SentimentData.country.isnot(None)
        ).count()
        
        # Count with user_location
        with_user_loc = db.query(SentimentData).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.platform == platform,
            SentimentData.user_location.isnot(None)
        ).count()
        
        # Count with location_label
        with_loc_label = db.query(SentimentData).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.platform == platform,
            SentimentData.location_label.isnot(None)
        ).count()
        
        # Count with any location
        with_any = db.query(SentimentData).filter(
            SentimentData.created_at >= twenty_four_hours_ago,
            SentimentData.platform == platform,
            or_(
                SentimentData.country.isnot(None),
                SentimentData.user_location.isnot(None),
                SentimentData.location_label.isnot(None)
            )
        ).count()
        
        print(f"{platform_name:<20} {total:<12,} {with_country:<12,} {with_user_loc:<12,} {with_loc_label:<12,} {with_any:<12,}")
    
    db.close()
    print('\nCheck complete!')
    
except Exception as e:
    print(f'Error checking location fields: {e}')
    import traceback
    traceback.print_exc()
    db.close()
    sys.exit(1)

