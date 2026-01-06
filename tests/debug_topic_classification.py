"""Debug why some records have 0 topics."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.topic_classifier import TopicClassifier
from processing.data_processor import DataProcessor
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test texts from the records that had 0 topics
test_texts = [
    "@Pweetyqueeny @Rychus7178064 @de_generalnoni @JDVance I trust president trump th...",  # Record 74104 - 0 topics
    "@PastorMarvy The same way your vote will not hold water against president tinubu...",  # Record 74106 - 0 topics
]

classifier = TopicClassifier()
processor = DataProcessor()

print("=" * 80)
print("DEBUGGING TOPIC CLASSIFICATION - Why 0 topics?")
print("=" * 80)

for i, text in enumerate(test_texts, 1):
    print(f"\n{'='*80}")
    print(f"Text {i}: {text[:100]}...")
    print(f"{'='*80}")
    
    # Get sentiment (to get embedding)
    sentiment_result = processor.sentiment_analyzer.analyze(text)
    embedding = sentiment_result.get('embedding')
    
    print(f"\nEmbedding: {'Present' if embedding and len(embedding) == 1536 else 'Missing/Invalid'}")
    if embedding:
        is_zero = all(x == 0.0 for x in embedding[:10])
        print(f"Embedding is zero: {is_zero}")
    
    # Classify topics
    if embedding and len(embedding) == 1536:
        topics = classifier.classify(text, embedding)
    else:
        topics = classifier.classify(text)
    
    print(f"\nTopics found: {len(topics)}")
    
    if topics:
        print("\nTop topics:")
        for j, topic in enumerate(topics[:3], 1):
            print(f"  {j}. {topic.get('topic')} ({topic.get('topic_name')})")
            print(f"     Confidence: {topic.get('confidence', 0):.3f}")
            print(f"     Keyword score: {topic.get('keyword_score', 0):.3f}")
            print(f"     Embedding score: {topic.get('embedding_score', 0):.3f}")
    else:
        print("\n[DEBUG] No topics found. Checking thresholds...")
        print(f"  min_score_threshold: {classifier.min_score_threshold}")
        print(f"  keyword_weight: {classifier.keyword_weight}")
        print(f"  embedding_weight: {classifier.embedding_weight}")
        
        # Check keyword matching and scores manually
        print("\n  Checking keyword matches and scores...")
        text_lower = text.lower()
        import numpy as np
        from utils.similarity import cosine_similarity
        
        text_emb = np.array(embedding, dtype=np.float32) if embedding and len(embedding) == 1536 else None
        
        for topic_key, topic_data in list(classifier.master_topics.items())[:10]:  # Check first 10 topics
            keywords = topic_data.get('keywords', [])
            keyword_groups = topic_data.get('keyword_groups')
            
            # Calculate keyword score
            keyword_score = classifier._keyword_match(
                text_lower,
                keywords=keywords if not keyword_groups else None,
                keyword_groups=keyword_groups
            )
            
            # Calculate embedding score
            embedding_score = 0.0
            if topic_key in classifier.topic_embeddings and text_emb is not None:
                topic_emb = classifier.topic_embeddings[topic_key]
                similarity = cosine_similarity(text_emb, topic_emb)
                embedding_score = max(0.0, float(similarity))
            
            # Calculate combined score
            combined_score = (
                classifier.keyword_weight * keyword_score +
                classifier.embedding_weight * embedding_score
            )
            
            # Check filtering
            if keyword_score == 0.0 and embedding_score < 0.25:
                status = "SKIPPED (no keywords + low embedding)"
            elif combined_score >= classifier.min_score_threshold:
                status = f"INCLUDED (score: {combined_score:.3f})"
            else:
                status = f"FILTERED (score: {combined_score:.3f} < {classifier.min_score_threshold})"
            
            if keyword_score > 0 or embedding_score > 0.1:
                print(f"    {topic_key}:")
                print(f"      Keyword score: {keyword_score:.3f}")
                print(f"      Embedding score: {embedding_score:.3f}")
                print(f"      Combined score: {combined_score:.3f}")
                print(f"      Status: {status}")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)

