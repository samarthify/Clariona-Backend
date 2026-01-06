"""
Test TopicClassifier on 100 records from database and save results to CSV.
"""

import sys
from pathlib import Path
import csv
import json
from datetime import datetime

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding
from processing.topic_classifier import TopicClassifier

# Initialize classifier
classifier = TopicClassifier(
    keyword_weight=0.4,
    embedding_weight=0.6,
    min_score_threshold=0.2,
    max_topics=5
)

print(f"TopicClassifier initialized: {len(classifier.master_topics)} topics, {len(classifier.topic_embeddings)} embeddings")

# Get database session
db = SessionLocal()

try:
    # Get 100 records with embeddings
    records = db.query(SentimentData).join(
        SentimentEmbedding,
        SentimentData.entry_id == SentimentEmbedding.entry_id
    ).filter(
        SentimentData.text.isnot(None),
        SentimentData.text != '',
        text("LENGTH(text) > 50")
    ).limit(100).all()
    
    print(f"\nTesting with {len(records)} records from database...")
    
    results = []
    total_time = 0
    
    for i, record in enumerate(records, 1):
        if i % 20 == 0:
            print(f"  Processing record {i}/{len(records)}...")
        
        # Get text
        text_content = record.text or record.content or record.description or ""
        if not text_content:
            continue
        
        # Get embedding
        emb_record = db.query(SentimentEmbedding).filter(
            SentimentEmbedding.entry_id == record.entry_id
        ).first()
        
        embedding = None
        if emb_record and emb_record.embedding:
            if isinstance(emb_record.embedding, str):
                embedding = json.loads(emb_record.embedding)
            else:
                embedding = emb_record.embedding
        
        # Classify
        start = time.time()
        topics = classifier.classify(text_content, text_embedding=embedding)
        elapsed = (time.time() - start) * 1000
        total_time += elapsed
        
        # Prepare result row
        topics_str = "; ".join([f"{t['topic_name']} ({t['confidence']:.3f})" for t in topics]) if topics else "None"
        topics_json = json.dumps([{
            "topic": t['topic'],
            "topic_name": t['topic_name'],
            "confidence": t['confidence'],
            "keyword_score": t['keyword_score'],
            "embedding_score": t['embedding_score']
        } for t in topics])
        
        results.append({
            "entry_id": record.entry_id,
            "text": text_content[:500],  # Limit text length
            "text_length": len(text_content),
            "platform": record.platform or "",
            "source": record.source or "",
            "has_embedding": "Yes" if embedding else "No",
            "topics_found": len(topics),
            "topics": topics_str,
            "topics_json": topics_json,
            "classification_time_ms": round(elapsed, 2),
            "existing_ministry": record.ministry_hint or "",
            "existing_issue": record.issue_slug or "",
            "created_at": record.created_at.isoformat() if record.created_at else ""
        })
    
    # Save to CSV
    output_file = Path(__file__).parent.parent / "topic_classification_results_100.csv"
    
    if results:
        fieldnames = [
            "entry_id", "text", "text_length", "platform", "source",
            "has_embedding", "topics_found", "topics", "topics_json",
            "classification_time_ms", "existing_ministry", "existing_issue", "created_at"
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n{'='*70}")
        print(f"Results saved to: {output_file}")
        print(f"{'='*70}")
        
        # Summary statistics
        matches = sum(1 for r in results if r['topics_found'] > 0)
        avg_time = total_time / len(results)
        
        print(f"\nSummary:")
        print(f"  Records tested: {len(results)}")
        print(f"  Records with topics: {matches} ({matches/len(results)*100:.1f}%)")
        print(f"  Average classification time: {avg_time:.2f}ms")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Throughput: {len(results)/(total_time/1000):.1f} records/sec")
        
        # Topic distribution
        topic_counts = {}
        for result in results:
            if result['topics_json']:
                topics_data = json.loads(result['topics_json'])
                for topic in topics_data:
                    topic_key = topic['topic']
                    topic_counts[topic_key] = topic_counts.get(topic_key, 0) + 1
        
        if topic_counts:
            print(f"\nTopic Distribution:")
            for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
                topic_name = classifier.master_topics.get(topic, {}).get('name', topic)
                print(f"  {topic_name:30} : {count:3} matches")
        
        print(f"\nCSV file contains:")
        print(f"  - Entry ID, Text, Platform, Source")
        print(f"  - Topics found (human-readable and JSON)")
        print(f"  - Classification metrics")
        print(f"  - Existing ministry/issue classifications")
        print(f"\n[SUCCESS] Test completed and results saved!")
    else:
        print("\n[ERROR] No results to save")

finally:
    db.close()
















