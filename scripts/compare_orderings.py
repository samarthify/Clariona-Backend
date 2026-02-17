#!/usr/bin/env python3
"""
Compare ordering of SentimentData by run_timestamp, created_at, and content dates.
Content date = COALESCE(published_at, published_date, date, run_timestamp)
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker
from src.api.models import SentimentData


def load_env():
    project_root = Path(__file__).parent.parent
    for p in [project_root / 'config' / '.env', project_root / '.env']:
        if p.exists():
            load_dotenv(dotenv_path=p)
            break


def show_list(title: str, rows: List[Tuple], limit: int = 20):
    print(title)
    print("-" * 80)
    for r in rows[:limit]:
        entry_id, run_ts, created_at, date_val, pub_at, pub_date = r
        print(f"  id={entry_id:>7} | run_ts={run_ts} | created_at={created_at} | date={date_val} | published_at={pub_at} | published_date={pub_date}")
    print()


def main():
    load_env()
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in env")
        sys.exit(1)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        cols = (
            SentimentData.entry_id,
            SentimentData.run_timestamp,
            SentimentData.created_at,
            SentimentData.date,
            SentimentData.published_at,
            SentimentData.published_date,
        )

        # A) Latest by run_timestamp DESC, entry_id DESC (AnalysisWorker behavior)
        latest_by_run_ts = db.query(*cols).order_by(desc(SentimentData.run_timestamp), desc(SentimentData.entry_id)).limit(100).all()

        # B) Latest by created_at DESC
        latest_by_created_at = db.query(*cols).order_by(desc(SentimentData.created_at), desc(SentimentData.entry_id)).limit(100).all()

        # C) Latest by content date DESC (coalesce published_at, published_date, date, run_timestamp)
        content_date = func.coalesce(SentimentData.published_at, SentimentData.published_date, SentimentData.date, SentimentData.run_timestamp)
        latest_by_content_date = db.query(*cols).order_by(desc(content_date), desc(SentimentData.entry_id)).limit(100).all()

        print("=" * 80)
        print("Ordering Comparison (Top 20 shown)")
        print("=" * 80)
        print()

        show_list("A) By run_timestamp DESC, entry_id DESC", latest_by_run_ts)
        show_list("B) By created_at DESC, entry_id DESC", latest_by_created_at)
        show_list("C) By content_date DESC, entry_id DESC", latest_by_content_date)

        # Overlap metrics
        def to_id_set(rows): return {r[0] for r in rows[:50]}
        a_set = to_id_set(latest_by_run_ts)
        b_set = to_id_set(latest_by_created_at)
        c_set = to_id_set(latest_by_content_date)

        print("Overlap (Top 50 IDs):")
        print("-" * 80)
        print(f"A∩B: {len(a_set & b_set)} / 50")
        print(f"A∩C: {len(a_set & c_set)} / 50")
        print(f"B∩C: {len(b_set & c_set)} / 50")
        print()

        # First divergence positions
        def first_divergence(a: List[Tuple], b: List[Tuple]) -> int:
            a_ids = [r[0] for r in a]
            b_ids = [r[0] for r in b]
            for i, (aid, bid) in enumerate(zip(a_ids, b_ids)):
                if aid != bid:
                    return i
            return -1

        ab_div = first_divergence(latest_by_run_ts, latest_by_created_at)
        ac_div = first_divergence(latest_by_run_ts, latest_by_content_date)
        bc_div = first_divergence(latest_by_created_at, latest_by_content_date)

        print("First divergence index (0-based, -1 means identical in top 100):")
        print("-" * 80)
        print(f"A vs B: {ab_div}")
        print(f"A vs C: {ac_div}")
        print(f"B vs C: {bc_div}")
        print()

        print("=" * 80)
        print("Note:")
        print("- AnalysisWorker currently uses ordering A (run_timestamp DESC, entry_id DESC).")
        print("- If you prefer created_at or content_date ordering, we can switch easily.")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()

