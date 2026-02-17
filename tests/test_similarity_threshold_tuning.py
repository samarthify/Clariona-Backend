"""
Test script for tuning similarity threshold in issue detection.

This script tests different similarity thresholds and shows results
to help determine the optimal threshold for issue clustering.
"""

import sys
from pathlib import Path
import time
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.processing.issue_detection_engine import IssueDetectionEngine
from src.processing.data_processor import DataProcessor
from src.api.database import SessionLocal
from src.api.models import MentionTopic, TopicIssue, IssueMention, TopicIssueLink
from sqlalchemy import func
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_existing_issues(session, topic_key: str = None):
    """Clean up existing issues for a topic or all topics."""
    try:
        if topic_key:
            # Clean up issues for specific topic
            issues = session.query(TopicIssue).filter(
                TopicIssue.topic_key == topic_key
            ).all()
            count = len(issues)
            
            # Delete issue mentions first (foreign key constraint)
            for issue in issues:
                session.query(IssueMention).filter(
                    IssueMention.issue_id == issue.id
                ).delete()
                session.query(TopicIssueLink).filter(
                    TopicIssueLink.issue_id == issue.id
                ).delete()
            
            # Delete issues
            session.query(TopicIssue).filter(
                TopicIssue.topic_key == topic_key
            ).delete()
            
            session.commit()
            logger.info(f"Cleaned up {count} existing issues for topic: {topic_key}")
        else:
            # Clean up all issues
            all_issues = session.query(TopicIssue).all()
            count = len(all_issues)
            
            # Delete issue mentions and links first
            for issue in all_issues:
                session.query(IssueMention).filter(
                    IssueMention.issue_id == issue.id
                ).delete()
                session.query(TopicIssueLink).filter(
                    TopicIssueLink.issue_id == issue.id
                ).delete()
            
            # Delete all issues
            session.query(TopicIssue).delete()
            session.commit()
            logger.info(f"Cleaned up {count} existing issues (all topics)")
            
    except Exception as e:
        session.rollback()
        logger.error(f"Error cleaning up issues: {e}", exc_info=True)
        raise


def get_topics_with_mentions(session, min_mentions: int = 100) -> List[str]:
    """Get topics that have enough mentions for testing."""
    # Get topics with mention counts
    topic_counts = (
        session.query(
            MentionTopic.topic_key,
            func.count(MentionTopic.mention_id).label('mention_count')
        )
        .group_by(MentionTopic.topic_key)
        .having(func.count(MentionTopic.mention_id) >= min_mentions)
        .order_by(func.count(MentionTopic.mention_id).desc())
        .all()
    )
    
    topics = [t[0] for t in topic_counts]
    logger.info(f"Found {len(topics)} topics with {min_mentions}+ mentions")
    
    for topic_key, count in topic_counts[:10]:  # Show top 10
        logger.info(f"  - {topic_key}: {count} mentions")
    
    return topics


def test_similarity_threshold(
    topic_key: str,
    similarity_threshold: float,
    limit: int = None
) -> Dict[str, Any]:
    """
    Test issue detection with a specific similarity threshold.
    
    Args:
        topic_key: Topic to test
        similarity_threshold: Similarity threshold to test (0.0-1.0)
        limit: Optional limit on mentions to process
        
    Returns:
        Dictionary with test results
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing similarity threshold: {similarity_threshold:.3f} for topic: {topic_key}")
    logger.info(f"{'='*60}")
    
    # Create engine with specific threshold
    engine = IssueDetectionEngine(
        similarity_threshold=similarity_threshold,
        min_cluster_size=500,  # Your configured value
        time_window_hours=168  # Your configured value (1 week)
    )
    
    start_time = time.time()
    
    try:
        # Run issue detection
        issues = engine.detect_issues(topic_key, limit=limit)
        elapsed_time = time.time() - start_time
        
        # Get cluster statistics
        session = SessionLocal()
        try:
            # Count total mentions processed
            total_mentions = (
                session.query(func.count(MentionTopic.mention_id))
                .filter(MentionTopic.topic_key == topic_key)
                .scalar()
            )
            
            # Count mentions in issues
            mentions_in_issues = (
                session.query(func.count(IssueMention.mention_id))
                .join(TopicIssue, IssueMention.issue_id == TopicIssue.id)
                .filter(TopicIssue.topic_key == topic_key)
                .scalar()
            )
            
            # Get issue details
            issue_details = []
            for issue in issues[:5]:  # First 5 issues
                issue_id = issue.get('issue_id')
                if issue_id:
                    issue_obj = session.query(TopicIssue).filter(
                        TopicIssue.id == issue_id
                    ).first()
                    if issue_obj:
                        issue_details.append({
                            'slug': issue_obj.issue_slug,
                            'mentions': issue_obj.mention_count,
                            'state': issue_obj.state,
                            'priority': issue_obj.priority_score
                        })
        finally:
            session.close()
        
        result = {
            'similarity_threshold': similarity_threshold,
            'topic_key': topic_key,
            'issues_created': len(issues),
            'total_mentions': total_mentions,
            'mentions_in_issues': mentions_in_issues,
            'coverage_percent': (mentions_in_issues / total_mentions * 100) if total_mentions > 0 else 0,
            'elapsed_time': elapsed_time,
            'issue_details': issue_details
        }
        
        logger.info(f"\nResults for threshold {similarity_threshold:.3f}:")
        logger.info(f"  Issues created/updated: {len(issues)}")
        logger.info(f"  Total mentions: {total_mentions}")
        logger.info(f"  Mentions in issues: {mentions_in_issues}")
        logger.info(f"  Coverage: {result['coverage_percent']:.1f}%")
        logger.info(f"  Time: {elapsed_time:.2f}s")
        
        if issue_details:
            logger.info(f"\n  Top issues:")
            for detail in issue_details[:3]:
                logger.info(f"    - {detail['slug']}: {detail['mentions']} mentions, "
                          f"state={detail['state']}, priority={detail['priority']:.1f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing threshold {similarity_threshold:.3f}: {e}", exc_info=True)
        return {
            'similarity_threshold': similarity_threshold,
            'topic_key': topic_key,
            'error': str(e),
            'issues_created': 0
        }


def compare_thresholds(
    topic_key: str,
    thresholds: List[float],
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Compare multiple similarity thresholds.
    
    Args:
        topic_key: Topic to test
        thresholds: List of similarity thresholds to test
        limit: Optional limit on mentions to process
        
    Returns:
        List of results for each threshold
    """
    logger.info(f"\n{'#'*60}")
    logger.info(f"Comparing similarity thresholds for topic: {topic_key}")
    logger.info(f"Thresholds to test: {thresholds}")
    logger.info(f"{'#'*60}\n")
    
    results = []
    
    # Clean up existing issues for this topic before testing
    session = SessionLocal()
    try:
        cleanup_existing_issues(session, topic_key)
    finally:
        session.close()
    
    for threshold in thresholds:
        result = test_similarity_threshold(topic_key, threshold, limit)
        results.append(result)
        
        # Small delay between tests
        time.sleep(1)
    
    return results


