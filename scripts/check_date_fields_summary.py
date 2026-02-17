#!/usr/bin/env python3
"""
Summarize null/non-null counts for date-related fields in sentiment_data and
print a few recent examples.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData


def load_env():
    project_root = Path(__file__).parent.parent
    for p in [project_root / 'config' / '.env', project_root / '.env']:
        if p.exists():
            load_dotenv(dotenv_path=p)
            break


def main():
    load_env()
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        total = db.query(func.count(SentimentData.entry_id)).scalar() or 0
        date_null = db.query(func.count(SentimentData.entry_id)).filter(SentimentData.date.is_(None)).scalar() or 0
        date_not_null = total - date_null

        pub_at_null = db.query(func.count(SentimentData.entry_id)).filter(SentimentData.published_at.is_(None)).scalar() or 0
        pub_date_null = db.query(func.count(SentimentData.entry_id)).filter(SentimentData.published_date.is_(None)).scalar() or 0
        created_at_null = db.query(func.count(SentimentData.entry_id)).filter(SentimentData.created_at.is_(None)).scalar() or 0
        run_ts_null = db.query(func.count(SentimentData.entry_id)).filter(SentimentData.run_timestamp.is_(None)).scalar() or 0

        print("=== Date Fields Summary ===")
        print(f"Total rows: {total}")
        print(f"date: null={date_null} not_null={date_not_null}")
        print(f"published_at: null={pub_at_null} not_null={total - pub_at_null}")
        print(f"published_date: null={pub_date_null} not_null={total - pub_date_null}")
        print(f"created_at: null={created_at_null} not_null={total - created_at_null}")
        print(f"run_timestamp: null={run_ts_null} not_null={total - run_ts_null}")
        print()

        # Show a few of the most recent records with their date fields
        print("Most recent 15 records (run_timestamp DESC):")
        rows = db.query(
            SentimentData.entry_id,
            SentimentData.platform,
            SentimentData.run_timestamp,
            SentimentData.created_at,
            SentimentData.date,
            SentimentData.published_at,
            SentimentData.published_date
        ).order_by(desc(SentimentData.run_timestamp), desc(SentimentData.entry_id)).limit(15).all()
        for r in rows:
            print(f"id={r.entry_id:>7} | plat={str(r.platform)[:10]:<10} | run_ts={r.run_timestamp} | created_at={r.created_at} | date={r.date} | published_at={r.published_at} | published_date={r.published_date}")

        print()

        # Oldest 5 without any content date (date, published_at, published_date all null)
        print("Oldest 5 with all content dates null:")
        rows2 = db.query(
            SentimentData.entry_id,
            SentimentData.platform,
            SentimentData.run_timestamp,
            SentimentData.date,
            SentimentData.published_at,
            SentimentData.published_date
        ).filter(
            SentimentData.date.is_(None),
            SentimentData.published_at.is_(None),
            SentimentData.published_date.is_(None)
        ).order_by(SentimentData.run_timestamp).limit(5).all()
        for r in rows2:
            print(f"id={r.entry_id:>7} | plat={str(r.platform)[:10]:<10} | run_ts={r.run_timestamp} | date={r.date} | published_at={r.published_at} | published_date={r.published_date}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

