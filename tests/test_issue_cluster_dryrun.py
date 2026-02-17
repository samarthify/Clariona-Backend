"""
Dry-run script to exercise DBSCAN clustering, persistence, and promotion.

Steps:
1) Persist clusters (detect_issues per topic) with promotion mode enabled.
2) Promote top-N clusters per topic to issues.

Note: ensure env/config sets processing.issue.promotion.enabled=true
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.processing.data_processor import DataProcessor
from src.processing.issue_detection_engine import IssueDetectionEngine
from src.api.database import SessionLocal
from src.api.models import MentionTopic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    session = SessionLocal()
    try:
        # Topics with mentions
        topic_keys = [t[0] for t in session.query(MentionTopic.topic_key).distinct().all()]
        if not topic_keys:
            logger.info("No topics with mentions found.")
            return

        logger.info(f"Found {len(topic_keys)} topics with mentions")

        processor = DataProcessor()
        engine: IssueDetectionEngine = processor.issue_detection_engine
        if not engine:
            logger.error("IssueDetectionEngine not initialized.")
            return

        # Ensure promotion mode is on
        logger.info(f"Promotion enabled? {engine.promotion_enabled}")

        # Persist clusters (no issue creation when promotion_enabled=True)
        for topic_key in topic_keys:
            logger.info(f"Persisting clusters for topic: {topic_key}")
            engine.detect_issues(topic_key, limit=None)

        # Promote clusters
        total_promoted = 0
        for topic_key in topic_keys:
            promoted = engine.promote_clusters_for_topic(topic_key)
            if promoted:
                logger.info(f"Promoted {len(promoted)} clusters to issues for topic {topic_key}")
                total_promoted += len(promoted)

        logger.info(f"Dry-run complete. Total promoted clusters: {total_promoted}")

    except Exception as e:
        logger.exception(f"Error in dry-run: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

