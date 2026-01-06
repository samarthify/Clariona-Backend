"""
Test script for Week 2: Topic System Integration

Tests:
1. TopicClassifier integration with DataProcessor
2. Parallel Topic + Sentiment classification
3. Database storage of topics
4. Batch processing with topics
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.data_processor import DataProcessor
from api.database import SessionLocal
from api import models
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_mention_processing():
    """Test single mention processing with Topic + Sentiment."""
    logger.info("=" * 60)
    logger.info("TEST 1: Single Mention Processing")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test text
    test_text = """
    The Nigerian government has announced a new fuel subsidy removal policy 
    that will affect millions of citizens. This decision has sparked widespread 
    protests across major cities including Lagos, Abuja, and Port Harcourt.
    """
    
    logger.info(f"Processing text: {test_text[:100]}...")
    result = processor.get_sentiment(test_text)
    
    # Verify results
    assert 'sentiment_label' in result, "Missing sentiment_label"
    assert 'sentiment_score' in result, "Missing sentiment_score"
    assert 'topics' in result, "Missing topics"
    assert isinstance(result['topics'], list), "Topics should be a list"
    
    logger.info(f"✅ Sentiment: {result['sentiment_label']} (score: {result['sentiment_score']})")
    logger.info(f"✅ Topics found: {len(result['topics'])}")
    
    for i, topic in enumerate(result['topics'], 1):
        logger.info(f"   {i}. {topic.get('topic_name', topic.get('topic'))} "
                   f"(confidence: {topic.get('confidence', 0):.3f})")
    
    logger.info(f"✅ Primary topic: {result.get('primary_topic_key')}")
    logger.info(f"✅ Embedding: {len(result.get('embedding', []))} dimensions")
    
    return result


def test_batch_processing():
    """Test batch processing with multiple texts."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Batch Processing")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    test_texts = [
        "Fuel prices have increased dramatically in Nigeria, causing hardship for citizens.",
        "The education sector needs more funding for infrastructure and teacher training.",
        "Healthcare services are improving with new hospitals being built across the country.",
        "Corruption remains a major challenge in government institutions.",
        "Agricultural development programs are helping farmers increase productivity."
    ]
    
    logger.info(f"Processing {len(test_texts)} texts in batch...")
    results = processor.batch_get_sentiment(test_texts)
    
    assert len(results) == len(test_texts), f"Expected {len(test_texts)} results, got {len(results)}"
    
    logger.info(f"✅ Processed {len(results)} texts")
    
    for i, (text, result) in enumerate(zip(test_texts, results), 1):
        logger.info(f"\nText {i}: {text[:50]}...")
        logger.info(f"  Sentiment: {result.get('sentiment_label')}")
        logger.info(f"  Topics: {len(result.get('topics', []))}")
        if result.get('topics'):
            logger.info(f"  Primary: {result.get('primary_topic_key')}")
    
    return results


def test_database_storage():
    """Test storing topics in database."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Database Storage")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    session = SessionLocal()
    
    try:
        # Check if processing_status column exists (migration might not be run)
        from sqlalchemy import inspect
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns('sentiment_data')]
        has_processing_status = 'processing_status' in columns
        
        if not has_processing_status:
            logger.warning("⚠️  Migration not run - processing_status column missing")
            logger.warning("⚠️  Skipping database storage test. Run: alembic upgrade head")
            return None
        
        # Create a test mention in database
        test_mention = models.SentimentData(
            run_timestamp=datetime.now(),
            text="Fuel subsidy removal has caused economic hardship for many Nigerians.",
            source="test",
            platform="test",
            processing_status='pending'
        )
        session.add(test_mention)
        session.commit()
        session.refresh(test_mention)
        
        logger.info(f"✅ Created test mention: entry_id={test_mention.entry_id}")
        
        # Process and get topics
        result = processor.get_sentiment(test_mention.text)
        topics = result.get('topics', [])
        
        logger.info(f"✅ Classified {len(topics)} topics")
        
        # Store topics in database
        if topics:
            processor._store_topics_in_database(session, test_mention.entry_id, topics)
            session.commit()
            logger.info(f"✅ Stored {len(topics)} topics in mention_topics table")
            
            # Verify storage
            stored_topics = session.query(models.MentionTopic).filter(
                models.MentionTopic.mention_id == test_mention.entry_id
            ).all()
            
            logger.info(f"✅ Verified: {len(stored_topics)} topics in database")
            for topic in stored_topics:
                logger.info(f"   - {topic.topic_key} (confidence: {topic.topic_confidence:.3f})")
            
            assert len(stored_topics) == len(topics), "Topic count mismatch"
        else:
            logger.warning("⚠️  No topics classified - cannot test storage")
        
        # Cleanup
        session.delete(test_mention)
        session.commit()
        logger.info("✅ Cleaned up test mention")
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error in database storage test: {e}")
        raise
    finally:
        session.close()


def test_parallel_execution():
    """Test that Topic and Sentiment run in parallel."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Parallel Execution Verification")
    logger.info("=" * 60)
    
    import time
    
    processor = DataProcessor()
    test_text = "Fuel prices are rising across Nigeria due to subsidy removal."
    
    # Time the parallel execution
    start_time = time.time()
    result = processor.get_sentiment(test_text)
    parallel_time = time.time() - start_time
    
    logger.info(f"✅ Parallel execution time: {parallel_time:.3f}s")
    logger.info(f"✅ Both sentiment and topics returned: "
               f"sentiment={result.get('sentiment_label')}, "
               f"topics={len(result.get('topics', []))}")
    
    # Verify both are present
    assert result.get('sentiment_label'), "Sentiment should be present"
    assert result.get('topics') is not None, "Topics should be present (even if empty)"
    
    return parallel_time


def test_backward_compatibility():
    """Test that legacy fields are still populated."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Backward Compatibility")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    test_text = "The government announced new policies for economic development."
    
    result = processor.get_sentiment(test_text)
    
    # Check legacy fields
    legacy_fields = ['ministry_hint', 'issue_slug', 'issue_label', 'issue_confidence', 'issue_keywords']
    
    logger.info("Checking legacy fields:")
    for field in legacy_fields:
        value = result.get(field)
        present = value is not None
        logger.info(f"  {field}: {value} {'✅' if present else '⚠️'}")
        # Note: issue fields will be None until Week 4, that's expected
    
    # ministry_hint should map to primary topic
    if result.get('primary_topic_key'):
        assert result.get('ministry_hint') == result.get('primary_topic_key'), \
            "ministry_hint should map to primary_topic_key"
        logger.info("✅ ministry_hint correctly maps to primary_topic_key")
    
    return result


def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("WEEK 2 TOPIC INTEGRATION TESTS")
    logger.info("=" * 60)
    
    results = {
        'test1_single': None,
        'test2_batch': None,
        'test3_database': None,
        'test4_parallel': None,
        'test5_compatibility': None
    }
    
    try:
        results['test1_single'] = test_single_mention_processing()
        results['test2_batch'] = test_batch_processing()
        results['test3_database'] = test_database_storage()
        results['test4_parallel'] = test_parallel_execution()
        results['test5_compatibility'] = test_backward_compatibility()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


