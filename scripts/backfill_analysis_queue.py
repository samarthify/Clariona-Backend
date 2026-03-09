#!/usr/bin/env python3
"""
Backfill analysis_queue with sentiment_data rows that need analysis.

Selects sentiment_data.entry_id where processing_status='pending' (and optionally
sentiment_label IS NULL), inserts into analysis_queue (ignore conflicts).
Run in batches to avoid long locks. Use for one-time migration of pre-queue records.
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.api.database import SessionLocal
from src.api.models import AnalysisQueue, SentimentData


def backfill(batch_size: int = 500, limit: int = None, dry_run: bool = False) -> int:
    """
    Backfill analysis_queue with pending sentiment_data entry_ids.
    
    Args:
        batch_size: Records per batch.
        limit: Max total records to backfill (None = no limit).
        dry_run: If True, only count and report, do not insert.
    
    Returns:
        Number of rows inserted into analysis_queue.
    """
    total_inserted = 0
    offset = 0
    while True:
        with SessionLocal() as db:
            subq = (
                db.query(SentimentData.entry_id)
                .filter(
                    SentimentData.processing_status == 'pending',
                    SentimentData.sentiment_label.is_(None),
                )
                .offset(offset)
                .limit(batch_size)
            )
            if limit:
                remaining = limit - total_inserted
                if remaining <= 0:
                    break
                subq = subq.limit(min(batch_size, remaining))
            rows = subq.all()
            entry_ids = [r[0] for r in rows]
            if not entry_ids:
                break
            if dry_run:
                print(f"Would enqueue {len(entry_ids)} entry_ids: {entry_ids[:10]}...")
                total_inserted += len(entry_ids)
            else:
                for eid in entry_ids:
                    stmt = pg_insert(AnalysisQueue).values(entry_id=eid, status='pending')
                    stmt = stmt.on_conflict_do_nothing(index_elements=['entry_id'])
                    db.execute(stmt)
                db.commit()
                total_inserted += len(entry_ids)
                print(f"Enqueued {len(entry_ids)} (total: {total_inserted})")
            offset += len(entry_ids)
            if limit and total_inserted >= limit:
                break
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description='Backfill analysis_queue with pending sentiment_data')
    parser.add_argument('--batch-size', type=int, default=500, help='Records per batch')
    parser.add_argument('--limit', type=int, default=None, help='Max total records to backfill')
    parser.add_argument('--dry-run', action='store_true', help='Count only, do not insert')
    args = parser.parse_args()
    
    n = backfill(batch_size=args.batch_size, limit=args.limit, dry_run=args.dry_run)
    print(f"Done. {'Would enqueue' if args.dry_run else 'Enqueued'} {n} records.")


if __name__ == '__main__':
    main()