def print_comparison_summary(results: List[Dict[str, Any]]):
    """Print a summary comparison of all thresholds."""
    logger.info(f"\n{'='*80}")
    logger.info("SIMILARITY THRESHOLD COMPARISON SUMMARY")
    logger.info(f"{'='*80}\n")
    
    logger.info(f"{'Threshold':<12} {'Issues':<8} {'Coverage %':<12} {'Time (s)':<10} {'Status'}")
    logger.info("-" * 80)
    
    for result in results:
        threshold = result.get('similarity_threshold', 0)
        issues = result.get('issues_created', 0)
        coverage = result.get('coverage_percent', 0)
        elapsed = result.get('elapsed_time', 0)
        error = result.get('error')
        
        status = "ERROR" if error else "OK"
        
        logger.info(f"{threshold:<12.3f} {issues:<8} {coverage:<12.1f} {elapsed:<10.2f} {status}")
    
    logger.info(f"\n{'='*80}\n")
    
    # Recommendations
    valid_results = [r for r in results if 'error' not in r]
    if valid_results:
        # Find threshold with best balance (good coverage, reasonable number of issues)
        best_balance = None
        best_score = -1
        
        for result in valid_results:
            coverage = result.get('coverage_percent', 0)
            issues = result.get('issues_created', 0)
            # Score: coverage * log(issues + 1) to balance both
            import math
            score = coverage * math.log(issues + 1)
            
            if score > best_score:
                best_score = score
                best_balance = result
        
        if best_balance:
            logger.info(f"💡 Recommended threshold: {best_balance['similarity_threshold']:.3f}")
            logger.info(f"   - Creates {best_balance['issues_created']} issues")
            logger.info(f"   - Covers {best_balance['coverage_percent']:.1f}% of mentions")
            logger.info(f"   - Balance score: {best_score:.2f}\n")


def main():
    """Main function to run similarity threshold tuning."""
    logger.info("="*80)
    logger.info("ISSUE DETECTION - SIMILARITY THRESHOLD TUNING")
    logger.info("="*80)
    
    session = SessionLocal()
    
    try:
        # Clean up all existing issues first
        logger.info("\nCleaning up all existing issues...")
        cleanup_existing_issues(session, topic_key=None)
        
        # Get all topics with mentions (not just those with 500+)
        # We'll process all topics to get a full picture
        topics = get_topics_with_mentions(session, min_mentions=1)
        
        if not topics:
            logger.error("No topics found with mentions.")
            return
        
        logger.info(f"\nFound {len(topics)} topics with mentions")
        logger.info("Processing all topics to get a comprehensive view...\n")
        
        # Use first topic for threshold comparison (or process all)
        test_topic = topics[0]
        logger.info(f"Using topic: {test_topic} for threshold comparison\n")
        
        # Test different similarity thresholds
        # Focused range for faster testing
        thresholds = [0.70, 0.75, 0.80]
        
        # Compare thresholds
        results = compare_thresholds(
            topic_key=test_topic,
            thresholds=thresholds,
            limit=None  # Process all mentions
        )
        
        # Print summary
        print_comparison_summary(results)
        
        # Now run on all topics with the default threshold to see overall results
        logger.info("\n" + "="*80)
        logger.info("Running issue detection on ALL topics with threshold 0.75")
        logger.info("="*80 + "\n")
        
        processor = DataProcessor()
        all_results = processor.detect_issues_for_all_topics(limit_per_topic=None)
        
        total_issues = sum(len(issues) for issues in all_results.values())
        logger.info(f"\n✅ Total issues created/updated across all topics: {total_issues}")
        
        for topic_key, issues in all_results.items():
            if issues:
                logger.info(f"  {topic_key}: {len(issues)} issues")
        
        logger.info("\n✅ Similarity threshold tuning complete!")
        logger.info("\nTo use a specific threshold, update your config:")
        logger.info('  "processing.issue.clustering.similarity_threshold": 0.75')
        logger.info("\nOr via environment variable:")
        logger.info("  CONFIG__PROCESSING__ISSUE__CLUSTERING__SIMILARITY_THRESHOLD=0.75")
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
