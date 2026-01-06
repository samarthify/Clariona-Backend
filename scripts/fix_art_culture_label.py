#!/usr/bin/env python3
"""
Script to fix issue_label for records with issue_slug = 'art_culture_creative'
Updates issue_label to 'Art Culture Creative' to match the JSON file
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
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
    # First, check how many records need updating
    count_query = db.query(SentimentData).filter(
        SentimentData.issue_slug == 'art_culture_creative'
    ).count()
    
    print(f"Found {count_query:,} records with issue_slug = 'art_culture_creative'")
    
    # Check current label values
    current_labels = db.query(SentimentData.issue_label).filter(
        SentimentData.issue_slug == 'art_culture_creative'
    ).distinct().all()
    
    print(f"\nCurrent issue_label values:")
    for label_tuple in current_labels:
        label = label_tuple[0]
        count = db.query(SentimentData).filter(
            SentimentData.issue_slug == 'art_culture_creative',
            SentimentData.issue_label == label
        ).count()
        print(f"  '{label}': {count:,} records")
    
    # Ask for confirmation
    print(f"\nWill update all records to have issue_label = 'Art Culture Creative'")
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Update cancelled.")
        db.close()
        sys.exit(0)
    
    # Update all records
    print("\nUpdating records...")
    update_query = text("""
        UPDATE sentiment_data 
        SET issue_label = 'Art Culture Creative'
        WHERE issue_slug = 'art_culture_creative'
    """)
    
    result = db.execute(update_query)
    db.commit()
    
    updated_count = result.rowcount
    print(f"\nSuccessfully updated {updated_count:,} records")
    
    # Verify the update
    verify_count = db.query(SentimentData).filter(
        SentimentData.issue_slug == 'art_culture_creative',
        SentimentData.issue_label == 'Art Culture Creative'
    ).count()
    
    print(f"Verification: {verify_count:,} records now have issue_label = 'Art Culture Creative'")
    
    # Show a few sample records
    print(f"\nSample updated records:")
    samples = db.query(SentimentData).filter(
        SentimentData.issue_slug == 'art_culture_creative',
        SentimentData.issue_label == 'Art Culture Creative'
    ).limit(5).all()
    
    for idx, record in enumerate(samples, 1):
        print(f"\n[{idx}] Entry ID: {record.entry_id}")
        print(f"    Issue Slug: {record.issue_slug}")
        print(f"    Issue Label: {record.issue_label}")
        print(f"    Platform: {record.platform or 'N/A'}")
    
    db.close()
    print('\nUpdate complete!')
    
except Exception as e:
    print(f'Error updating records: {e}')
    import traceback
    traceback.print_exc()
    db.rollback()
    db.close()
    sys.exit(1)


