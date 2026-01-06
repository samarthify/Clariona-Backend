"""
Simple test of TopicClassifier using real database data.
Tests the classifier as it would be used in the actual pipeline.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

import json
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding
from processing.topic_classifier import TopicClassifier

# Initialize classifier (as it would be in the pipeline)
classifier = TopicClassifier(
    keyword_weight=0.3,
    embedding_weight=0.7,
    min_score_threshold=0.3,
    max_topics=5
)

print(f"\nTopicClassifier initialized: {len(classifier.master_topics)} topics, {len(classifier.topic_embeddings)} embeddings")

# Get database session
db = SessionLocal()

try:
    # Get records with embeddings
    records = db.query(SentimentData).join(
        SentimentEmbedding,
        SentimentData.entry_id == SentimentEmbedding.entry_id
    ).filter(
        SentimentData.text.isnot(None),
        SentimentData.text != '',
        text("LENGTH(text) > 50")
    ).limit(50).all()
    
    print(f"\nTesting with {len(records)} records from database...\n")
    
    matches = 0
    total_time = 0
    topic_counts = {}
    
    for i, record in enumerate(records, 1):
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
        
        # Classify (as it would be in pipeline)
        start = time.time()
        topics = classifier.classify(text_content, text_embedding=embedding)
        elapsed = (time.time() - start) * 1000
        total_time += elapsed
        
        if topics:
            matches += 1
            if matches <= 10:  # Show first 10 matches
                text_preview = text_content[:70].encode('ascii', 'ignore').decode('ascii')
                print(f"Record {i} (ID: {record.entry_id}):")
                print(f"  Text: {text_preview}...")
                for topic in topics:
                    print(f"  -> {topic['topic_name']} (conf: {topic['confidence']:.3f}, kw: {topic['keyword_score']:.3f}, emb: {topic['embedding_score']:.3f})")
                    topic_counts[topic['topic']] = topic_counts.get(topic['topic'], 0) + 1
                print()
            else:
                # Just count for rest
                for topic in topics:
                    topic_counts[topic['topic']] = topic_counts.get(topic['topic'], 0) + 1
    
    print(f"\n{'='*70}")
    print(f"Results: {matches}/{len(records)} records matched ({matches/len(records)*100:.1f}%)")
    print(f"Average time: {total_time/len(records):.2f}ms")
    print(f"Throughput: {len(records)/(total_time/1000):.1f} records/sec")
    
    if topic_counts:
        print(f"\nTopic Distribution:")
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            topic_name = classifier.master_topics.get(topic, {}).get('name', topic)
            print(f"  {topic_name:30} : {count:3} matches")

finally:
    db.close()

