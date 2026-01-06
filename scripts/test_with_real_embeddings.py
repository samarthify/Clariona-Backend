"""
Test TopicClassifier with real embeddings from the database.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import logging
import json
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding
from processing.topic_classifier import TopicClassifier

# Set up logging
logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('RealEmbeddingTest')


def parse_embedding(embedding_data):
    """Parse embedding from various formats."""
    if embedding_data is None:
        return None
    
    # If it's already a list
    if isinstance(embedding_data, list):
        if len(embedding_data) == 1536:
            try:
                return [float(x) for x in embedding_data]
            except:
                return None
        return None
    
    # If it's a string, try to parse
    if isinstance(embedding_data, str):
        try:
            parsed = json.loads(embedding_data)
            if isinstance(parsed, list) and len(parsed) == 1536:
                return [float(x) for x in parsed]
        except:
            pass
    
    return None


def test_with_real_embeddings():
    """Test classifier with real embeddings from database."""
    
    print("\n" + "="*90)
    print("TOPIC CLASSIFIER - TEST WITH REAL EMBEDDINGS")
    print("="*90)
    
    db = SessionLocal()
    try:
        # Get records with embeddings
        print("\n[1] Fetching records with embeddings...")
        records_with_emb = db.query(SentimentData).join(
            SentimentEmbedding,
            SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.text.isnot(None),
            SentimentData.text != '',
            text("LENGTH(text) > 50")
        ).limit(20).all()
        
        print(f"    Found {len(records_with_emb)} records with embeddings")
        
        if not records_with_emb:
            print("    No records with embeddings found")
            return
        
        # Initialize classifier
        print("\n[2] Initializing TopicClassifier...")
        classifier = TopicClassifier(
            keyword_weight=0.3,
            embedding_weight=0.7,
            min_score_threshold=0.25,  # Lower threshold
            max_topics=5
        )
        print(f"    Classifier ready: {len(classifier.master_topics)} topics, {len(classifier.topic_embeddings)} embeddings")
        
        # Test classification
        print("\n[3] Testing classification with embeddings...")
        print("-" * 90)
        
        results = []
        total_time = 0
        matches = 0
        
        for i, record in enumerate(records_with_emb, 1):
            text_content = (
                record.text or 
                record.content or 
                record.description or 
                record.title or 
                ""
            )
            
            if not text_content or len(text_content.strip()) < 20:
                continue
            
            # Get embedding
            embedding_record = db.query(SentimentEmbedding).filter(
                SentimentEmbedding.entry_id == record.entry_id
            ).first()
            
            if not embedding_record:
                continue
            
            # Parse embedding
            embedding_list = parse_embedding(embedding_record.embedding)
            
            if not embedding_list:
                print(f"  Record {i}: Could not parse embedding")
                continue
            
            # Classify
            start_time = time.time()
            classifications = classifier.classify(text_content, text_embedding=embedding_list)
            elapsed = (time.time() - start_time) * 1000
            total_time += elapsed
            
            if classifications:
                matches += 1
            
            # Store result
            results.append({
                "entry_id": record.entry_id,
                "text": text_content[:100],
                "classifications": classifications,
                "time": elapsed,
                "has_embedding": True
            })
            
            # Print result (handle Unicode)
            try:
                text_preview = text_content[:80].encode('ascii', 'ignore').decode('ascii')
            except:
                text_preview = text_content[:80]
            
            print(f"\n  Record {i} (ID: {record.entry_id}):")
            print(f"    Text: {text_preview}...")
            print(f"    Time: {elapsed:.2f}ms")
            
            if classifications:
                print(f"    Topics Found ({len(classifications)}):")
                for cls in classifications:
                    print(f"      • {cls['topic_name']:30} | "
                          f"Conf: {cls['confidence']:.3f} | "
                          f"KW: {cls['keyword_score']:.3f} | "
                          f"Emb: {cls['embedding_score']:.3f}")
            else:
                print(f"    Topics: None")
        
        # Summary
        print("\n" + "="*90)
        print("SUMMARY")
        print("="*90)
        
        print(f"\n[Results]")
        print(f"  Records Tested: {len(results)}")
        print(f"  Records with Topics: {matches} ({matches/len(results)*100:.1f}%)")
        print(f"  Average Time: {total_time/len(results):.2f}ms")
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
        
        print("\n" + "="*90)
        print("[TEST COMPLETE]")
        print("="*90)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n[ERROR] {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    test_with_real_embeddings()

