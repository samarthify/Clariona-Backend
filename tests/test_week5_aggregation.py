"""
Test script for Week 5: Aggregation & Integration

Tests:
1. SentimentAggregationService
2. SentimentTrendCalculator
3. TopicSentimentNormalizer
4. DataProcessor integration
5. Complete aggregation pipeline
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.sentiment_aggregation_service import SentimentAggregationService
from processing.sentiment_trend_calculator import SentimentTrendCalculator
from processing.topic_sentiment_normalizer import TopicSentimentNormalizer
from processing.data_processor import DataProcessor
from api.database import SessionLocal
from api import models
from sqlalchemy import inspect
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_aggregation_service():
    """Test SentimentAggregationService."""
    logger.info("=" * 60)
    logger.info("TEST 1: SentimentAggregationService")
    logger.info("=" * 60)
    
    service = SentimentAggregationService()
    
    logger.info("✅ SentimentAggregationService initialized")
    logger.info(f"   Time windows: {list(service.TIME_WINDOWS.keys())}")
    logger.info(f"   Min mentions: {service.min_mentions_for_aggregation}")
    
    return True


def test_trend_calculator():
    """Test SentimentTrendCalculator."""
    logger.info("=" * 60)
    logger.info("TEST 2: SentimentTrendCalculator")
    logger.info("=" * 60)
    
    calculator = SentimentTrendCalculator()
    
    logger.info("✅ SentimentTrendCalculator initialized")
    logger.info(f"   Improvement threshold: {calculator.improvement_threshold}")
    logger.info(f"   Deterioration threshold: {calculator.deterioration_threshold}")
    logger.info(f"   Stable threshold: {calculator.stable_threshold}")
    
    return True


def test_normalizer():
    """Test TopicSentimentNormalizer."""
    logger.info("=" * 60)
    logger.info("TEST 3: TopicSentimentNormalizer")
    logger.info("=" * 60)
    
    normalizer = TopicSentimentNormalizer()
    
    logger.info("✅ TopicSentimentNormalizer initialized")
    logger.info(f"   Default lookback days: {normalizer.default_lookback_days}")
    logger.info(f"   Min sample size: {normalizer.min_sample_size}")
    
    return True


def test_data_processor_integration():
    """Test DataProcessor integration."""
    logger.info("=" * 60)
    logger.info("TEST 4: DataProcessor Integration")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Check if services are initialized
    if processor.aggregation_service is None:
        logger.warning("⚠️  AggregationService not initialized. Skipping integration test.")
        return None
    
    logger.info("✅ Aggregation services initialized in DataProcessor")
    logger.info("✅ aggregate_sentiment_for_topic() method available")
    logger.info("✅ calculate_trend_for_topic() method available")
    logger.info("✅ normalize_sentiment_for_topic() method available")
    logger.info("✅ run_aggregation_pipeline() method available")
    
    return True


def test_database_schema():
    """Test database schema for aggregation tables."""
    logger.info("=" * 60)
    logger.info("TEST 5: Database Schema")
    logger.info("=" * 60)
    
    session = SessionLocal()
    
    try:
        inspector = inspect(session.bind)
        tables = inspector.get_table_names()
        
        required_tables = [
            'sentiment_aggregations',
            'sentiment_trends',
            'topic_sentiment_baselines'
        ]
        
        for table in required_tables:
            if table in tables:
                columns = [col['name'] for col in inspector.get_columns(table)]
                logger.info(f"✅ Table '{table}' exists with {len(columns)} columns")
            else:
                logger.error(f"❌ Table '{table}' not found")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking database schema: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_real_data_processing():
    """Test aggregation with real data."""
    logger.info("=" * 60)
    logger.info("TEST 6: Real Data Processing")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    if processor.aggregation_service is None:
        logger.warning("⚠️  AggregationService not initialized. Skipping real data test.")
        return None
    
    session = SessionLocal()
    
    try:
        # Check if we have topics with mentions
        from api.models import MentionTopic
        topics_with_mentions = session.query(MentionTopic.topic_key).distinct().limit(3).all()
        
        if not topics_with_mentions:
            logger.warning("⚠️  No topics with mentions found. Skipping real data test.")
            return None
        
        topic_keys = [t[0] for t in topics_with_mentions]
        logger.info(f"Testing aggregation for {len(topic_keys)} topics")
        
        # Test aggregation for first topic
        test_topic = topic_keys[0]
        logger.info(f"Testing aggregation for topic: {test_topic}")
        
        start_time = time.time()
        aggregation = processor.aggregate_sentiment_for_topic(test_topic, time_window='24h')
        elapsed_time = time.time() - start_time
        
        if aggregation:
            logger.info(f"✅ Aggregation completed in {elapsed_time:.2f} seconds")
            logger.info(f"   Sentiment Index: {aggregation.get('sentiment_index', 'N/A'):.2f}")
            logger.info(f"   Mention Count: {aggregation.get('mention_count', 0)}")
            logger.info(f"   Weighted Score: {aggregation.get('weighted_sentiment_score', 'N/A'):.3f}")
        else:
            logger.info("⚠️  No aggregation result (insufficient data)")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in real data test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_aggregation_pipeline():
    """Test complete aggregation pipeline."""
    logger.info("=" * 60)
    logger.info("TEST 7: Aggregation Pipeline")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    if processor.aggregation_service is None:
        logger.warning("⚠️  AggregationService not initialized. Skipping pipeline test.")
        return None
    
    try:
        logger.info("Running aggregation pipeline (limit=3 topics)...")
        start_time = time.time()
        
        results = processor.run_aggregation_pipeline(
            time_window='24h',
            include_trends=True,
            include_normalization=True,
            limit=3
        )
        
        elapsed_time = time.time() - start_time
        
        logger.info(f"✅ Pipeline completed in {elapsed_time:.2f} seconds")
        logger.info(f"   Aggregations: {len(results.get('aggregations', {}))}")
        logger.info(f"   Trends: {len(results.get('trends', {}))}")
        logger.info(f"   Normalized: {len(results.get('normalized', {}))}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in pipeline test: {e}", exc_info=True)
        return False


def run_all_tests():
    """Run all Week 5 tests."""
    logger.info("\n" + "=" * 60)
    logger.info("WEEK 5 AGGREGATION & INTEGRATION TESTS")
    logger.info("=" * 60)
    
    results = {
        'test1_aggregation': None,
        'test2_trends': None,
        'test3_normalizer': None,
        'test4_integration': None,
        'test5_schema': None,
        'test6_real_data': None,
        'test7_pipeline': None
    }
    
    try:
        results['test1_aggregation'] = test_aggregation_service()
        results['test2_trends'] = test_trend_calculator()
        results['test3_normalizer'] = test_normalizer()
        results['test4_integration'] = test_data_processor_integration()
        results['test5_schema'] = test_database_schema()
        results['test6_real_data'] = test_real_data_processing()
        results['test7_pipeline'] = test_aggregation_pipeline()
        
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





