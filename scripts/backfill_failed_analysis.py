#!/usr/bin/env python3
"""
Identify and backfill posts with failed analysis.

Two patterns in sentiment_justification indicate failed analysis:
  1. "Analysis failed" with "Recommended Action: Monitor for potential developments"
     (LLM response parsing failed or generic error fallback)
  2. "Rate limit error" (OpenAI rate limit hit during analysis)

Usage:
  # Identify only - report counts and sample records
  python scripts/backfill_failed_analysis.py --identify

  # Backfill (re-analyze) failed records
  python scripts/backfill_failed_analysis.py --backfill [--limit N] [--batch-size N] [--dry-run]

  # Include processing_status='failed' records as well
  python scripts/backfill_failed_analysis.py --backfill --include-processing-failed

  # Include completed-but-no-sentiment (bug: marked completed without real analysis)
  python scripts/backfill_failed_analysis.py --backfill --include-completed-no-sentiment

  # Only last 7 days (default) - use --lookback-days to change
  python scripts/backfill_failed_analysis.py --backfill --include-processing-failed --include-completed-no-sentiment --lookback-days 7
"""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Add project root to path so "from src.xxx" works
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

# Local imports (after path setup)
from src.api.database import SessionLocal
from src.api import models


# --- Pattern definitions ---

# Pattern 1: "Analysis failed" - generic failure (with or without "Recommended Action: Monitor for potential developments")
JUSTIFICATION_PATTERN_ANALYSIS_FAILED = "Analysis failed"

# Pattern 2: Rate limit error in justification
JUSTIFICATION_PATTERN_RATE_LIMIT = "rate limit"


def _matches_failed_pattern(justification: str | None) -> tuple[bool, str]:
    """Return (matches, pattern_name)."""
    if not justification:
        return False, ""
    j = justification.strip()
    if not j:
        return False, ""
    j_lower = j.lower()
    if JUSTIFICATION_PATTERN_ANALYSIS_FAILED in j:
        return True, "analysis_failed"
    if JUSTIFICATION_PATTERN_RATE_LIMIT in j_lower:
        return True, "rate_limit"
    return False, ""


