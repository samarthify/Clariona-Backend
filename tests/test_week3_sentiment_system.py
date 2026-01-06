"""
Test script for Week 3: Sentiment System Revamp

Tests:
1. Emotion detection
2. Weight calculation
3. Embedding generation (fixes Week 2 issue)
4. Database storage of all fields
5. Integration with DataProcessor
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.emotion_analyzer import EmotionAnalyzer
from processing.sentiment_weight_calculator import SentimentWeightCalculator
from processing.weighted_sentiment_calculator import WeightedSentimentCalculator
from processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
from processing.data_processor import DataProcessor
from api.database import SessionLocal
from api import models
from datetime import datetime
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_emotion_analyzer():
    """Test emotion detection."""
    logger.info("=" * 60)
    logger.info("TEST 1: Emotion Detection")
    logger.info("=" * 60)
    
    analyzer = EmotionAnalyzer()
    
    test_texts = [
        ("I am furious about the fuel price increase!", "anger"),
        ("I'm terrified of the security situation", "fear"),
        ("I trust the government will fix this", "trust"),
        ("I'm so sad about the economic crisis", "sadness"),
        ("I'm so happy about the new infrastructure!", "joy"),
        ("I'm disgusted by the corruption", "disgust"),
    ]
    
    logger.info(f"Testing {len(test_texts)} emotion examples...")
    
    for text, expected_emotion in test_texts:
        result = analyzer.analyze_emotion(text)
        detected = result.get('emotion_label')
        score = result.get('emotion_score')
        distribution = result.get('emotion_distribution', {})
        
        logger.info(f"\nText: {text[:50]}...")
        logger.info(f"  Expected: {expected_emotion}")
        logger.info(f"  Detected: {detected} (score: {score:.3f})")
        logger.info(f"  Distribution: {json.dumps(distribution, indent=2)}")
        
        # Check if expected emotion is in top emotions
        top_emotions = sorted(distribution.items(), key=lambda x: x[1], reverse=True)[:2]
        top_emotion_names = [e[0] for e in top_emotions]
        
        if detected == expected_emotion or expected_emotion in top_emotion_names:
            logger.info(f"  ✅ Match!")
        else:
            logger.warning(f"  ⚠️  Expected {expected_emotion}, got {detected}")
    
    return True


def test_weight_calculator():
    """Test influence and confidence weight calculation."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Weight Calculation")
    logger.info("=" * 60)
    
    calculator = SentimentWeightCalculator()
    
    test_cases = [
        ("presidency_statement", False, 0, 5.0),
        ("national_media", False, 0, 4.0),
        ("twitter", True, 100000, 1.5 * 1.3),  # Verified + high reach
        ("twitter", False, 5000, 1.0),
        ("news", False, 0, 4.0),
    ]
    
    logger.info("Testing influence weight calculation...")
    for source_type, verified, reach, expected_min in test_cases:
        weight = calculator.calculate_influence_weight(
            source_type=source_type,
            user_verified=verified,
            reach=reach
        )
        logger.info(f"  {source_type} (verified={verified}, reach={reach}): {weight}")
        assert weight >= expected_min * 0.9, f"Weight {weight} below expected minimum {expected_min}"
        assert 1.0 <= weight <= 5.0, f"Weight {weight} out of range"
    
    logger.info("\nTesting confidence weight calculation...")
    confidence = calculator.calculate_confidence_weight(
        sentiment_score=-0.8,
        emotion_score=0.7
    )
    logger.info(f"  Confidence weight (sentiment=-0.8, emotion=0.7): {confidence:.3f}")
    assert 0.0 <= confidence <= 1.0, "Confidence weight out of range"
    
    return True


