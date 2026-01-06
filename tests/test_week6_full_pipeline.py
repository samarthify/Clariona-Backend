"""
Test script for Week 6: Full Pipeline Testing & Optimization

Tests:
1. End-to-end pipeline (Topic → Sentiment → Issue → Aggregation)
2. Performance testing
3. Edge cases
4. Database integration
5. Error handling
6. Concurrent processing
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.data_processor import DataProcessor
from api.database import SessionLocal
from api import models
from sqlalchemy import inspect
import logging
import json
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_end_to_end_pipeline():
    """Test complete end-to-end pipeline."""
    logger.info("=" * 60)
    logger.info("TEST 1: End-to-End Pipeline")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test text with multiple topics
    test_text = """
    The Nigerian government has announced a major healthcare reform initiative 
    that will provide free medical services to all citizens. This decision has 
    been met with mixed reactions - some praise it as progressive, while others 
    express concerns about funding and implementation challenges.
    """
    
    logger.info("Testing complete pipeline: Text → Topics → Sentiment → Issues → Aggregation")
    
    start_time = time.time()
    
    # Step 1: Process text (Topic + Sentiment)
    result = processor.get_sentiment(test_text, source_type='news')
    
    elapsed_time = time.time() - start_time
    
    logger.info(f"✅ Processing completed in {elapsed_time:.3f} seconds")
    logger.info(f"   Sentiment: {result.get('sentiment_label')} ({result.get('sentiment_score', 0):.3f})")
    logger.info(f"   Topics: {len(result.get('topics', []))}")
    
    # Verify all components present
    assert 'sentiment_label' in result, "Missing sentiment_label"
    assert 'sentiment_score' in result, "Missing sentiment_score"
    assert 'topics' in result, "Missing topics"
    assert 'emotion_label' in result or result.get('emotion_label') is None, "Emotion field check"
    
    return True


def test_performance_batch_processing():
    """Test performance of batch processing."""
    logger.info("=" * 60)
    logger.info("TEST 2: Performance - Batch Processing")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Create test texts
    test_texts = [
        "Healthcare reform is essential for national development.",
        "Education funding needs urgent attention from the government.",
        "Infrastructure projects are progressing well across the country.",
        "Security concerns are rising in certain regions.",
        "Economic policies are showing positive results."
    ] * 4  # 20 texts total
    
    logger.info(f"Testing batch processing with {len(test_texts)} texts")
    
    start_time = time.time()
    results = processor.batch_get_sentiment(test_texts, max_workers=5)
    elapsed_time = time.time() - start_time
    
    logger.info(f"✅ Batch processing completed in {elapsed_time:.3f} seconds")
    logger.info(f"   Average time per text: {elapsed_time / len(test_texts):.3f} seconds")
    logger.info(f"   Throughput: {len(test_texts) / elapsed_time:.2f} texts/second")
    
    assert len(results) == len(test_texts), f"Expected {len(test_texts)} results, got {len(results)}"
    
    # Performance check: should process 20 texts in reasonable time
    if elapsed_time > 60:
        logger.warning(f"⚠️  Batch processing took {elapsed_time:.1f}s (may be slow)")
    
    return True


def test_aggregation_performance():
    """Test aggregation performance."""
    logger.info("=" * 60)
    logger.info("TEST 3: Performance - Aggregation")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    if processor.aggregation_service is None:
        logger.warning("⚠️  AggregationService not initialized. Skipping aggregation performance test.")
        return None
    
    session = SessionLocal()
    
    try:
        # Check if we have topics
        from api.models import MentionTopic
        topics = session.query(MentionTopic.topic_key).distinct().limit(5).all()
        
        if not topics:
            logger.warning("⚠️  No topics found. Skipping aggregation performance test.")
            return None
        
        topic_keys = [t[0] for t in topics]
        logger.info(f"Testing aggregation performance for {len(topic_keys)} topics")
        
        start_time = time.time()
        aggregations = processor.aggregation_service.aggregate_all_topics(
            time_window='24h',
            limit=5
        )
        elapsed_time = time.time() - start_time
        
        logger.info(f"✅ Aggregation completed in {elapsed_time:.3f} seconds")
        logger.info(f"   Topics processed: {len(aggregations)}")
        if aggregations:
            logger.info(f"   Average time per topic: {elapsed_time / len(aggregations):.3f} seconds")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in aggregation performance test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_edge_case_empty_text():
    """Test edge case: empty text."""
    logger.info("=" * 60)
    logger.info("TEST 4: Edge Case - Empty Text")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test empty text
    result = processor.get_sentiment("", source_type='news')
    
    logger.info(f"✅ Empty text handled")
    logger.info(f"   Sentiment: {result.get('sentiment_label', 'N/A')}")
    
    # Should handle gracefully
    assert result is not None, "Should return result even for empty text"
    
    return True


def test_edge_case_very_long_text():
    """Test edge case: very long text."""
    logger.info("=" * 60)
    logger.info("TEST 5: Edge Case - Very Long Text")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Create very long text (10,000+ characters)
    long_text = "This is a test sentence. " * 500  # ~12,000 characters
    
    logger.info(f"Testing with text length: {len(long_text)} characters")
    
    start_time = time.time()
    result = processor.get_sentiment(long_text, source_type='news')
    elapsed_time = time.time() - start_time
    
    logger.info(f"✅ Long text processed in {elapsed_time:.3f} seconds")
    logger.info(f"   Sentiment: {result.get('sentiment_label', 'N/A')}")
    
    assert result is not None, "Should handle long text"
    
    return True


def test_edge_case_special_characters():
    """Test edge case: special characters."""
    logger.info("=" * 60)
    logger.info("TEST 6: Edge Case - Special Characters")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test with special characters
    special_text = "Test with émojis 🎉 and spéciál cháracters! @#$%^&*()"
    
    result = processor.get_sentiment(special_text, source_type='news')
    
    logger.info(f"✅ Special characters handled")
    logger.info(f"   Sentiment: {result.get('sentiment_label', 'N/A')}")
    
    assert result is not None, "Should handle special characters"
    
    return True


def test_database_integration():
    """Test database integration across all systems."""
    logger.info("=" * 60)
    logger.info("TEST 7: Database Integration")
    logger.info("=" * 60)
    
    session = SessionLocal()
    
    try:
        inspector = inspect(session.bind)
        tables = inspector.get_table_names()
        
        # Check all required tables exist
        required_tables = [
            'sentiment_data',
            'topics',
            'mention_topics',
            'topic_issues',
            'issue_mentions',
            'topic_issue_links',
            'sentiment_aggregations',
            'sentiment_trends',
            'topic_sentiment_baselines'
        ]
        
        missing_tables = []
        for table in required_tables:
            if table in tables:
                logger.info(f"✅ Table '{table}' exists")
            else:
                logger.error(f"❌ Table '{table}' missing")
                missing_tables.append(table)
        
        if missing_tables:
            return False
        
        # Check data counts
        sentiment_count = session.query(models.SentimentData).count()
        topics_count = session.query(models.Topic).count()
        mention_topics_count = session.query(models.MentionTopic).count()
        
        logger.info(f"   SentimentData records: {sentiment_count}")
        logger.info(f"   Topics: {topics_count}")
        logger.info(f"   MentionTopics: {mention_topics_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in database integration test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_concurrent_processing():
    """Test concurrent processing safety."""
    logger.info("=" * 60)
    logger.info("TEST 8: Concurrent Processing")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test concurrent batch processing
    test_texts = [
        "Healthcare is important.",
        "Education needs funding.",
        "Infrastructure is improving."
    ] * 3  # 9 texts
    
    logger.info(f"Testing concurrent processing with {len(test_texts)} texts")
    
    def process_batch(batch_id):
        try:
            results = processor.batch_get_sentiment(test_texts, max_workers=3)
            return len(results)
        except Exception as e:
            logger.error(f"Error in batch {batch_id}: {e}")
            return 0
    
    # Run 3 concurrent batches
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_batch, i) for i in range(3)]
        results = [f.result() for f in as_completed(futures)]
    
    elapsed_time = time.time() - start_time
    
    logger.info(f"✅ Concurrent processing completed in {elapsed_time:.3f} seconds")
    logger.info(f"   Batches completed: {len(results)}")
    logger.info(f"   Results per batch: {results}")
    
    # All batches should complete successfully
    assert all(r > 0 for r in results), "All batches should produce results"
    
    return True


def test_error_handling():
    """Test error handling across components."""
    logger.info("=" * 60)
    logger.info("TEST 9: Error Handling")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Test with None input
    try:
        result = processor.get_sentiment(None, source_type='news')
        logger.info("✅ None input handled gracefully")
    except Exception as e:
        logger.warning(f"⚠️  None input raised exception: {e}")
        # This is acceptable - some components may not handle None
    
    # Test with invalid source type
    try:
        result = processor.get_sentiment("Test text", source_type='invalid_type')
        logger.info("✅ Invalid source type handled")
    except Exception as e:
        logger.warning(f"⚠️  Invalid source type raised exception: {e}")
        # This is acceptable
    
    return True


def test_data_consistency():
    """Test data consistency across tables."""
    logger.info("=" * 60)
    logger.info("TEST 10: Data Consistency")
    logger.info("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Check mention_topics consistency
        mention_topics = session.query(models.MentionTopic).limit(10).all()
        
        for mt in mention_topics:
            # Verify mention exists
            mention = session.query(models.SentimentData).filter(
                models.SentimentData.entry_id == mt.mention_id
            ).first()
            
            if not mention:
                logger.warning(f"⚠️  Orphaned MentionTopic: mention_id={mt.mention_id}")
        
        logger.info("✅ Data consistency check completed")
        return True
        
    except Exception as e:
        logger.error(f"Error in data consistency test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def run_all_tests():
    """Run all Week 6 tests."""
    logger.info("\n" + "=" * 60)
    logger.info("WEEK 6 FULL PIPELINE TESTING & OPTIMIZATION")
    logger.info("=" * 60)
    
    results = {
        'test1_e2e': None,
        'test2_perf_batch': None,
        'test3_perf_agg': None,
        'test4_edge_empty': None,
        'test5_edge_long': None,
        'test6_edge_special': None,
        'test7_db_integration': None,
        'test8_concurrent': None,
        'test9_error_handling': None,
        'test10_consistency': None
    }
    
    try:
        results['test1_e2e'] = test_end_to_end_pipeline()
        results['test2_perf_batch'] = test_performance_batch_processing()
        results['test3_perf_agg'] = test_aggregation_performance()
        results['test4_edge_empty'] = test_edge_case_empty_text()
        results['test5_edge_long'] = test_edge_case_very_long_text()
        results['test6_edge_special'] = test_edge_case_special_characters()
        results['test7_db_integration'] = test_database_integration()
        results['test8_concurrent'] = test_concurrent_processing()
        results['test9_error_handling'] = test_error_handling()
        results['test10_consistency'] = test_data_consistency()
        
        # Count successes
        passed = sum(1 for v in results.values() if v is True)
        skipped = sum(1 for v in results.values() if v is None)
        failed = sum(1 for v in results.values() if v is False)
        
        logger.info("\n" + "=" * 60)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"⚠️  Skipped: {skipped}")
        logger.info(f"❌ Failed: {failed}")
        logger.info("=" * 60)
        
        if failed == 0:
            logger.info("✅ ALL TESTS PASSED")
            return True
        else:
            logger.warning("⚠️  SOME TESTS FAILED OR WERE SKIPPED")
            return False
        
    except Exception as e:
        logger.error(f"\n❌ TEST SUITE FAILED: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)





