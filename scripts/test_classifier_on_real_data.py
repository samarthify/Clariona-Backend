"""
Test TopicClassifier on real data from sentiment_data table.
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
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(message)s'
)

logger = logging.getLogger('RealDataTest')


def get_sample_records(db: Session, limit: int = 20):
    """Get sample records from sentiment_data table."""
    try:
        # Get records with text content
        records = db.query(SentimentData).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")  # At least 50 characters
        ).order_by(
            SentimentData.created_at.desc()
        ).limit(limit).all()
        
        return records
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        return []


def test_on_real_data():
    """Test classifier on real sentiment data."""
    
    print("\n" + "="*90)
    print("TOPIC CLASSIFIER - REAL DATA TEST")
    print("="*90)
    
    # Initialize classifier
    print("\n[1] Initializing TopicClassifier...")
    start = time.time()
    classifier = TopicClassifier(
        keyword_weight=0.3,
        embedding_weight=0.7,
        min_score_threshold=0.3,
        max_topics=5
    )
    init_time = time.time() - start
    print(f"    Initialized in {init_time:.3f}s")
    print(f"    Topics: {len(classifier.master_topics)}, Embeddings: {len(classifier.topic_embeddings)}")
    
    # Get database session
    print("\n[2] Connecting to database...")
    db = SessionLocal()
    try:
        print("    Connected successfully")
        
        # Get sample records
        print("\n[3] Fetching sample records from sentiment_data table...")
        records = get_sample_records(db, limit=20)
        print(f"    Found {len(records)} records with text content")
        
        if not records:
            print("\n[ERROR] No records found. Make sure the database has data.")
            return
        
        # Test classification
        print("\n[4] Running classifications...")
        print("-" * 90)
        
        results = []
        total_time = 0
        records_with_topics = 0
        
        for i, record in enumerate(records, 1):
            # Get text content (try multiple fields)
            text_content = (
                record.text or 
                record.content or 
                record.description or 
                record.title or 
                ""
            )
            
            if not text_content or len(text_content.strip()) < 20:
                continue
            
            # Truncate for display
            text_preview = text_content[:100].replace('\n', ' ') + "..."
            
            # Classify
            start_time = time.time()
            classifications = classifier.classify(text_content, text_embedding=None)
            elapsed = (time.time() - start_time) * 1000  # ms
            total_time += elapsed
            
            # Store result
            result = {
                "entry_id": record.entry_id,
                "text": text_content,
                "text_preview": text_preview,
                "classifications": classifications,
                "time": elapsed,
                "platform": record.platform,
                "source": record.source,
                "existing_ministry": record.ministry_hint,
                "existing_issue": record.issue_slug
            }
            results.append(result)
            
            if classifications:
                records_with_topics += 1
            
            # Print result
            print(f"\nRecord {i} (ID: {record.entry_id})")
            print(f"  Platform: {record.platform or 'N/A'}")
            print(f"  Source: {record.source or 'N/A'}")
            print(f"  Text: {text_preview}")
            print(f"  Time: {elapsed:.2f}ms")
            
            if classifications:
                print(f"  Topics Found ({len(classifications)}):")
                for cls in classifications:
                    print(f"    • {cls['topic_name']:30} | "
                          f"Conf: {cls['confidence']:.3f} | "
                          f"KW: {cls['keyword_score']:.3f}")
            else:
                print(f"  Topics: None (below threshold)")
            
            # Show existing classification if available
            if record.ministry_hint:
                print(f"  Existing Ministry: {record.ministry_hint}")
            if record.issue_slug:
                print(f"  Existing Issue: {record.issue_slug}")
        
        # Summary
        print("\n" + "="*90)
        print("SUMMARY")
        print("="*90)
        
        print(f"\n[Statistics]")
        print(f"  Records Processed: {len(results)}")
        print(f"  Records with Topics: {records_with_topics} ({records_with_topics/len(results)*100:.1f}%)")
        print(f"  Records without Topics: {len(results) - records_with_topics}")
        
        print(f"\n[Performance]")
        if results:
            avg_time = total_time / len(results)
            print(f"  Total Time: {total_time:.2f}ms")
            print(f"  Average per Record: {avg_time:.2f}ms")
            print(f"  Throughput: {len(results)/(total_time/1000):.1f} records/second")
        
        # Topic distribution
        topic_counts = {}
        for result in results:
            for cls in result["classifications"]:
                topic = cls["topic"]
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        if topic_counts:
            print(f"\n[Topic Distribution]")
            sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
            for topic, count in sorted_topics:
                topic_name = classifier.master_topics.get(topic, {}).get("name", topic)
                print(f"  {topic_name:30} : {count:3} mentions")
        
        # Show some examples
        print(f"\n[Example Classifications]")
        examples_shown = 0
        for result in results:
            if result["classifications"] and examples_shown < 5:
                print(f"\n  Example {examples_shown + 1}:")
                print(f"    Text: {result['text_preview']}")
                print(f"    Topics: {', '.join([cls['topic_name'] for cls in result['classifications']])}")
                examples_shown += 1
        
        print("\n" + "="*90)
        print("[SUCCESS] Real data test completed!")
        print("="*90)
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    test_on_real_data()
















