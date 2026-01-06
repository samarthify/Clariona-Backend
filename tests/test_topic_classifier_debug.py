"""
Debug script to investigate why topics aren't being classified.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.topic_classifier import TopicClassifier
from api.database import SessionLocal
from api import models
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test text
test_text = "Fuel prices have increased dramatically in Nigeria, causing hardship for citizens."

logger.info("=" * 60)
logger.info("TOPIC CLASSIFIER DEBUG")
logger.info("=" * 60)

# Initialize classifier
classifier = TopicClassifier()

logger.info(f"\nClassifier initialized:")
logger.info(f"  - Topics loaded: {len(classifier.master_topics)}")
logger.info(f"  - Embeddings loaded: {len(classifier.topic_embeddings)}")
logger.info(f"  - Min score threshold: {classifier.min_score_threshold}")
logger.info(f"  - Keyword weight: {classifier.keyword_weight}")
logger.info(f"  - Embedding weight: {classifier.embedding_weight}")

# List all topics
logger.info(f"\nAvailable topics:")
for topic_key, topic_data in classifier.master_topics.items():
    keywords = topic_data.get('keywords', [])
    keyword_groups = topic_data.get('keyword_groups')
    has_embedding = topic_key in classifier.topic_embeddings
    embedding = classifier.topic_embeddings.get(topic_key)
    is_zero = embedding is not None and all(x == 0.0 for x in embedding[:10]) if embedding is not None else None
    
    logger.info(f"  - {topic_key}: {topic_data.get('name', 'N/A')}")
    logger.info(f"    Keywords: {len(keywords)} keywords")
    if keyword_groups:
        logger.info(f"    Keyword groups: {len(keyword_groups)} groups")
    logger.info(f"    Has embedding: {has_embedding}")
    if embedding is not None:
        logger.info(f"    Embedding dim: {len(embedding)}")
        logger.info(f"    Embedding is zero: {is_zero}")
        if is_zero:
            logger.warning(f"    ⚠️  ZERO VECTOR DETECTED!")

# Test classification WITHOUT embedding (keyword-only)
logger.info(f"\n" + "=" * 60)
logger.info(f"Testing classification WITHOUT embedding (keyword-only):")
logger.info(f"  '{test_text}'")
logger.info("=" * 60)

result = classifier.classify(test_text)
logger.info(f"\nResult: {len(result)} topics found")
for topic in result:
    logger.info(f"  - {topic.get('topic_name')} ({topic.get('topic')}): confidence={topic.get('confidence'):.3f}")

# Test classification WITH a dummy embedding (all zeros - should trigger warning)
logger.info(f"\n" + "=" * 60)
logger.info(f"Testing classification WITH zero embedding:")
logger.info("=" * 60)
zero_embedding = [0.0] * 1536
result_zero = classifier.classify(test_text, zero_embedding)
logger.info(f"Result: {len(result_zero)} topics found")
for topic in result_zero:
    logger.info(f"  - {topic.get('topic_name')} ({topic.get('topic')}): confidence={topic.get('confidence'):.3f}")

# Test classification WITH a real embedding (from sentiment analyzer)
logger.info(f"\n" + "=" * 60)
logger.info(f"Testing classification WITH real embedding (from sentiment analyzer):")
logger.info("=" * 60)
from processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
sentiment_analyzer = PresidentialSentimentAnalyzer()
sentiment_result = sentiment_analyzer.analyze(test_text)
real_embedding = sentiment_result.get('embedding')
if real_embedding and len(real_embedding) == 1536:
    logger.info(f"Got embedding: {len(real_embedding)} dimensions")
    # Check if it's zero
    is_zero = all(x == 0.0 for x in real_embedding[:10])
    logger.info(f"Embedding is zero (first 10): {is_zero}")
    result_with_embedding = classifier.classify(test_text, real_embedding)
    logger.info(f"Result: {len(result_with_embedding)} topics found")
    for topic in result_with_embedding:
        logger.info(f"  - {topic.get('topic_name')} ({topic.get('topic')}): confidence={topic.get('confidence'):.3f}")
else:
    logger.warning(f"Could not get valid embedding: {real_embedding}")

# Test with a simple keyword match
logger.info(f"\n" + "=" * 60)
logger.info("Testing with text that should match 'fuel_pricing':")
logger.info("=" * 60)
test_text2 = "fuel subsidy removal price increase"
result2 = classifier.classify(test_text2)
logger.info(f"Result: {len(result2)} topics found")
for topic in result2:
    logger.info(f"  - {topic.get('topic_name')} ({topic.get('topic')}): confidence={topic.get('confidence'):.3f}")

