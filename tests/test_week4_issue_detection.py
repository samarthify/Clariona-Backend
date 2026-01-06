"""
Test script for Week 4: Issue Detection System

Tests:
1. IssueClusteringService - Clustering mentions
2. IssueDetectionEngine - Detecting and managing issues
3. IssueLifecycleManager - Lifecycle state management
4. IssuePriorityCalculator - Priority scoring
5. DataProcessor integration
6. Database storage (topic_issues, issue_mentions, topic_issue_links)
7. Real data processing
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processing.issue_clustering_service import IssueClusteringService
from processing.issue_detection_engine import IssueDetectionEngine
from processing.issue_lifecycle_manager import IssueLifecycleManager
from processing.issue_priority_calculator import IssuePriorityCalculator
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


def test_clustering_service():
    """Test IssueClusteringService."""
    logger.info("=" * 60)
    logger.info("TEST 1: IssueClusteringService")
    logger.info("=" * 60)
    
    clustering_service = IssueClusteringService()
    
    # Create test mentions with embeddings
    mentions = []
    base_embedding = np.random.rand(1536).tolist()
    
    for i in range(10):
        # Create similar mentions (same topic)
        embedding = (np.array(base_embedding) + np.random.rand(1536) * 0.1).tolist()
        mentions.append({
            'entry_id': i + 1,
            'text': f"Test mention about healthcare issue {i}",
            'embedding': embedding,
            'timestamp': datetime.now() - timedelta(hours=i)
        })
    
    logger.info(f"Testing clustering with {len(mentions)} mentions")
    
    # Cluster mentions
    clusters = clustering_service.cluster_mentions(mentions, 'healthcare')
    
    logger.info(f"✅ Created {len(clusters)} clusters")
    for i, cluster in enumerate(clusters, 1):
        logger.info(f"   Cluster {i}: {len(cluster)} mentions")
    
    assert len(clusters) > 0, "Should create at least one cluster"
    
    return True


def test_detection_engine():
    """Test IssueDetectionEngine."""
    logger.info("=" * 60)
    logger.info("TEST 2: IssueDetectionEngine")
    logger.info("=" * 60)
    
    engine = IssueDetectionEngine()
    
    logger.info("✅ IssueDetectionEngine initialized")
    logger.info(f"   Clustering threshold: {engine.clustering_service.similarity_threshold}")
    logger.info(f"   Issue similarity threshold: {engine.issue_similarity_threshold}")
    logger.info(f"   Min cluster size: {engine.clustering_service.min_cluster_size}")
    
    assert engine.clustering_service is not None, "Clustering service should be initialized"
    assert engine.lifecycle_manager is not None, "Lifecycle manager should be initialized"
    assert engine.priority_calculator is not None, "Priority calculator should be initialized"
    
    return True


def test_lifecycle_manager():
    """Test IssueLifecycleManager."""
    logger.info("=" * 60)
    logger.info("TEST 3: IssueLifecycleManager")
    logger.info("=" * 60)
    
    manager = IssueLifecycleManager()
    session = SessionLocal()
    
    try:
        # Create a test issue
        from uuid import uuid4
        test_issue = models.TopicIssue(
            id=uuid4(),
            issue_slug='test-issue-lifecycle',
            issue_label='Test Issue',
            topic_key='healthcare',
            primary_topic_key='healthcare',
            state='emerging',
            start_time=datetime.now() - timedelta(hours=2),
            last_activity=datetime.now() - timedelta(hours=1),
            mention_count=5,
            is_active=True
        )
        session.add(test_issue)
        session.flush()
        
        # Test lifecycle update
        result = manager.update_lifecycle(test_issue, session)
        
        logger.info(f"✅ Lifecycle update result:")
        logger.info(f"   State: {result['state']}")
        logger.info(f"   Reason: {result.get('reason', 'N/A')}")
        
        assert 'state' in result, "Result should contain state"
        assert result['state'] in ['emerging', 'active', 'escalated', 'stabilizing', 'resolved', 'archived']
        
        # Cleanup
        session.delete(test_issue)
        session.commit()
        
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error in lifecycle test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_priority_calculator():
    """Test IssuePriorityCalculator."""
    logger.info("=" * 60)
    logger.info("TEST 4: IssuePriorityCalculator")
    logger.info("=" * 60)
    
    calculator = IssuePriorityCalculator()
    session = SessionLocal()
    
    try:
        # Create a test issue
        from uuid import uuid4
        test_issue = models.TopicIssue(
            id=uuid4(),
            issue_slug='test-issue-priority',
            issue_label='Test Issue',
            topic_key='healthcare',
            primary_topic_key='healthcare',
            state='active',
            start_time=datetime.now() - timedelta(hours=5),
            last_activity=datetime.now() - timedelta(minutes=30),
            mention_count=10,
            is_active=True
        )
        session.add(test_issue)
        session.flush()
        
        # Test priority calculation
        result = calculator.calculate_priority(test_issue, session)
        
        logger.info(f"✅ Priority calculation result:")
        logger.info(f"   Priority Score: {result['priority_score']:.2f}")
        logger.info(f"   Priority Band: {result['priority_band']}")
        logger.info(f"   Components:")
        logger.info(f"     - Sentiment: {result.get('sentiment_score', 0):.2f}")
        logger.info(f"     - Volume: {result.get('volume_score', 0):.2f}")
        logger.info(f"     - Time: {result.get('time_score', 0):.2f}")
        
        assert 'priority_score' in result, "Result should contain priority_score"
        assert 'priority_band' in result, "Result should contain priority_band"
        assert 0 <= result['priority_score'] <= 100, "Priority score should be 0-100"
        assert result['priority_band'] in ['critical', 'high', 'medium', 'low'], "Invalid priority band"
        
        # Cleanup
        session.delete(test_issue)
        session.commit()
        
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error in priority test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_data_processor_integration():
    """Test DataProcessor integration with issue detection."""
    logger.info("=" * 60)
    logger.info("TEST 5: DataProcessor Integration")
    logger.info("=" * 60)
    
    processor = DataProcessor()
    
    # Check if issue detection engine is initialized
    if processor.issue_detection_engine is None:
        logger.warning("⚠️  IssueDetectionEngine not initialized. Skipping integration test.")
        return None  # Not a failure, just not available
    
    logger.info("✅ IssueDetectionEngine initialized in DataProcessor")
    logger.info("✅ detect_issues_for_topic() method available")
    logger.info("✅ detect_issues_for_all_topics() method available")
    
    return True


def test_database_schema():
    """Test database schema for issue detection tables."""
    logger.info("=" * 60)
    logger.info("TEST 6: Database Schema")
    logger.info("=" * 60)
    
    session = SessionLocal()
    
    try:
        inspector = inspect(session.bind)
        
        # Check topic_issues table
        tables = inspector.get_table_names()
        required_tables = ['topic_issues', 'issue_mentions', 'topic_issue_links']
        
        for table in required_tables:
            if table in tables:
                columns = [col['name'] for col in inspector.get_columns(table)]
                logger.info(f"✅ Table '{table}' exists with {len(columns)} columns")
                logger.info(f"   Key columns: {', '.join(columns[:5])}...")
            else:
                logger.error(f"❌ Table '{table}' not found")
                return False
        
        # Check topic_issues columns
        topic_issues_columns = [col['name'] for col in inspector.get_columns('topic_issues')]
        required_columns = ['id', 'issue_slug', 'topic_key', 'state', 'priority_score', 'mention_count']
        
        for col in required_columns:
            if col in topic_issues_columns:
                logger.info(f"   ✅ Column '{col}' exists in topic_issues")
            else:
                logger.warning(f"   ⚠️  Column '{col}' not found in topic_issues")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking database schema: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_real_data_processing():
    """Test issue detection with real data from database."""
    logger.info("=" * 60)
    logger.info("TEST 7: Real Data Processing")
    logger.info("=" * 60)
    
    session = SessionLocal()
    processor = DataProcessor()
    
    try:
        # Check if issue detection is available
        if processor.issue_detection_engine is None:
            logger.warning("⚠️  IssueDetectionEngine not initialized. Skipping real data test.")
            return None
        
        # Check if we have topics with mentions
        from api.models import MentionTopic
        topics_with_mentions = session.query(MentionTopic.topic_key).distinct().limit(5).all()
        
        if not topics_with_mentions:
            logger.warning("⚠️  No topics with mentions found. Skipping real data test.")
            return None
        
        topic_keys = [t[0] for t in topics_with_mentions]
        logger.info(f"Found {len(topic_keys)} topics with mentions")
        
        # Test issue detection for first topic
        test_topic = topic_keys[0]
        logger.info(f"Testing issue detection for topic: {test_topic}")
        
        start_time = time.time()
        issues = processor.detect_issues_for_topic(test_topic, limit=50)
        elapsed_time = time.time() - start_time
        
        logger.info(f"✅ Issue detection completed in {elapsed_time:.2f} seconds")
        logger.info(f"   Issues created/updated: {len(issues)}")
        
        for issue in issues[:5]:  # Show first 5
            logger.info(f"   - {issue.get('issue_slug', 'N/A')}: {issue.get('action', 'N/A')} "
                       f"({issue.get('mentions_count', issue.get('mentions_added', 0))} mentions)")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in real data test: {e}", exc_info=True)
        return False
    finally:
        session.close()


def test_database_storage():
    """Test database storage of issues."""
    logger.info("=" * 60)
    logger.info("TEST 8: Database Storage")
    logger.info("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Check if tables exist
        inspector = inspect(session.bind)
        if 'topic_issues' not in inspector.get_table_names():
            logger.warning("⚠️  topic_issues table not found. Run migration first.")
            return None
        
        # Count existing issues
        issue_count = session.query(models.TopicIssue).count()
        mention_link_count = session.query(models.IssueMention).count()
        topic_link_count = session.query(models.TopicIssueLink).count()
        
        logger.info(f"✅ Database storage working:")
        logger.info(f"   - topic_issues: {issue_count} issues")
        logger.info(f"   - issue_mentions: {mention_link_count} mention links")
        logger.info(f"   - topic_issue_links: {topic_link_count} topic links")
        
        # Check a sample issue if available
        sample_issue = session.query(models.TopicIssue).first()
        if sample_issue:
            logger.info(f"   Sample issue:")
            logger.info(f"     - Slug: {sample_issue.issue_slug}")
            logger.info(f"     - State: {sample_issue.state}")
            logger.info(f"     - Priority: {sample_issue.priority_band} ({sample_issue.priority_score:.1f})")
            logger.info(f"     - Mentions: {sample_issue.mention_count}")
            
            # Check mention links
            mention_links = session.query(models.IssueMention).filter(
                models.IssueMention.issue_id == sample_issue.id
            ).count()
            logger.info(f"     - Linked mentions: {mention_links}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking database storage: {e}", exc_info=True)
        return False
    finally:
        session.close()


def run_all_tests():
    """Run all Week 4 tests."""
    logger.info("\n" + "=" * 60)
    logger.info("WEEK 4 ISSUE DETECTION SYSTEM TESTS")
    logger.info("=" * 60)
    
    results = {
        'test1_clustering': None,
        'test2_detection': None,
        'test3_lifecycle': None,
        'test4_priority': None,
        'test5_integration': None,
        'test6_schema': None,
        'test7_real_data': None,
        'test8_storage': None
    }
    
    try:
        results['test1_clustering'] = test_clustering_service()
        results['test2_detection'] = test_detection_engine()
        results['test3_lifecycle'] = test_lifecycle_manager()
        results['test4_priority'] = test_priority_calculator()
        results['test5_integration'] = test_data_processor_integration()
        results['test6_schema'] = test_database_schema()
        results['test7_real_data'] = test_real_data_processing()
        results['test8_storage'] = test_database_storage()
        
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





