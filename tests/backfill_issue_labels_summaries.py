#!/usr/bin/env python3
"""
Backfill script to generate labels and summaries for existing issues.

This script:
1. Finds all existing issues (optionally filter by topic)
2. Gets all mentions for each issue
3. Regenerates label and summary using LLM
4. Updates the issues in the database

Usage:
    python3 tests/backfill_issue_labels_summaries.py
    python3 tests/backfill_issue_labels_summaries.py --topic inflation
    python3 tests/backfill_issue_labels_summaries.py --dry-run
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to path (same as issue_detection_engine.py does)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from api.database import SessionLocal
from api.models import TopicIssue, IssueMention, SentimentData, SentimentEmbedding
from processing.issue_detection_engine import IssueDetectionEngine
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def get_all_issue_mentions(session: Session, issue: TopicIssue) -> list:
    """Get all mentions for an issue with their embeddings."""
    # Get all issue mentions
    issue_mentions = session.query(IssueMention).filter(
        IssueMention.issue_id == issue.id
    ).all()
    
    if not issue_mentions:
        return []
    
    mention_ids = [im.mention_id for im in issue_mentions]
    
    # Fetch sentiment data with embeddings
    mentions = session.query(SentimentData, SentimentEmbedding).outerjoin(
        SentimentEmbedding, SentimentData.entry_id == SentimentEmbedding.entry_id
    ).filter(
        SentimentData.entry_id.in_(mention_ids)
    ).all()
    
    result = []
    for sd, se in mentions:
        embedding = None
        if se and se.embedding:
            embedding = se.embedding
        elif se and se.embedding_vector:
            embedding = se.embedding_vector
        
        # Skip zero vectors
        if embedding and isinstance(embedding, list):
            if all(abs(x) < 1e-6 for x in embedding):
                continue
        
        result.append({
            'entry_id': sd.entry_id,
            'text': sd.text or '',
            'embedding': embedding,
            'sentiment_score': sd.sentiment_score,
            'sentiment_label': sd.sentiment_label,
            'emotion_label': sd.emotion_label,
            'source_type': sd.source_type,
            'source': sd.source,
            'platform': sd.platform,
            'created_at': sd.created_at
        })
    
    return result


def backfill_issues(topic_key: str = None, dry_run: bool = False):
    """Backfill labels and summaries for existing issues."""
    session = SessionLocal()
    engine = IssueDetectionEngine()
    
    try:
        # Get all issues
        query = session.query(TopicIssue).filter(TopicIssue.is_active == True)
        if topic_key:
            query = query.filter(TopicIssue.topic_key == topic_key)
        
        issues = query.all()
        logger.info(f"Found {len(issues)} active issues to process" + (f" for topic: {topic_key}" if topic_key else ""))
        
        if not issues:
            logger.info("No issues found to process")
            return
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, issue in enumerate(issues, 1):
            try:
                logger.info(f"[{i}/{len(issues)}] Processing issue: {issue.issue_slug} (id={issue.id})")
                
                # Get all mentions for this issue
                mentions = get_all_issue_mentions(session, issue)
                
                if not mentions:
                    logger.warning(f"  No mentions found for issue {issue.issue_slug}, skipping")
                    skipped_count += 1
                    continue
                
                if len(mentions) < 15:
                    logger.warning(f"  Only {len(mentions)} mentions (need at least 15), skipping")
                    skipped_count += 1
                    continue
                
                logger.info(f"  Found {len(mentions)} mentions, generating label and summary...")
                
                # Generate label and summary
                if not engine.openai_client:
                    logger.error("  OpenAI client not available, skipping")
                    skipped_count += 1
                    continue
                
                label_result = engine._generate_issue_label_and_summary(mentions)
                
                new_label = label_result.get('title')
                new_summary = label_result.get('statement')
                
                if not new_label and not new_summary:
                    logger.warning(f"  Failed to generate label/summary, skipping")
                    skipped_count += 1
                    continue
                
                # Show what we're updating
                old_label = issue.issue_label or "(none)"
                old_summary = issue.issue_summary or "(none)"
                
                logger.info(f"  Old label: {old_label[:80]}")
                logger.info(f"  New label: {new_label[:80] if new_label else '(none)'}")
                logger.info(f"  Old summary: {old_summary[:100] if old_summary else '(none)'}")
                logger.info(f"  New summary: {new_summary[:100] if new_summary else '(none)'}")
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would update issue {issue.issue_slug}")
                    updated_count += 1
                else:
                    # Update issue
                    if new_label:
                        issue.issue_label = new_label
                    if new_summary:
                        issue.issue_summary = new_summary
                    
                    session.commit()
                    logger.info(f"  ✓ Updated issue {issue.issue_slug}")
                    updated_count += 1
                
            except Exception as e:
                logger.error(f"  Error processing issue {issue.issue_slug}: {e}", exc_info=True)
                error_count += 1
                session.rollback()
                continue
        
        logger.info(f"\n=== Backfill Complete ===")
        logger.info(f"Total issues: {len(issues)}")
        logger.info(f"Updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Errors: {error_count}")
        
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill labels and summaries for existing issues")
    parser.add_argument("--topic", type=str, help="Filter by topic key (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    
    args = parser.parse_args()
    
    backfill_issues(topic_key=args.topic, dry_run=args.dry_run)