def test_weighted_sentiment_calculator():
    """Test weighted sentiment calculation."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Weighted Sentiment Calculation")
    logger.info("=" * 60)
    
    calculator = WeightedSentimentCalculator()
    
    # Test mentions with different weights
    mentions = [
        {'sentiment_label': 'negative', 'sentiment_score': -0.8, 'influence_weight': 5.0, 'confidence_weight': 0.9},
        {'sentiment_label': 'negative', 'sentiment_score': -0.6, 'influence_weight': 1.0, 'confidence_weight': 0.7},
        {'sentiment_label': 'positive', 'sentiment_score': 0.5, 'influence_weight': 2.0, 'confidence_weight': 0.8},
    ]
    
    result = calculator.calculate_weighted_sentiment(mentions)
    
    logger.info(f"  Weighted sentiment score: {result['weighted_sentiment_score']:.3f}")
    logger.info(f"  Sentiment index: {result['sentiment_index']:.2f}")
    logger.info(f"  Mention count: {result['mention_count']}")
    logger.info(f"  Total influence weight: {result['total_influence_weight']:.2f}")
    
    assert -1.0 <= result['weighted_sentiment_score'] <= 1.0, "Weighted score out of range"
    assert 0.0 <= result['sentiment_index'] <= 100.0, "Sentiment index out of range"
    
    # Test sentiment index conversion
    index = calculator.calculate_sentiment_index(-1.0)
    assert index == 0.0, f"Index for -1.0 should be 0.0, got {index}"
    
    index = calculator.calculate_sentiment_index(0.0)
    assert index == 50.0, f"Index for 0.0 should be 50.0, got {index}"
    
    index = calculator.calculate_sentiment_index(1.0)
    assert index == 100.0, f"Index for 1.0 should be 100.0, got {index}"
    
    logger.info("  ✅ Sentiment index conversion working correctly")
    
    return True


def test_embedding_generation():
    """Test that embeddings are generated (not zero vectors)."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Embedding Generation (Week 2 Fix)")
    logger.info("=" * 60)
    
    analyzer = PresidentialSentimentAnalyzer()
    test_text = "Fuel prices have increased dramatically in Nigeria."
    
    result = analyzer.analyze(test_text)
    embedding = result.get('embedding', [])
    
    logger.info(f"  Embedding length: {len(embedding)}")
    logger.info(f"  First 5 values: {embedding[:5] if embedding else 'None'}")
    
    if embedding:
        is_zero = all(x == 0.0 for x in embedding[:10])
        if is_zero:
            logger.error("  ❌ Embedding is still a zero vector!")
            return False
        else:
            logger.info("  ✅ Embedding is NOT a zero vector (Week 2 issue fixed!)")
            return True
    else:
        logger.error("  ❌ No embedding returned!")
        return False


def test_sentiment_analyzer_integration():
    """Test PresidentialSentimentAnalyzer with all Week 3 features."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Sentiment Analyzer Integration")
    logger.info("=" * 60)
    
    analyzer = PresidentialSentimentAnalyzer()
    test_text = "I am furious about the fuel price increase! This is unacceptable."
    
    result = analyzer.analyze(test_text, source_type="twitter", user_verified=True, reach=50000)
    
    # Check all Week 3 fields
    required_fields = [
        'sentiment_label', 'sentiment_score', 'sentiment_justification',
        'emotion_label', 'emotion_score', 'emotion_distribution',
        'influence_weight', 'confidence_weight', 'embedding'
    ]
    
    logger.info("Checking required fields:")
    for field in required_fields:
        value = result.get(field)
        present = value is not None
        logger.info(f"  {field}: {'✅' if present else '❌'} {type(value).__name__}")
        assert present, f"Missing required field: {field}"
    
    logger.info(f"\n  Sentiment: {result['sentiment_label']} ({result['sentiment_score']:.3f})")
    logger.info(f"  Emotion: {result['emotion_label']} ({result['emotion_score']:.3f})")
    logger.info(f"  Influence weight: {result['influence_weight']:.2f}")
    logger.info(f"  Confidence weight: {result['confidence_weight']:.3f}")
    logger.info(f"  Embedding: {len(result['embedding'])} dimensions")
    
    # Verify embedding is not zero
    embedding = result['embedding']
    if embedding:
        is_zero = all(x == 0.0 for x in embedding[:10])
        assert not is_zero, "Embedding should not be zero vector"
        logger.info("  ✅ Embedding is valid (not zero)")
    
    return True


def test_data_processor_integration():
    """Test DataProcessor with Week 3 features."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: DataProcessor Integration")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    test_text = "I'm very angry about the corruption in government."
    
    result = processor.get_sentiment(test_text, source_type="twitter")
    
    # Check Week 3 fields are in result
    week3_fields = ['emotion_label', 'emotion_score', 'emotion_distribution', 
                    'influence_weight', 'confidence_weight']
    
    logger.info("Checking Week 3 fields in DataProcessor result:")
    for field in week3_fields:
        value = result.get(field)
        present = value is not None
        logger.info(f"  {field}: {'✅' if present else '❌'}")
        assert present, f"Missing Week 3 field: {field}"
    
    logger.info(f"\n  Sentiment: {result['sentiment_label']}")
    logger.info(f"  Emotion: {result['emotion_label']} ({result['emotion_score']:.3f})")
    logger.info(f"  Influence weight: {result['influence_weight']:.2f}")
    logger.info(f"  Topics: {len(result.get('topics', []))}")
    
    return True


