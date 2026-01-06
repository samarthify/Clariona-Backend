#!/usr/bin/env python3
"""
Script to check all date fields for a specific record
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData

env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found")
    sys.exit(1)

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    # Find the record
    record = db.query(SentimentData).filter(
        SentimentData.post_id == "2003087606096224436"
    ).first()
    
    if record:
        print(f"Entry ID: {record.entry_id}")
        print(f"Post ID: {record.post_id}")
        print(f"\nDate Fields:")
        print(f"  created_at: {record.created_at}")
        print(f"  run_timestamp: {record.run_timestamp}")
        print(f"  date: {record.date}")
        print(f"  published_at: {record.published_at}")
        print(f"  published_date: {record.published_date}")
        print(f"\nText preview: {record.text[:200] if record.text else 'N/A'}")
    else:
        print("Record not found")
    
    db.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()



















