"""
Check existing data status in database to see what can be processed.

This script analyzes the database to determine:
- Total records per user
- Records with embeddings
- Records with sentiment labels
- Records with both (can skip OpenAI)
- Records missing fields (need processing)
- Records with topics
- Existing issues
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from src.api.database import SessionLocal
from src.api.models import (
    SentimentData, SentimentEmbedding, MentionTopic,
    TopicIssue, IssueMention, User
)
import json
from datetime import datetime


def check_user_data_status(user_id: str = None):
    """Check data status for a specific user or all users."""
    db: Session = SessionLocal()
    
    try:
        # Get user(s)
        if user_id:
            # Try to find user by ID (UUID string)
            try:
                users = db.query(User).filter(User.id == user_id).all()
            except Exception as e:
                # If UUID format fails, try as string
                users = db.query(User).filter(User.id.cast(str) == str(user_id)).all()
            
            if not users:
                print(f"ERROR: User {user_id} not found in database")
                return
        else:
            users = db.query(User).all()
            if not users:
                print("ERROR: No users found in database")
                return
        
        print("=" * 80)
        print("DATABASE STATUS CHECK")
        print("=" * 80)
        print()
        
        for user in users:
            user_id_str = str(user.id)
            print(f"USER: {user_id_str}")
            print("-" * 80)
            
            # Total records
            total_records = db.query(SentimentData).filter(
                SentimentData.user_id == user.id
            ).count()
            
            print(f"Total Records: {total_records}")
            
            if total_records == 0:
                print("WARNING: No records found for this user")
                print()
                continue
            
            # Records with embeddings
            records_with_embeddings = db.query(SentimentData).join(
                SentimentEmbedding,
                SentimentData.entry_id == SentimentEmbedding.entry_id
            ).filter(
                SentimentData.user_id == user.id,
                SentimentEmbedding.embedding.isnot(None)
            ).count()
            
            # Records with sentiment
            records_with_sentiment = db.query(SentimentData).filter(
                SentimentData.user_id == user.id,
                SentimentData.sentiment_label.isnot(None)
            ).count()
            
            # Records with both embedding and sentiment
            records_with_both = db.query(SentimentData).join(
                SentimentEmbedding,
                SentimentData.entry_id == SentimentEmbedding.entry_id
            ).filter(
                SentimentData.user_id == user.id,
                SentimentData.sentiment_label.isnot(None),
                SentimentEmbedding.embedding.isnot(None)
            ).count()
            
            # Records with emotion
            records_with_emotion = db.query(SentimentData).filter(
                SentimentData.user_id == user.id,
                SentimentData.emotion_label.isnot(None)
            ).count()
            
            # Records with topics
            records_with_topics = db.query(func.count(func.distinct(MentionTopic.mention_id))).join(
                SentimentData,
                MentionTopic.mention_id == SentimentData.entry_id
            ).filter(
                SentimentData.user_id == user.id
            ).scalar() or 0
            
            # Records with location
            records_with_location = db.query(SentimentData).filter(
                SentimentData.user_id == user.id,
                SentimentData.location_label.isnot(None)
            ).count()
            
            print(f"\nField Completion:")
            print(f"  [OK] With Embeddings: {records_with_embeddings} ({records_with_embeddings/total_records*100:.1f}%)")
            print(f"  [OK] With Sentiment: {records_with_sentiment} ({records_with_sentiment/total_records*100:.1f}%)")
            print(f"  [OK] With Both (Embedding + Sentiment): {records_with_both} ({records_with_both/total_records*100:.1f}%)")
            print(f"  [OK] With Emotion: {records_with_emotion} ({records_with_emotion/total_records*100:.1f}%)")
            print(f"  [OK] With Topics: {records_with_topics} ({records_with_topics/total_records*100:.1f}%)")
            print(f"  [OK] With Location: {records_with_location} ({records_with_location/total_records*100:.1f}%)")
            
            # Missing fields
            missing_embedding = total_records - records_with_embeddings
            missing_sentiment = total_records - records_with_sentiment
            missing_emotion = total_records - records_with_emotion
            missing_topics = total_records - records_with_topics
            missing_location = total_records - records_with_location
            
            print(f"\nMissing Fields:")
            print(f"  [X] Missing Embeddings: {missing_embedding} ({missing_embedding/total_records*100:.1f}%)")
            print(f"  [X] Missing Sentiment: {missing_sentiment} ({missing_sentiment/total_records*100:.1f}%)")
            print(f"  [X] Missing Emotion: {missing_emotion} ({missing_emotion/total_records*100:.1f}%)")
            print(f"  [X] Missing Topics: {missing_topics} ({missing_topics/total_records*100:.1f}%)")
            print(f"  [X] Missing Location: {missing_location} ({missing_location/total_records*100:.1f}%)")
            
            # Records that can skip OpenAI (have both embedding and sentiment)
            can_skip_openai = records_with_both
            need_openai = total_records - can_skip_openai
            
            print(f"\nOpenAI Cost Estimation:")
            print(f"  [OK] Can Skip OpenAI: {can_skip_openai} ({can_skip_openai/total_records*100:.1f}%)")
            print(f"  [$] Need OpenAI Calls: {need_openai} ({need_openai/total_records*100:.1f}%)")
            
            # Check existing issues
            # Get all mentions for this user
            mention_ids = db.query(SentimentData.entry_id).filter(
                SentimentData.user_id == user.id
            ).subquery()
            
            # Count issues linked to user's mentions
            issues_count = db.query(func.count(func.distinct(IssueMention.issue_id))).join(
                mention_ids,
                IssueMention.mention_id == mention_ids.c.entry_id
            ).scalar() or 0
            
            # Get total issues
            total_issues = db.query(TopicIssue).count()
            
            print(f"\nIssue Detection Status:")
            print(f"  Total Issues in DB: {total_issues}")
            print(f"  Issues Linked to User's Mentions: {issues_count}")
            
            # Check issue metrics completion
            if issues_count > 0:
                # Get issues linked to user's mentions
                user_issue_ids = db.query(func.distinct(IssueMention.issue_id)).join(
                    mention_ids,
                    IssueMention.mention_id == mention_ids.c.entry_id
                ).subquery()
                
                issues_with_volume = db.query(TopicIssue).filter(
                    TopicIssue.id.in_(db.query(user_issue_ids.c.issue_id)),
                    TopicIssue.volume_current_window.isnot(None)
                ).count()
                
                issues_with_velocity = db.query(TopicIssue).filter(
                    TopicIssue.id.in_(db.query(user_issue_ids.c.issue_id)),
                    TopicIssue.velocity_percent.isnot(None)
                ).count()
                
                issues_with_sentiment_agg = db.query(TopicIssue).filter(
                    TopicIssue.id.in_(db.query(user_issue_ids.c.issue_id)),
                    TopicIssue.sentiment_distribution.isnot(None)
                ).count()
                
                issues_with_metadata = db.query(TopicIssue).filter(
                    TopicIssue.id.in_(db.query(user_issue_ids.c.issue_id)),
                    TopicIssue.top_keywords.isnot(None)
                ).count()
                
                print(f"\nIssue Metrics Completion:")
                print(f"  [OK] With Volume/Velocity: {issues_with_volume}/{issues_count} ({issues_with_volume/issues_count*100:.1f}%)" if issues_count > 0 else "  [OK] With Volume/Velocity: 0/0")
                print(f"  [OK] With Velocity: {issues_with_velocity}/{issues_count} ({issues_with_velocity/issues_count*100:.1f}%)" if issues_count > 0 else "  [OK] With Velocity: 0/0")
                print(f"  [OK] With Sentiment Aggregation: {issues_with_sentiment_agg}/{issues_count} ({issues_with_sentiment_agg/issues_count*100:.1f}%)" if issues_count > 0 else "  [OK] With Sentiment Aggregation: 0/0")
                print(f"  [OK] With Metadata: {issues_with_metadata}/{issues_count} ({issues_with_metadata/issues_count*100:.1f}%)" if issues_count > 0 else "  [OK] With Metadata: 0/0")
            
            # Processing recommendations
            print(f"\nProcessing Recommendations:")
            if records_with_both > 0:
                print(f"  [OK] {records_with_both} records can use existing data (skip OpenAI)")
            if need_openai > 0:
                print(f"  [WARN] {need_openai} records need OpenAI calls (missing embedding or sentiment)")
            if missing_emotion > 0 or missing_topics > 0 or missing_location > 0:
                print(f"  [INFO] {max(missing_emotion, missing_topics, missing_location)} records need additional processing")
            if issues_count == 0 and records_with_topics > 0:
                print(f"  [INFO] {records_with_topics} records have topics but no issues - run Phase 6 to create issues")
            if issues_count > 0:
                if issues_with_volume < issues_count:
                    print(f"  [INFO] {issues_count - issues_with_volume} issues need volume/velocity calculation")
                if issues_with_sentiment_agg < issues_count:
                    print(f"  [INFO] {issues_count - issues_with_sentiment_agg} issues need sentiment aggregation")
                if issues_with_metadata < issues_count:
                    print(f"  [INFO] {issues_count - issues_with_metadata} issues need metadata extraction")
            
            print()
            print("=" * 80)
            print()
        
        print("\n[OK] Status check complete!")
        print("\nTo process existing data, run:")
        print(f"  curl -X POST \"http://localhost:8000/agent/test-cycle-no-auth?test_user_id=<USER_ID>&use_existing_data=true\"")
        
    except Exception as e:
        print(f"ERROR: Error checking database status: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check existing data status in database")
    parser.add_argument("--user-id", type=str, help="Specific user ID to check (optional)")
    
    args = parser.parse_args()
    
    check_user_data_status(user_id=args.user_id)
