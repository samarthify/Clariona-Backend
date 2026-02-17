"""
Verify that recent records have all analysis fields properly stored:
- sentiment_label, sentiment_score, sentiment_justification
- emotion_label, emotion_score, emotion_distribution
- topics (in mention_topics table)
- embeddings (in sentiment_embeddings table)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import func, and_
from api.database import SessionLocal
from api import models

def verify_recent_analysis():
    """Verify analysis fields for records from the last 24 hours."""
    cutoff_time = datetime.now() - timedelta(days=1)
    
    with SessionLocal() as db:
        # Get recent analyzed records
        recent_records = db.query(models.SentimentData).filter(
            and_(
                models.SentimentData.date >= cutoff_time,
                models.SentimentData.sentiment_label.isnot(None)
            )
        ).order_by(
            models.SentimentData.date.desc()
        ).limit(100).all()
        
        print(f"\n{'='*80}")
        print(f"Verifying {len(recent_records)} recent analyzed records (last 24 hours)")
        print(f"{'='*80}\n")
        
        if not recent_records:
            print("No recent analyzed records found.")
            return
        
        # Statistics
        stats = {
            'total': len(recent_records),
            'has_sentiment_label': 0,
            'has_sentiment_score': 0,
            'has_sentiment_justification': 0,
            'has_emotion_label': 0,
            'has_emotion_score': 0,
            'has_emotion_distribution': 0,
            'has_embedding': 0,
            'has_topics': 0,
            'has_processing_status': 0,
            'has_processing_completed_at': 0,
        }
        
        issues = []
        
        for record in recent_records:
            # Check sentiment fields
            if record.sentiment_label:
                stats['has_sentiment_label'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing sentiment_label")
            
            if record.sentiment_score is not None:
                stats['has_sentiment_score'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing sentiment_score")
            
            if record.sentiment_justification:
                stats['has_sentiment_justification'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing sentiment_justification")
            
            # Check emotion fields
            if record.emotion_label:
                stats['has_emotion_label'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing emotion_label")
            
            if record.emotion_score is not None:
                stats['has_emotion_score'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing emotion_score")
            
            if record.emotion_distribution:
                stats['has_emotion_distribution'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing emotion_distribution")
            
            # Check embedding
            if record.embedding and record.embedding.embedding:
                stats['has_embedding'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing embedding")
            
            # Check topics (0 topics is valid, so we just count how many have topics)
            topic_count = db.query(models.MentionTopic).filter(
                models.MentionTopic.mention_id == record.entry_id
            ).count()
            
            if topic_count > 0:
                stats['has_topics'] += 1
            # Note: 0 topics is a valid result, not an issue
            
            # Check processing status
            if record.processing_status:
                stats['has_processing_status'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing processing_status")
            
            if record.processing_completed_at:
                stats['has_processing_completed_at'] += 1
            else:
                issues.append(f"Entry {record.entry_id}: Missing processing_completed_at")
        
        # Print statistics
        print("Field Storage Statistics:")
        print("-" * 80)
        print(f"Total records checked: {stats['total']}")
        print(f"\nSentiment Fields:")
        print(f"  sentiment_label:        {stats['has_sentiment_label']}/{stats['total']} ({stats['has_sentiment_label']*100//stats['total']}%)")
        print(f"  sentiment_score:         {stats['has_sentiment_score']}/{stats['total']} ({stats['has_sentiment_score']*100//stats['total']}%)")
        print(f"  sentiment_justification: {stats['has_sentiment_justification']}/{stats['total']} ({stats['has_sentiment_justification']*100//stats['total']}%)")
        print(f"\nEmotion Fields:")
        print(f"  emotion_label:          {stats['has_emotion_label']}/{stats['total']} ({stats['has_emotion_label']*100//stats['total']}%)")
        print(f"  emotion_score:          {stats['has_emotion_score']}/{stats['total']} ({stats['has_emotion_score']*100//stats['total']}%)")
        print(f"  emotion_distribution:   {stats['has_emotion_distribution']}/{stats['total']} ({stats['has_emotion_distribution']*100//stats['total']}%)")
        print(f"\nOther Fields:")
        print(f"  embedding:              {stats['has_embedding']}/{stats['total']} ({stats['has_embedding']*100//stats['total']}%)")
        print(f"  topics:                 {stats['has_topics']}/{stats['total']} ({stats['has_topics']*100//stats['total']}%)")
        print(f"  processing_status:      {stats['has_processing_status']}/{stats['total']} ({stats['has_processing_status']*100//stats['total']}%)")
        print(f"  processing_completed_at: {stats['has_processing_completed_at']}/{stats['total']} ({stats['has_processing_completed_at']*100//stats['total']}%)")
        
        # Show sample records
        print(f"\n{'='*80}")
        print("Sample Records (first 5):")
        print(f"{'='*80}\n")
        
        for i, record in enumerate(recent_records[:5], 1):
            topic_count = db.query(models.MentionTopic).filter(
                models.MentionTopic.mention_id == record.entry_id
            ).count()
            
            topics = db.query(models.MentionTopic).filter(
                models.MentionTopic.mention_id == record.entry_id
            ).all()
            
            print(f"Record {i} - Entry ID: {record.entry_id}")
            print(f"  Date: {record.date}")
            print(f"  Sentiment: {record.sentiment_label} (score: {record.sentiment_score})")
            print(f"  Emotion: {record.emotion_label} (score: {record.emotion_score})")
            print(f"  Embedding: {'Yes' if record.embedding and record.embedding.embedding else 'No'}")
            print(f"  Topics ({topic_count}): {[t.topic_key for t in topics]}")
            print(f"  Processing: {record.processing_status} (completed: {record.processing_completed_at})")
            print()
        
        # Show issues if any
        if issues:
            print(f"\n{'='*80}")
            print(f"Issues Found ({len(issues)}):")
            print(f"{'='*80}\n")
            for issue in issues[:20]:  # Show first 20 issues
                print(f"  - {issue}")
            if len(issues) > 20:
                print(f"\n  ... and {len(issues) - 20} more issues")
        else:
            print(f"\n{'='*80}")
            print("✓ All fields are properly stored!")
            print(f"{'='*80}\n")

if __name__ == "__main__":
    verify_recent_analysis()
