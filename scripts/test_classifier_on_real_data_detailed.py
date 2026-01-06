"""
Detailed test of TopicClassifier on real data with lower thresholds and analysis.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import logging
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import SessionLocal
from api.models import SentimentData
from processing.topic_classifier import TopicClassifier

# Set up logging
logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('RealDataTest')


def get_sample_records(db: Session, limit: int = 30):
    """Get sample records from sentiment_data table."""
    try:
        records = db.query(SentimentData).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).order_by(
            SentimentData.created_at.desc()
        ).limit(limit).all()
        
        return records
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        return []


def test_with_different_thresholds():
    """Test with different threshold values."""
    
    print("\n" + "="*90)
    print("TOPIC CLASSIFIER - REAL DATA TEST (DETAILED)")
    print("="*90)
    
    # Get database records
    db = SessionLocal()
    try:
        records = get_sample_records(db, limit=30)
        print(f"\n[Database] Found {len(records)} records")
        
        if not records:
            print("[ERROR] No records found")
            return
        
        # Test with different thresholds
        thresholds = [0.2, 0.25, 0.3, 0.35]
        
        for threshold in thresholds:
            print(f"\n{'='*90}")
            print(f"TESTING WITH THRESHOLD: {threshold}")
            print(f"{'='*90}")
            
            classifier = TopicClassifier(
                keyword_weight=0.3,
                embedding_weight=0.7,
                min_score_threshold=threshold,
                max_topics=5
            )
            
            matches = 0
            total_time = 0
            topic_counts = {}
            
            for i, record in enumerate(records[:15], 1):  # Test first 15
                text_content = (
                    record.text or 
                    record.content or 
                    record.description or 
                    record.title or 
                    ""
                )
                
                if not text_content or len(text_content.strip()) < 20:
                    continue
                
                start_time = time.time()
                classifications = classifier.classify(text_content, text_embedding=None)
                elapsed = (time.time() - start_time) * 1000
                total_time += elapsed
                
                if classifications:
                    matches += 1
                    for cls in classifications:
                        topic = cls["topic"]
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    
                    # Show first few matches
                    if matches <= 3:
                        text_preview = text_content[:80].replace('\n', ' ') + "..."
                        print(f"\n  Match {matches}:")
                        print(f"    Text: {text_preview}")
                        topics_str = ', '.join([f"{c['topic_name']} ({c['confidence']:.3f})" for c in classifications])
                        print(f"    Topics: {topics_str}")
            
            print(f"\n  Results:")
            print(f"    Records with topics: {matches}/{15} ({matches/15*100:.1f}%)")
            print(f"    Average time: {total_time/15:.2f}ms")
            if topic_counts:
                top_topics = ', '.join([f"{k}({v})" for k, v in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:3]])
                print(f"    Top topics: {top_topics}")
        
        # Detailed analysis of a few records
        print(f"\n{'='*90}")
        print("DETAILED ANALYSIS - Sample Records")
        print(f"{'='*90}")
        
        classifier = TopicClassifier(
            keyword_weight=0.3,
            embedding_weight=0.7,
            min_score_threshold=0.2,  # Lower threshold for analysis
            max_topics=10  # More topics for analysis
        )
        
        analyzed = 0
        for record in records:
            if analyzed >= 5:
                break
            
            text_content = (
                record.text or 
                record.content or 
                record.description or 
                record.title or 
                ""
            )
            
            if not text_content or len(text_content.strip()) < 30:
                continue
            
            classifications = classifier.classify(text_content, text_embedding=None)
            
            if classifications or record.ministry_hint:  # Show even if no match, if it has ministry
                analyzed += 1
                text_preview = text_content[:100].replace('\n', ' ')
                
                print(f"\n  Record {analyzed} (ID: {record.entry_id}):")
                print(f"    Text: {text_preview}...")
                print(f"    Platform: {record.platform}")
                print(f"    Existing Ministry: {record.ministry_hint or 'None'}")
                print(f"    Existing Issue: {record.issue_slug or 'None'}")
                
                if classifications:
                    print(f"    Topics Found ({len(classifications)}):")
                    for cls in classifications:
                        print(f"      • {cls['topic_name']:30} | "
                              f"Conf: {cls['confidence']:.3f} | "
                              f"KW: {cls['keyword_score']:.3f}")
                else:
                    print(f"    Topics: None (below threshold 0.2)")
                    
                    # Show top scoring topics even if below threshold
                    text_lower = text_content.lower()
                    top_scores = []
                    for topic_key, topic_data in classifier.master_topics.items():
                        keywords = topic_data.get('keywords', [])
                        if keywords:
                            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
                            if matches > 0:
                                score = min(matches / len(keywords), 1.0)
                                if matches > 1:
                                    import numpy as np
                                    score = min(score * (1 + np.log(matches + 1) / 10), 1.0)
                                top_scores.append((topic_key, topic_data.get('name'), score, matches))
                    
                    if top_scores:
                        top_scores.sort(key=lambda x: x[2], reverse=True)
                        print(f"    Top scoring topics (below threshold):")
                        for topic_key, name, score, match_count in top_scores[:3]:
                            print(f"      • {name:30} | Score: {score:.3f} | Matches: {match_count}")
        
        print(f"\n{'='*90}")
        print("[ANALYSIS COMPLETE]")
        print(f"{'='*90}")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    test_with_different_thresholds()