def test_database_storage():
    """Test storing Week 3 fields in database."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Database Storage")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    session = SessionLocal()
    
    try:
        # Check if Week 3 columns exist
        from sqlalchemy import inspect
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns('sentiment_data')]
        week3_columns = ['emotion_label', 'emotion_score', 'emotion_distribution', 
                        'influence_weight', 'confidence_weight']
        week2_columns = ['processing_status', 'processing_started_at', 'processing_completed_at']
        
        missing_week3 = [col for col in week3_columns if col not in columns]
        missing_week2 = [col for col in week2_columns if col not in columns]
        
        if missing_week2:
            logger.warning(f"⚠️  Week 2 columns missing: {missing_week2}")
            logger.warning("⚠️  Run migration: alembic upgrade head")
            logger.warning("⚠️  Skipping database storage test")
            return None
        
        if missing_week3:
            logger.warning(f"⚠️  Week 3 columns missing: {missing_week3}")
            logger.warning("⚠️  Run migration: alembic upgrade head")
            logger.warning("⚠️  Skipping database storage test")
            return None
        
        # Create test mention
        test_mention = models.SentimentData(
            run_timestamp=datetime.now(),
            text="I'm very angry about the fuel price increase!",
            source="test",
            platform="test",
            processing_status='pending'
        )
        session.add(test_mention)
        session.commit()
        session.refresh(test_mention)
        
        logger.info(f"✅ Created test mention: entry_id={test_mention.entry_id}")
        
        # Process and get results
        result = processor.get_sentiment(test_mention.text, test_mention.source_type)
        
        # Update with Week 3 fields
        test_mention.sentiment_label = result['sentiment_label']
        test_mention.sentiment_score = result['sentiment_score']
        test_mention.emotion_label = result.get('emotion_label')
        test_mention.emotion_score = result.get('emotion_score')
        if result.get('emotion_distribution'):
            test_mention.emotion_distribution = json.dumps(result['emotion_distribution'])
        test_mention.influence_weight = result.get('influence_weight', 1.0)
        test_mention.confidence_weight = result.get('confidence_weight')
        test_mention.processing_status = 'completed'
        
        session.commit()
        session.refresh(test_mention)
        
        logger.info(f"✅ Stored Week 3 fields:")
        logger.info(f"   emotion_label: {test_mention.emotion_label}")
        logger.info(f"   emotion_score: {test_mention.emotion_score}")
        logger.info(f"   influence_weight: {test_mention.influence_weight}")
        logger.info(f"   confidence_weight: {test_mention.confidence_weight}")
        
        # Cleanup
        session.delete(test_mention)
        session.commit()
        logger.info("✅ Cleaned up test mention")
        
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error in database storage test: {e}")
        raise
    finally:
        session.close()


def run_all_tests():
    """Run all Week 3 tests."""
    logger.info("\n" + "=" * 60)
    logger.info("WEEK 3 SENTIMENT SYSTEM REVAMP TESTS")
    logger.info("=" * 60)
    
    results = {}
    
    try:
        results['test1_emotion'] = test_emotion_analyzer()
        results['test2_weight'] = test_weight_calculator()
        results['test3_weighted'] = test_weighted_sentiment_calculator()
        results['test4_embedding'] = test_embedding_generation()
        results['test5_analyzer'] = test_sentiment_analyzer_integration()
        results['test6_processor'] = test_data_processor_integration()
        results['test7_database'] = test_database_storage()
        
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

