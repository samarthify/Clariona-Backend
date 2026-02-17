"""
Standalone test script for issue detection as a polling service.

This script runs issue detection independently to test the multi-cluster support
and verify the polling logic works correctly.
"""

import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func

from src.api.database import SessionLocal
from src.processing.data_processor import DataProcessor
from src.api.models import MentionTopic, ProcessingCluster, ClusterMention, TopicIssue, IssueMention
from src.config.config_manager import ConfigManager
from src.config.logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def get_topics_with_mentions(session, min_mentions: int = 1):
    """Get topics that have mentions."""
    topics = (
        session.query(MentionTopic.topic_key)
        .group_by(MentionTopic.topic_key)
        .having(func.count(MentionTopic.mention_id) >= min_mentions)
        .all()
    )
    return [t[0] for t in topics]


def print_cluster_stats(session, topic_key: str):
    """Print statistics about clusters for a topic."""
    clusters = (
        session.query(ProcessingCluster)
        .filter(ProcessingCluster.topic_key == topic_key)
        .all()
    )
    
    logger.info(f"\n=== Cluster Stats for {topic_key} ===")
    logger.info(f"Total clusters: {len(clusters)}")
    
    for cluster in clusters:
        mention_count = (
            session.query(ClusterMention)
            .filter(ClusterMention.cluster_id == cluster.id)
            .count()
        )
        logger.info(
            f"  Cluster {cluster.id}: size={cluster.size}, "
            f"density={cluster.density_score:.3f if cluster.density_score else None}, "
            f"status={cluster.status}, mentions={mention_count}"
        )


def print_issue_stats(session, topic_key: str):
    """Print statistics about issues for a topic."""
    issues = (
        session.query(TopicIssue)
        .filter(TopicIssue.topic_key == topic_key)
        .all()
    )
    
    logger.info(f"\n=== Issue Stats for {topic_key} ===")
    logger.info(f"Total issues: {len(issues)}")
    
    for issue in issues:
        mention_count = (
            session.query(IssueMention)
            .filter(IssueMention.issue_id == issue.id)
            .count()
        )
        logger.info(
            f"  Issue {issue.id}: title={issue.title[:50] if issue.title else 'N/A'}, "
            f"mentions={mention_count}, priority={issue.priority_score}"
        )


def check_multi_cluster_mentions(session, topic_key: str):
    """Check for mentions that belong to multiple clusters."""
    multi_cluster_mentions = (
        session.query(ClusterMention.mention_id, func.count(ClusterMention.cluster_id))
        .join(ProcessingCluster, ClusterMention.cluster_id == ProcessingCluster.id)
        .filter(ProcessingCluster.topic_key == topic_key)
        .group_by(ClusterMention.mention_id)
        .having(func.count(ClusterMention.cluster_id) > 1)
        .all()
    )
    
    if multi_cluster_mentions:
        logger.info(f"\n=== Multi-Cluster Mentions for {topic_key} ===")
        logger.info(f"Found {len(multi_cluster_mentions)} mentions in multiple clusters:")
        for mention_id, cluster_count in multi_cluster_mentions[:10]:  # Show first 10
            clusters = (
                session.query(ClusterMention.cluster_id)
                .filter(ClusterMention.mention_id == mention_id)
                .all()
            )
            cluster_ids = [str(c[0]) for c in clusters]
            logger.info(f"  Mention {mention_id}: in {cluster_count} clusters: {', '.join(cluster_ids[:3])}...")
    else:
        logger.info(f"\n=== Multi-Cluster Mentions for {topic_key} ===")
        logger.info("No mentions found in multiple clusters yet.")


async def run_issue_detection_cycle(processor: DataProcessor, topic_key: str = None):
    """Run one cycle of issue detection."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Issue Detection Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}")
    
    try:
        if topic_key:
            logger.info(f"Running issue detection for topic: {topic_key}")
            processor.detect_issues_for_topic(topic_key)
            
            # Check promotion if enabled
            config = ConfigManager()
            if config.get_bool("processing.issue.promotion.enabled", False):
                logger.info(f"Running promotion for topic: {topic_key}")
                processor.issue_detection_engine.promote_clusters_for_topic(topic_key)
        else:
            logger.info("Running issue detection for all topics")
            processor.detect_issues_for_all_topics()
            
            # Check promotion if enabled
            config = ConfigManager()
            if config.get_bool("processing.issue.promotion.enabled", False):
                logger.info("Running promotion for all topics")
                session = SessionLocal()
                try:
                    topics = get_topics_with_mentions(session, min_mentions=1)
                    for topic in topics:
                        processor.issue_detection_engine.promote_clusters_for_topic(topic)
                finally:
                    session.close()
        
        logger.info("Issue detection cycle completed successfully")
        
    except Exception as e:
        logger.error(f"Error in issue detection cycle: {e}", exc_info=True)


async def poller_loop(processor: DataProcessor, topic_key: str = None, interval: int = 60):
    """Run issue detection in a polling loop."""
    logger.info(f"Starting issue detection poller (interval={interval}s)")
    logger.info(f"Topic filter: {topic_key if topic_key else 'ALL TOPICS'}")
    
    iteration = 0
    while True:
        iteration += 1
        logger.info(f"\n{'#'*60}")
        logger.info(f"Poller Iteration #{iteration}")
        logger.info(f"{'#'*60}")
        
        await run_issue_detection_cycle(processor, topic_key)
        
        # Print stats after each cycle
        session = SessionLocal()
        try:
            if topic_key:
                print_cluster_stats(session, topic_key)
                print_issue_stats(session, topic_key)
                check_multi_cluster_mentions(session, topic_key)
            else:
                # Show stats for first few topics
                topics = (
                    session.query(MentionTopic.topic_key)
                    .group_by(MentionTopic.topic_key)
                    .having(func.count(MentionTopic.mention_id) >= 10)
                    .limit(3)
                    .all()
                )
                for topic in topics:
                    print_cluster_stats(session, topic[0])
                    print_issue_stats(session, topic[0])
                    check_multi_cluster_mentions(session, topic[0])
        finally:
            session.close()
        
        logger.info(f"\nSleeping for {interval} seconds before next cycle...")
        await asyncio.sleep(interval)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test issue detection as a poller")
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Specific topic key to process (default: all topics)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Polling interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't poll)"
    )
    
    args = parser.parse_args()
    
    logger.info("Initializing Issue Detection Poller Test")
    logger.info(f"Topic: {args.topic or 'ALL'}")
    logger.info(f"Interval: {args.interval}s")
    logger.info(f"Mode: {'Single run' if args.once else 'Polling loop'}")
    
    # Initialize processor
    processor = DataProcessor()
    
    if args.once:
        # Run once
        asyncio.run(run_issue_detection_cycle(processor, args.topic))
        
        # Print final stats
        session = SessionLocal()
        try:
            if args.topic:
                print_cluster_stats(session, args.topic)
                print_issue_stats(session, args.topic)
                check_multi_cluster_mentions(session, args.topic)
            else:
                topics = (
                    session.query(MentionTopic.topic_key)
                    .group_by(MentionTopic.topic_key)
                    .having(func.count(MentionTopic.mention_id) >= 10)
                    .limit(5)
                    .all()
                )
                for topic in topics:
                    print_cluster_stats(session, topic[0])
                    print_issue_stats(session, topic[0])
                    check_multi_cluster_mentions(session, topic[0])
        finally:
            session.close()
    else:
        # Run polling loop
        try:
            asyncio.run(poller_loop(processor, args.topic, args.interval))
        except KeyboardInterrupt:
            logger.info("\nPoller stopped by user")


if __name__ == "__main__":
    main()
