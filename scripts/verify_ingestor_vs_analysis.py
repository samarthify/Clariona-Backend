#!/usr/bin/env python3
"""
Compare records inserted in the last N minutes (ingestor) vs records analyzed
in the last N minutes (analysis worker). Use this to confirm that new ingestor
inserts are being picked up and analyzed.

Usage (run from repo root; use project venv if needed):
  ./venv/bin/python scripts/verify_ingestor_vs_analysis.py
  ./venv/bin/python scripts/verify_ingestor_vs_analysis.py --minutes 15
  ./venv/bin/python scripts/verify_ingestor_vs_analysis.py --minutes 10 --log logs/analysis_worker.log
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta

import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
for env_path in [
    Path(__file__).parent.parent / "config" / ".env",
    Path(__file__).parent.parent / ".env",
]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

DATABASE_URL = os.getenv("DATABASE_URL")


def parse_log_timestamp(line: str) -> datetime | None:
    """Parse timestamp from analysis_worker.log line, e.g. 2026-02-02 12:18:10,162."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+", line.strip())
    if not m:
        return None
    try:
        # Assume server local time if no TZ in log
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def extract_analyzed_ids_from_log(log_path: Path, since: datetime) -> set[int]:
    """Extract entry_ids from '✓ Analyzed [id]' lines in log that are >= since (naive local)."""
    ids = set()
    if not log_path.exists():
        return ids
    since_naive = since.replace(tzinfo=None) if since.tzinfo else since
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = parse_log_timestamp(line)
            if ts is None:
                continue
            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
            if ts_naive < since_naive:
                continue
            m = re.search(r"✓ Analyzed \[(\d+)\]", line)
            if m:
                ids.add(int(m.group(1)))
    return ids


def extract_claimed_ids_from_log(log_path: Path, since: datetime) -> set[int]:
    """Extract entry_ids from 'Claimed ... entry_ids=[...]' lines in log that are >= since (naive local)."""
    ids = set()
    if not log_path.exists():
        return ids
    since_naive = since.replace(tzinfo=None) if since.tzinfo else since
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = parse_log_timestamp(line)
            if ts is None:
                continue
            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
            if ts_naive < since_naive:
                continue
            m = re.search(r"entry_ids=\[([^\]]+)\]", line)
            if m:
                for part in re.split(r",\s*", m.group(1)):
                    part = part.strip()
                    if "..." in part:
                        continue
                    try:
                        ids.add(int(part))
                    except ValueError:
                        pass
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ingestor inserts vs analysis worker in the last N minutes."
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=10,
        help="Time window in minutes (default: 10)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path(__file__).parent.parent / "logs" / "analysis_worker.log",
        help="Path to analysis_worker.log (default: logs/analysis_worker.log)",
    )
    args = parser.parse_args()

    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker
    from src.api.models import SentimentData

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Cutoff: last N minutes. DB created_at is timezone=False (server local).
    now = datetime.now()
    cutoff_naive = now - timedelta(minutes=args.minutes)

    print("=" * 72)
    print("Ingestor vs Analysis — last {} minutes".format(args.minutes))
    print("Cutoff (approx): {}".format(cutoff_naive))
    print("=" * 72)

    # 1) Inserted in last N minutes (by created_at)
    inserted_rows = (
        db.query(
            SentimentData.entry_id,
            SentimentData.created_at,
            SentimentData.processing_status,
            SentimentData.sentiment_label,
            SentimentData.processing_completed_at,
        )
        .filter(SentimentData.created_at >= cutoff_naive)
        .order_by(desc(SentimentData.entry_id))
        .all()
    )
    inserted_ids = {r.entry_id for r in inserted_rows}
    inserted_analyzed = {r.entry_id for r in inserted_rows if r.sentiment_label is not None}
    inserted_pending = {r.entry_id for r in inserted_rows if r.processing_status == "pending"}
    inserted_processing = {r.entry_id for r in inserted_rows if r.processing_status == "processing"}

    # 2) Analyzed (processing_completed_at) in last N minutes (any record)
    analyzed_in_window_rows = (
        db.query(
            SentimentData.entry_id,
            SentimentData.created_at,
            SentimentData.processing_completed_at,
        )
        .filter(
            SentimentData.processing_completed_at.isnot(None),
            SentimentData.processing_completed_at >= cutoff_naive,
        )
        .order_by(desc(SentimentData.processing_completed_at))
        .limit(500)
        .all()
    )
    analyzed_in_window_ids = {r.entry_id for r in analyzed_in_window_rows}

    # 3) Overlap: inserted in window AND already have sentiment (analyzed)
    overlap = inserted_ids & inserted_analyzed
    not_yet_analyzed = inserted_ids - inserted_analyzed

    print()
    print("1. Inserted in last {} min (by created_at): {}".format(args.minutes, len(inserted_ids)))
    if inserted_ids:
        print("   Status: completed={}, pending={}, processing={}".format(
            len(inserted_analyzed),
            len(inserted_pending),
            len(inserted_processing),
        ))
        print("   entry_id range: {} .. {}".format(min(inserted_ids), max(inserted_ids)))
    print()

    print("2. Analyzed in last {} min (by processing_completed_at): {}".format(
        args.minutes, len(analyzed_in_window_ids)
    ))
    if analyzed_in_window_rows:
        print("   (sample: latest {} entry_ids)".format(min(10, len(analyzed_in_window_rows))))
        for r in analyzed_in_window_rows[:10]:
            print("     entry_id={} completed_at={}".format(r.entry_id, r.processing_completed_at))
    print()

    print("3. Of the inserted-in-window records:")
    print("   Already analyzed: {} / {} ({:.0%})".format(
        len(overlap), len(inserted_ids), len(overlap) / len(inserted_ids) if inserted_ids else 0
    ))
    if not_yet_analyzed:
        print("   Not yet analyzed: {}".format(len(not_yet_analyzed)))
        # Show up to 20 so it's readable
        sample = sorted(not_yet_analyzed, reverse=True)[:20]
        print("   entry_ids (newest first, max 20): {}".format(sample))
        if len(not_yet_analyzed) > 20:
            print("   ... and {} more".format(len(not_yet_analyzed) - 20))
    else:
        print("   Not yet analyzed: 0")
    print()

    # 4) Optional: from log file
    if args.log.exists():
        analyzed_from_log = extract_analyzed_ids_from_log(args.log, cutoff_naive)
        claimed_from_log = extract_claimed_ids_from_log(args.log, cutoff_naive)
        print("4. From log {} (lines in last {} min):".format(args.log, args.minutes))
        print("   Claimed (entry_ids in 'Claimed ... entry_ids='): {}".format(len(claimed_from_log)))
        print("   Analyzed (entry_ids in '✓ Analyzed [id]'):       {}".format(len(analyzed_from_log)))
        # How many of our inserted-in-window ids appear in log as analyzed?
        inserted_and_in_log = inserted_ids & analyzed_from_log
        print("   Inserted-in-window that appear as 'Analyzed' in log: {} / {}".format(
            len(inserted_and_in_log), len(inserted_ids)
        ))
        if inserted_ids and not inserted_and_in_log and analyzed_from_log:
            print("   (So far, analyzed ids in log are mostly older; new ordering should fix this.)")
    else:
        print("4. Log not found: {} (skip log comparison)".format(args.log))

    print()
    print("=" * 72)
    db.close()


if __name__ == "__main__":
    main()
