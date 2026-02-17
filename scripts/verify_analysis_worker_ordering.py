#!/usr/bin/env python3
"""
Verify that AnalysisWorker is processing the latest records first.
Cross-references analyzed entry_ids with the database to check ordering.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData

# Load environment
env_paths = [
    Path(__file__).parent.parent / 'config' / '.env',
    Path(__file__).parent.parent / '.env',
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

# Entry IDs from the logs you provided
analyzed_entry_ids = [
    155862, 155533, 155554, 156283, 155867, 155559, 155558, 155556, 156281,
    155765, 155872, 155866, 155863, 155864, 155871, 155557, 155865, 156282,
    155869, 155661, 155870, 155874, 155868, 155555, 155873, 155875
]

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    print("=" * 80)
    print("VERIFICATION: AnalysisWorker Record Ordering")
    print("=" * 80)
    print()
    
    # 1. Get the analyzed records
    print("1. Checking analyzed entry_ids from logs:")
    print("-" * 80)
    analyzed_records = db.query(
        SentimentData.entry_id,
        SentimentData.run_timestamp,
        SentimentData.created_at,
        SentimentData.sentiment_label
    ).filter(
        SentimentData.entry_id.in_(analyzed_entry_ids)
    ).order_by(desc(SentimentData.run_timestamp)).all()
    
    print(f"Found {len(analyzed_records)} analyzed records in DB")
    print()
    
    if analyzed_records:
        print("Analyzed records (ordered by run_timestamp DESC):")
        for rec in analyzed_records[:10]:  # Show first 10
            print(f"  entry_id={rec.entry_id:6d} | run_timestamp={rec.run_timestamp} | sentiment={rec.sentiment_label}")
        if len(analyzed_records) > 10:
            print(f"  ... and {len(analyzed_records) - 10} more")
        print()
    
    # 2. Get the most recent unanalyzed records (what should be processed next)
    print("2. Most recent UNANALYZED records (what should be processed next):")
    print("-" * 80)
    unanalyzed = db.query(
        SentimentData.entry_id,
        SentimentData.run_timestamp,
        SentimentData.created_at
    ).filter(
        SentimentData.sentiment_label.is_(None)
    ).order_by(desc(SentimentData.run_timestamp)).limit(50).all()
    
    print(f"Found {len(unanalyzed)} unanalyzed records")
    print()
    
    if unanalyzed:
        print("Top 20 unanalyzed records (ordered by run_timestamp DESC):")
        for rec in unanalyzed[:20]:
            print(f"  entry_id={rec.entry_id:6d} | run_timestamp={rec.run_timestamp}")
        print()
    
    # 3. Get the most recent records overall (regardless of analysis status)
    print("3. Most recent records OVERALL (all statuses):")
    print("-" * 80)
    all_recent = db.query(
        SentimentData.entry_id,
        SentimentData.run_timestamp,
        SentimentData.created_at,
        SentimentData.sentiment_label
    ).order_by(desc(SentimentData.run_timestamp)).limit(50).all()
    
    print(f"Top 20 most recent records (all statuses):")
    for rec in all_recent[:20]:
        status = "✓" if rec.sentiment_label else "✗"
        print(f"  {status} entry_id={rec.entry_id:6d} | run_timestamp={rec.run_timestamp} | sentiment={rec.sentiment_label}")
    print()
    
    # 4. Cross-reference: Are analyzed IDs in the top recent records?
    print("4. Cross-reference check:")
    print("-" * 80)
    analyzed_ids_set = set(analyzed_entry_ids)
    top_50_ids = {rec.entry_id for rec in all_recent[:50]}
    
    overlap = analyzed_ids_set & top_50_ids
    print(f"Analyzed entry_ids that are in top 50 most recent: {len(overlap)}/{len(analyzed_entry_ids)}")
    
    if overlap:
        print(f"  ✓ Good: {len(overlap)} analyzed records are recent")
    else:
        print(f"  ✗ WARNING: None of the analyzed records are in top 50 most recent!")
    
    # Check if any analyzed records are older than unanalyzed ones
    if analyzed_records and unanalyzed:
        oldest_analyzed = min(rec.run_timestamp for rec in analyzed_records)
        newest_unanalyzed = max(rec.run_timestamp for rec in unanalyzed)
        
        print()
        print(f"Oldest analyzed record: {oldest_analyzed}")
        print(f"Newest unanalyzed record: {newest_unanalyzed}")
        
        if oldest_analyzed < newest_unanalyzed:
            print(f"  ✗ PROBLEM: Old analyzed records ({oldest_analyzed}) while newer unanalyzed exist ({newest_unanalyzed})")
        else:
            print(f"  ✓ OK: All analyzed records are newer than unanalyzed ones")
    
    print()
    print("=" * 80)
    
    db.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