def fetch_failed_records(
    db: Session,
    limit: Optional[int] = None,
    include_processing_failed: bool = False,
    include_completed_no_sentiment: bool = False,
    lookback_days: int = 7,
):
    """
    Fetch sentiment_data records with failed analysis.
    - Justification patterns: "Analysis failed", "rate limit"
    - Optionally: processing_status='failed'
    - Optionally: processing_status='completed' AND sentiment_label IS NULL (bug victims)
    - lookback_days: only records from last N days (date/run_timestamp/created_at)
    """
    from sqlalchemy import func

    justification_conditions = or_(
        models.SentimentData.sentiment_justification.ilike(f"%{JUSTIFICATION_PATTERN_ANALYSIS_FAILED}%"),
        func.lower(models.SentimentData.sentiment_justification).like(f"%{JUSTIFICATION_PATTERN_RATE_LIMIT}%"),
    )
    justification_filter = and_(
        models.SentimentData.sentiment_justification.isnot(None),
        justification_conditions,
    )

    conditions = [justification_filter]
    if include_processing_failed:
        conditions.append(models.SentimentData.processing_status == "failed")
    if include_completed_no_sentiment:
        conditions.append(
            and_(
                models.SentimentData.processing_status == "completed",
                models.SentimentData.sentiment_label.is_(None),
            )
        )
    base_filter = or_(*conditions)

    # Restrict to last N days (date or run_timestamp or created_at)
    cutoff = datetime.now() - timedelta(days=lookback_days)
    time_filter = or_(
        models.SentimentData.date >= cutoff,
        models.SentimentData.run_timestamp >= cutoff,
        models.SentimentData.created_at >= cutoff,
    )

    q = (
        db.query(models.SentimentData)
        .filter(base_filter, time_filter)
        .order_by(models.SentimentData.entry_id.desc())
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def identify_failed_records(
    db: Session,
    include_processing_failed: bool = False,
    include_completed_no_sentiment: bool = False,
    lookback_days: int = 7,
    sample: int = 10,
):
    """Identify and print counts + sample of failed records."""
    records = fetch_failed_records(
        db,
        limit=None,
        include_processing_failed=include_processing_failed,
        include_completed_no_sentiment=include_completed_no_sentiment,
        lookback_days=lookback_days,
    )

    by_pattern = {"analysis_failed": 0, "rate_limit": 0, "completed_no_sentiment": 0}
    for r in records:
        _, p = _matches_failed_pattern(r.sentiment_justification)
        if p:
            by_pattern[p] = by_pattern.get(p, 0) + 1
        if include_processing_failed and r.processing_status == "failed":
            by_pattern["processing_failed"] = by_pattern.get("processing_failed", 0) + 1
        if include_completed_no_sentiment and r.processing_status == "completed" and r.sentiment_label is None:
            by_pattern["completed_no_sentiment"] = by_pattern.get("completed_no_sentiment", 0) + 1

    print("\n" + "=" * 80)
    print("FAILED ANALYSIS IDENTIFICATION REPORT")
    print("=" * 80)
    print(f"\nLookback: last {lookback_days} days")
    print(f"Total records with failed analysis patterns: {len(records)}")
    for k, v in by_pattern.items():
        if v:
            print(f"  - {k}: {v}")

    if not records:
        print("\nNo records matching failed patterns found.")
        return

    sample_records = records[:sample]
    print(f"\nSample of up to {sample} records:")
    print("-" * 80)
    for r in sample_records:
        text_content = (r.text or r.content or r.title or "").strip()
        text_preview = (text_content[:120] + "...") if text_content and len(text_content) > 120 else (text_content or "(no text)")
        just_preview = (r.sentiment_justification or "")[:150]
        if len(r.sentiment_justification or "") > 150:
            just_preview += "..."
        matched, pattern = _matches_failed_pattern(r.sentiment_justification)
        print(f"  entry_id={r.entry_id}  pattern={pattern}  status={r.processing_status}")
        print(f"    text: {text_preview}")
        print(f"    justification: {just_preview}")
        print()
    print("=" * 80)


def backfill_records(
    db: Session,
    limit: Optional[int] = None,
    batch_size: int = 20,
    dry_run: bool = False,
    include_processing_failed: bool = False,
    include_completed_no_sentiment: bool = False,
    lookback_days: int = 7,
    delay_seconds: float = 1.0,
):
    """
    Re-analyze failed records using PresidentialSentimentAnalyzer and update DB.
    """
    from src.processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer

    records = fetch_failed_records(
        db,
        limit=limit,
        include_processing_failed=include_processing_failed,
        include_completed_no_sentiment=include_completed_no_sentiment,
        lookback_days=lookback_days,
    )
    if not records:
        print("No failed records to backfill.")
        return

    print(f"\nBackfilling {len(records)} failed records (last {lookback_days} days, dry_run={dry_run}, batch_size={batch_size})")
    if dry_run:
        print("DRY RUN - no changes will be written.")
        return

    analyzer = PresidentialSentimentAnalyzer()

    updated = 0
    errors = 0
    for i, record in enumerate(records):
        text_content = record.text or record.content or record.title or record.description
        if not text_content or str(text_content).strip() == "":
            print(f"  Skipping entry_id={record.entry_id}: no text content")
            continue

        try:
            result = analyzer.analyze(
                str(text_content).strip(),
                source_type=record.source_type,
                user_verified=getattr(record, "user_verified", False),
                reach=record.likes or 0,
            )

            # Update sentiment fields
            label = result.get("sentiment_label")
            justif = (result.get("sentiment_justification") or "").strip()
            # Only mark completed if we got valid sentiment (not analyzer failure fallback)
            if label and str(label).strip() and "Analysis failed" not in justif and "rate limit" not in justif.lower():
                record.sentiment_label = label
                record.sentiment_score = result.get("sentiment_score")
                record.sentiment_justification = result.get("sentiment_justification")
                record.emotion_label = result.get("emotion_label")
                record.emotion_score = result.get("emotion_score")
                record.emotion_distribution = result.get("emotion_distribution")
                record.influence_weight = result.get("influence_weight")
                record.confidence_weight = result.get("confidence_weight")
                record.processing_status = "completed"
                record.processing_completed_at = datetime.now()
            else:
                record.processing_status = "failed"
                record.processing_completed_at = datetime.now()
                print(f"  Skipping entry_id={record.entry_id}: analyzer returned invalid result (label={label!r})")
                errors += 1
                continue

            # Update or create embedding
            emb = result.get("embedding")
            if emb:
                existing = db.query(models.SentimentEmbedding).filter(
                    models.SentimentEmbedding.entry_id == record.entry_id
                ).first()
                if existing:
                    existing.embedding = emb
                else:
                    db.add(
                        models.SentimentEmbedding(
                            entry_id=record.entry_id,
                            embedding=emb,
                        )
                    )

            updated += 1
            if (i + 1) % batch_size == 0:
                db.commit()
                print(f"  Committed batch up to record {i + 1}/{len(records)}")
                time.sleep(delay_seconds)

        except Exception as e:
            errors += 1
            print(f"  Error on entry_id={record.entry_id}: {e}")
            continue

    if updated > 0 and (updated % batch_size) != 0:
        db.commit()
    print(f"\nBackfill complete: {updated} updated, {errors} errors")


def main():
    parser = argparse.ArgumentParser(
        description="Identify and backfill posts with failed analysis (analysis failed or rate limit)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--identify", action="store_true", help="Only identify failed records (no changes)")
    group.add_argument("--backfill", action="store_true", help="Re-analyze and update failed records")
    parser.add_argument("--limit", type=int, default=None, help="Max records to process (backfill only)")
    parser.add_argument("--batch-size", type=int, default=20, help="Commit every N records (backfill)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes (backfill)")
    parser.add_argument(
        "--include-processing-failed",
        action="store_true",
        help="Include records with processing_status='failed' in selection",
    )
    parser.add_argument(
        "--include-completed-no-sentiment",
        action="store_true",
        help="Include records marked completed but sentiment_label IS NULL (bug victims)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="Only process records from last N days (default: 7)",
    )
    parser.add_argument("--sample", type=int, default=10, help="Sample size for identify report")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.identify:
            identify_failed_records(
                db,
                include_processing_failed=args.include_processing_failed,
                include_completed_no_sentiment=args.include_completed_no_sentiment,
                lookback_days=args.lookback_days,
                sample=args.sample,
            )
        else:
            backfill_records(
                db,
                limit=args.limit,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                include_processing_failed=args.include_processing_failed,
                include_completed_no_sentiment=args.include_completed_no_sentiment,
                lookback_days=args.lookback_days,
            )


if __name__ == "__main__":
    main()
