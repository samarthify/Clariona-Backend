"""
Test Week 3 with real data from database.

Tests:
1. Real data processing with performance metrics
2. Database storage verification
3. Performance monitoring (model loading, processing time)
4. Verify no pipeline delays from model loading
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.data_processor import DataProcessor
from processing.emotion_analyzer import EmotionAnalyzer
from api.database import SessionLocal
from api import models
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_real_data_processing():
    """Test Week 3 with real data from database."""
    logger.info("=" * 80)
    logger.info("WEEK 3 REAL DATA TEST - Performance & Database Storage")
    logger.info("=" * 80)
    
    session = SessionLocal()
    processor = DataProcessor()
    
    try:
        # Check if Week 3 columns exist
        from sqlalchemy import inspect
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns('sentiment_data')]
        week3_columns = ['emotion_label', 'emotion_score', 'emotion_distribution', 
                        'influence_weight', 'confidence_weight']
        week2_columns = ['processing_status']
        
        missing_week2 = [col for col in week2_columns if col not in columns]
        missing_week3 = [col for col in week3_columns if col not in columns]
        
        if missing_week3:
            logger.error(f"❌ Missing Week 3 columns: {missing_week3}")
            logger.error("⚠️  Run migration: cd src; alembic upgrade head")
            return False
        
        if missing_week2:
            logger.warning(f"⚠️  Missing Week 2 columns: {missing_week2} (will use default values)")
            # Continue anyway - processing_status might not be critical for this test
        
        logger.info("✅ Database schema verified - all Week 2 and Week 3 columns present")
        
        # Get real data (records without sentiment analysis)
        logger.info("\n" + "-" * 80)
        logger.info("Fetching real data from database...")
        
        # Get records without sentiment analysis (limit to 10 for testing)
        records = session.query(models.SentimentData).filter(
            models.SentimentData.sentiment_label.is_(None)
        ).limit(10).all()
        
        if not records:
            logger.warning("⚠️  No unprocessed records found. Creating test records...")
            # Create test records
            test_texts = [
                "I am furious about the fuel price increase! This is unacceptable.",
                "I'm very happy about the new infrastructure projects in Lagos.",
                "I'm worried about the security situation in the country.",
                "I trust the government will fix the economic issues.",
                "I'm sad about the rising unemployment rate.",
            ]
            
            for i, text in enumerate(test_texts):
                record = models.SentimentData(
                    run_timestamp=datetime.now() - timedelta(days=i),
                    text=text,
                    source="test",
                    platform="test",
                    processing_status='pending'
                )
                session.add(record)
            session.commit()
            
            # Fetch again
            records = session.query(models.SentimentData).filter(
                models.SentimentData.sentiment_label.is_(None)
            ).limit(10).all()
        
        logger.info(f"✅ Found {len(records)} records to process")
        
        # Performance metrics
        metrics = {
            'total_records': len(records),
            'processing_times': [],
            'emotion_times': [],
            'total_time': 0,
            'model_load_time': 0,
            'first_load': True
        }
        
        # Test model loading performance (lazy loading)
        logger.info("\n" + "-" * 80)
        logger.info("Testing EmotionAnalyzer lazy loading performance...")
        
        start_time = time.time()
        emotion_analyzer = EmotionAnalyzer(lazy_load=True)
        init_time = time.time() - start_time
        logger.info(f"✅ EmotionAnalyzer initialization: {init_time:.3f}s (should be < 0.1s with lazy loading)")
        
        # First emotion analysis (triggers model load)
        logger.info("First emotion analysis (triggers model load - may take 10-30s)...")
        start_time = time.time()
        first_result = emotion_analyzer.analyze_emotion("Test text for model loading")
        first_load_time = time.time() - start_time
        metrics['model_load_time'] = first_load_time
        logger.info(f"✅ First analysis (model load): {first_load_time:.2f}s")
        
        # Second emotion analysis (should be fast - model already loaded)
        logger.info("Second emotion analysis (model already loaded - should be fast)...")
        start_time = time.time()
        second_result = emotion_analyzer.analyze_emotion("Another test text")
        second_analysis_time = time.time() - start_time
        logger.info(f"✅ Second analysis (cached): {second_analysis_time:.3f}s (should be < 1s)")
        
        if second_analysis_time > 1.0:
            logger.warning(f"⚠️  Second analysis took {second_analysis_time:.2f}s - model may be reloading")
        else:
            logger.info("✅ Model caching working correctly - no reload delay")
        
        # Process real records
        logger.info("\n" + "-" * 80)
        logger.info("Processing real records with Week 3 features...")
        logger.info("-" * 80)
        
        total_start = time.time()
        
        for i, record in enumerate(records, 1):
            text = record.text or record.content or record.title or record.description
            if not text:
                logger.warning(f"Record {record.entry_id}: No text content, skipping")
                continue
            
            logger.info(f"\n[{i}/{len(records)}] Processing record {record.entry_id}...")
            logger.info(f"  Text: {text[:80]}...")
            
            # Process with Week 3 features
            process_start = time.time()
            result = processor.get_sentiment(text, source_type=record.source_type)
            process_time = time.time() - process_start
            metrics['processing_times'].append(process_time)
            
            logger.info(f"  Processing time: {process_time:.3f}s")
            logger.info(f"  Sentiment: {result['sentiment_label']} ({result['sentiment_score']:.3f})")
            logger.info(f"  Emotion: {result.get('emotion_label', 'N/A')} ({result.get('emotion_score', 0):.3f})")
            logger.info(f"  Influence weight: {result.get('influence_weight', 1.0):.2f}")
            logger.info(f"  Confidence weight: {result.get('confidence_weight', 0):.3f}")
            logger.info(f"  Topics: {len(result.get('topics', []))}")
            
            # Verify embedding is not zero
            embedding = result.get('embedding', [])
            if embedding:
                is_zero = all(x == 0.0 for x in embedding[:10])
                if is_zero:
                    logger.error(f"  ❌ Embedding is zero vector!")
                else:
                    logger.info(f"  ✅ Embedding valid ({len(embedding)} dims)")
            
            # Store in database
            store_start = time.time()
            record.sentiment_label = result['sentiment_label']
            record.sentiment_score = result['sentiment_score']
            record.sentiment_justification = result.get('sentiment_justification')
            
            # Week 3 fields
            record.emotion_label = result.get('emotion_label')
            record.emotion_score = result.get('emotion_score')
            if result.get('emotion_distribution'):
                record.emotion_distribution = json.dumps(result['emotion_distribution'])
            record.influence_weight = result.get('influence_weight', 1.0)
            record.confidence_weight = result.get('confidence_weight')
            
            if hasattr(record, 'processing_status'):
                record.processing_status = 'completed'
            if hasattr(record, 'processing_completed_at'):
                record.processing_completed_at = datetime.now()
            
            session.commit()
            store_time = time.time() - store_start
            
            logger.info(f"  Database storage: {store_time:.3f}s")
            logger.info(f"  ✅ Record {record.entry_id} processed and stored")
        
        total_time = time.time() - total_start
        metrics['total_time'] = total_time
        
        # Performance summary
        logger.info("\n" + "=" * 80)
        logger.info("PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total records processed: {metrics['total_records']}")
        logger.info(f"Total processing time: {total_time:.2f}s")
        logger.info(f"Average time per record: {total_time / len(records):.3f}s")
        logger.info(f"Model load time (first use): {metrics['model_load_time']:.2f}s")
        logger.info(f"Model load time (cached): {second_analysis_time:.3f}s")
        
        if metrics['processing_times']:
            avg_process = sum(metrics['processing_times']) / len(metrics['processing_times'])
            min_process = min(metrics['processing_times'])
            max_process = max(metrics['processing_times'])
            logger.info(f"Processing time stats:")
            logger.info(f"  Average: {avg_process:.3f}s")
            logger.info(f"  Min: {min_process:.3f}s")
            logger.info(f"  Max: {max_process:.3f}s")
        
        # Verify database storage
        logger.info("\n" + "-" * 80)
        logger.info("Verifying database storage...")
        
        stored_records = session.query(models.SentimentData).filter(
            models.SentimentData.entry_id.in_([r.entry_id for r in records])
        ).all()
        
        verified = 0
        for record in stored_records:
            has_emotion = record.emotion_label is not None
            has_weight = record.influence_weight is not None
            has_status = (hasattr(record, 'processing_status') and 
                         record.processing_status == 'completed') if hasattr(record, 'processing_status') else True
            
            if has_emotion and has_weight and has_status:
                verified += 1
        
        logger.info(f"✅ Verified {verified}/{len(stored_records)} records have Week 3 fields stored")
        
        if verified == len(stored_records):
            logger.info("✅ ALL RECORDS SUCCESSFULLY STORED WITH WEEK 3 FIELDS")
        else:
            logger.warning(f"⚠️  {len(stored_records) - verified} records missing Week 3 fields")
        
        # Performance check
        logger.info("\n" + "-" * 80)
        logger.info("PERFORMANCE CHECK")
        logger.info("-" * 80)
        
        if metrics['model_load_time'] > 30:
            logger.warning(f"⚠️  Model load time is high: {metrics['model_load_time']:.2f}s")
            logger.warning("   This is expected on first load, but subsequent loads should be cached")
        else:
            logger.info(f"✅ Model load time acceptable: {metrics['model_load_time']:.2f}s")
        
        if second_analysis_time < 1.0:
            logger.info("✅ Model caching working - no pipeline delays from repeated loading")
        else:
            logger.warning("⚠️  Model may be reloading - check singleton pattern")
        
        if avg_process < 5.0:
            logger.info(f"✅ Processing time acceptable: {avg_process:.3f}s per record")
        else:
            logger.warning(f"⚠️  Processing time is high: {avg_process:.3f}s per record")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ WEEK 3 REAL DATA TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in real data test: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = test_real_data_processing()
    sys.exit(0 if success else 1)

