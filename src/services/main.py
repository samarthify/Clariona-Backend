"""
Streaming Collection Service - Main Entry Point

This module provides the unified entry point for the streaming collection service,
which runs:
1. DatasetTailerService: Tails Apify runs in real-time.
2. LocalScheduler: Schedules daily runs of local collectors.
"""

import asyncio
import logging
import os
import sys
import signal
import resource
from datetime import datetime
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from dotenv import load_dotenv

# Load environment variables from multiple locations (first found wins)
project_root = src_path.parent
env_paths = [
    project_root / 'config' / '.env',      # config/.env (where APIFY_API_TOKEN is)
    project_root / '.env',                  # project root .env
    src_path / 'collectors' / '.env',       # src/collectors/.env
]
_loaded_env_paths = []
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=False)
        _loaded_env_paths.append(str(env_path))

from sqlalchemy.orm import Session
from api.database import SessionLocal

from services.data_ingestor import DataIngestor
from services.dataset_tailer import DatasetTailerService
from services.scheduler import LocalScheduler
from services.x_stream_rules_manager import XStreamRulesManager
from services.x_stream_collector import XStreamCollector
from services.analysis_worker import AnalysisWorker
from processing.data_processor import DataProcessor
from api.models import MentionTopic, TopicIssue, IssueMention, SentimentData, SentimentEmbedding

from src.config.logging_config import setup_logging, get_logger, setup_module_logger
from logging.handlers import RotatingFileHandler

# Configure logging using centralized configuration
setup_logging()
logger = get_logger(__name__)


def setup_service_loggers(logs_dir: Path = None):
    """
    Setup separate log files for each service component.
    Logs will go to both console (via root logger) and separate files.
    
    Args:
        logs_dir: Directory for log files (defaults to logs/)
    """
    if logs_dir is None:
        logs_dir = project_root / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Define service loggers with their file names
    service_loggers = {
        'services.issue_detection': logs_dir / 'issue_detection.log',
        'services.scheduler': logs_dir / 'scheduler.log',
        'services.dataset_tailer': logs_dir / 'dataset_tailer.log',
        'services.analysis_worker': logs_dir / 'analysis_worker.log',
        'services.data_ingestor': logs_dir / 'data_ingestor.log',
        'services.x_stream_collector': logs_dir / 'x_stream_collector.log',
        'services.x_stream_rules_manager': logs_dir / 'x_stream_rules_manager.log',
    }
    
    # Setup each service logger with its own file
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    for logger_name, log_file in service_loggers.items():
        service_logger = logging.getLogger(logger_name)
        service_logger.setLevel(logging.INFO)
        
        # Add file handler for this service
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=1,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        service_logger.addHandler(file_handler)
        
        # Keep propagate=True so logs also go to console via root logger
        service_logger.propagate = True
    
    logger.info(f"Service loggers configured - logs directory: {logs_dir}")
    logger.info(f"Service log files: {', '.join([f.name for f in service_loggers.values()])}")


# Setup service-specific loggers
setup_service_loggers()

# Log which env files were loaded
if _loaded_env_paths:
    logger.info(f"Environment loaded from: {', '.join(_loaded_env_paths)}")
else:
    logger.warning("No .env files found in expected locations")


class StreamingCollectionService:
    """
    Main service that orchestrates all streaming collection components.
    """
    
    def __init__(self, user_id: str = None):
        """
        Initialize the streaming collection service.
        
        Args:
            user_id: Optional user ID to associate with collected data.
        """
        self.user_id = user_id
        self.db_session: Session = None
        self.ingestor: DataIngestor = None
        self.tailer: DatasetTailerService = None
        self.scheduler: LocalScheduler = None
        self.analysis_worker: AnalysisWorker = None
        self.analysis_task: asyncio.Task | None = None
        self.issue_task: asyncio.Task | None = None
        self.x_stream_collector: XStreamCollector | None = None
        self.x_stream_collector_task: asyncio.Task | None = None
        self.x_stream_enabled = os.getenv("X_STREAM_ENABLED", "true").lower() == "true"
        self.issue_poll_interval = float(os.getenv("ISSUE_POLL_INTERVAL_SECONDS", "300"))
        self.issue_max_workers = int(os.getenv("ISSUE_DETECTION_MAX_WORKERS", "20"))
        self._running = False
    
    async def start(self):
        """Start all streaming components."""
        logger.info("Starting Streaming Collection Service...")
        
        # Initialize database session
        self.db_session = SessionLocal()
        
        # Initialize DataIngestor
        self.ingestor = DataIngestor(self.db_session, user_id=self.user_id)
        logger.info("DataIngestor initialized.")
        
        # Initialize and start DatasetTailer
        self.tailer = DatasetTailerService(self.ingestor, poll_interval=5.0)
        asyncio.create_task(self.tailer.run_forever())
        logger.info("DatasetTailerService started.")
        
        # Initialize and start LocalScheduler
        self.scheduler = LocalScheduler(self.ingestor)
        await self.scheduler.start()
        logger.info("LocalScheduler started.")

        # X API Filtered Stream
        if self.x_stream_enabled:
            try:
                rules_mgr = XStreamRulesManager(self.db_session)
                rules_mgr.sync_rules_to_x_api()
                self.x_stream_collector = XStreamCollector(self.ingestor)
                self.x_stream_collector_task = asyncio.create_task(self.x_stream_collector.run_forever())
                logger.info("XStreamCollector started.")
            except Exception as e:
                logger.warning(f"XStreamCollector failed to start (check X_BEARER_TOKEN and credits): {e}")
        
        # Initialize and start AnalysisWorker (real-time analysis)
        self.analysis_worker = AnalysisWorker(max_workers=25)
        self.analysis_task = asyncio.create_task(self.analysis_worker.run_forever())
        logger.info("AnalysisWorker started (real-time analysis enabled).")

        # Issue detection + promotion polling
        self.issue_task = asyncio.create_task(self._issue_detection_loop())
        logger.info(f"Issue detection loop started (interval={self.issue_poll_interval}s).")
        
        self._running = True
        logger.info("Streaming Collection Service is now running.")

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._shutdown_handler(s)))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler in the same way, harmless on Linux
                pass

        # Keep running until stopped
        try:
            while self._running:
                # Heartbeat: Log memory usage and life signs
                try:
                    usage = resource.getrusage(resource.RUSAGE_SELF)
                    # On Linux, ru_maxrss is in Kilobytes
                    mem_mb = usage.ru_maxrss / 1024
                    logger.info(f"HEARTBEAT: Service is alive. RSS Memory: {mem_mb:.1f} MB. Active tasks: {len(asyncio.all_tasks())}")
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")

                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
        except Exception as e:
            logger.critical(f"CRITICAL ERROR in main service loop: {e}", exc_info=True)
            # Try to stop gracefully if possible
            await self.stop()
            raise

    async def _shutdown_handler(self, sig):
        """Handle termination signals."""
        logger.warning(f"RECEIVED SIGNAL: {sig.name} ({sig.value}) - Initiating Graceful Shutdown...")
        await self.stop()
    
    async def stop(self):
        """Stop all streaming components."""
        logger.info("Stopping Streaming Collection Service...")
        self._running = False
        
        if self.tailer:
            await self.tailer.stop()

        if self.x_stream_collector:
            self.x_stream_collector.stop()
        if self.x_stream_collector_task:
            self.x_stream_collector_task.cancel()
            try:
                await self.x_stream_collector_task
            except asyncio.CancelledError:
                pass
        
        if self.scheduler:
            await self.scheduler.stop()
        
        if self.analysis_worker:
            self.analysis_worker.stop()
        
        if self.issue_task:
            self.issue_task.cancel()
        
        if self.db_session:
            self.db_session.close()
        
        logger.info("Streaming Collection Service stopped.")
    
    def get_status(self) -> dict:
        """Get status of all components."""
        return {
            'running': self._running,
            'tailer': {
                'watching_runs': len(self.tailer.watching_runs) if self.tailer else 0,
                'processed_runs': len(self.tailer.processed_run_ids) if self.tailer else 0,
            },
            'scheduler': self.scheduler.get_next_run_times() if self.scheduler else {},
            'x_stream_enabled': self.x_stream_enabled,
            'x_stream_running': self.x_stream_collector_task is not None and not self.x_stream_collector_task.done() if self.x_stream_collector_task else False,
            'issue_poll_interval_seconds': self.issue_poll_interval,
        }

    async def _issue_detection_loop(self):
        """Periodic issue detection and promotion across all topics."""
        # Use dedicated issue detection logger
        issue_logger = get_logger('services.issue_detection')
        issue_logger.info(f"Issue detection loop initialized, will run every {self.issue_poll_interval}s")
        iteration = 0
        while self._running:
            try:
                iteration += 1
                start_time = time.time()
                issue_logger.info(f"Issue detection loop: Starting iteration {iteration} (every {self.issue_poll_interval}s)")
                # Run blocking issue detection in a thread to not verify block the event loop
                await asyncio.to_thread(self._run_issue_detection)
                issue_logger.info(f"Issue detection loop: Completed iteration {iteration}")

            except asyncio.CancelledError:
                issue_logger.info("Issue detection loop: Cancelled")
                break
            except Exception as e:
                issue_logger.error(f"Issue detection loop error: {e}", exc_info=True)

            except Exception as e:
                issue_logger.error(f"Issue detection loop error: {e}", exc_info=True)

            # Calculate duration and sleep
            duration = time.time() - start_time
            sleep_time = max(1.0, self.issue_poll_interval - duration)
            
            issue_logger.info(f"Issue detection loop: Iteration {iteration} took {duration:.1f}s. Sleeping for {sleep_time:.1f}s (Target interval: {self.issue_poll_interval}s)")
            await asyncio.sleep(sleep_time)
    
    def _run_issue_detection(self):
        """Synchronous issue detection - runs in a thread pool."""
        issue_logger = get_logger('services.issue_detection')
        issue_logger.info("Issue detection: Starting detection run")
        processor = DataProcessor()
        engine = processor.issue_detection_engine
        if not engine:
            issue_logger.warning("Issue detection: No issue detection engine available, skipping")
            return
        
        issue_logger.info(f"Issue detection: Engine available, proceeding with detection (Parallel: {self.issue_max_workers} workers)")
        # Persist clusters (and create issues immediately if promotion disabled)
        processor.detect_issues_for_all_topics(limit_per_topic=None, max_workers=self.issue_max_workers)

        # If promotion mode is on, promote top-N clusters to issues
        if engine.promotion_enabled:
            issue_logger.info("Promotion mode enabled - promoting clusters to issues")
            session = SessionLocal()
            try:
                # Check current active issue count and enforce issue limit
                from src.api.models import TopicIssue
                from config.config_manager import ConfigManager
                config = ConfigManager()
                MAX_ACTIVE_ISSUES = config.get_int('processing.issue.promotion.max_active_issues', 30)
                current_active = session.query(TopicIssue).filter(
                    TopicIssue.is_active == True
                ).count()
                
                issue_logger.info(f"Current active issues: {current_active} (limit: {MAX_ACTIVE_ISSUES})")
                
                # If over limit, archive lowest priority issues to get back to limit
                if current_active > MAX_ACTIVE_ISSUES:
                    excess = current_active - MAX_ACTIVE_ISSUES
                    issue_logger.warning(f"Exceeding limit by {excess} issues. Archiving lowest priority issues...")
                    
                    # Get lowest priority active issues (sorted by priority_score, then by mention_count)
                    low_priority_issues = session.query(TopicIssue).filter(
                        TopicIssue.is_active == True
                    ).order_by(
                        TopicIssue.priority_score.asc(),
                        TopicIssue.mention_count.asc()
                    ).limit(excess).all()
                    
                    archived_count = 0
                    for issue in low_priority_issues:
                        issue.is_active = False
                        issue.is_archived = True
                        issue.state = 'archived'
                        archived_count += 1
                        issue_logger.info(f"Archived issue: {issue.issue_slug} (priority: {issue.priority_score:.1f}, mentions: {issue.mention_count})")
                    
                    session.commit()
                    issue_logger.info(f"Archived {archived_count} issues to maintain limit of {MAX_ACTIVE_ISSUES}")
                    current_active = session.query(TopicIssue).filter(
                        TopicIssue.is_active == True
                    ).count()
                    issue_logger.info(f"Active issues after archiving: {current_active}")
                
                # Merge similar issues across all topics (runs regardless of limit)
                # Note: This happens BEFORE promotion. Additional merging happens after each topic's promotion.
                issue_logger.info("Checking for similar issues to merge across all topics (before promotion)...")
                topic_keys = [t[0] for t in session.query(MentionTopic.topic_key).distinct().all()]
                issue_logger.info(f"Found {len(topic_keys)} topics to check for merging")
                total_merged = 0
                merge_start_time = datetime.now()
                for topic_key in topic_keys:
                    try:
                        issue_logger.debug(f"Checking for similar issues to merge in topic: {topic_key}")
                        merged_count = engine._merge_similar_issues(session, topic_key)
                        if merged_count > 0:
                            total_merged += merged_count
                            issue_logger.info(f"Issue merging: topic={topic_key} merged {merged_count} pairs of similar issues")
                    except Exception as e:
                        issue_logger.error(f"Issue merging failed for topic {topic_key}: {e}", exc_info=True)
                
                if total_merged > 0:
                    session.commit()
                    merge_duration = (datetime.now() - merge_start_time).total_seconds()
                    issue_logger.info(f"Issue merging complete: {total_merged} pairs of similar issues merged across all topics (took {merge_duration:.1f}s)")
                    # Recheck active count after merging
                    current_active = session.query(TopicIssue).filter(
                        TopicIssue.is_active == True
                    ).count()
                    issue_logger.info(f"Active issues after merging: {current_active}")
                else:
                    merge_duration = (datetime.now() - merge_start_time).total_seconds()
                    issue_logger.info(f"No issues were merged (took {merge_duration:.1f}s)")
                
                # Recheck active count (in case no merging happened)
                current_active = session.query(TopicIssue).filter(
                    TopicIssue.is_active == True
                ).count()
                issue_logger.info(f"Current active issues before promotion: {current_active} (limit: {MAX_ACTIVE_ISSUES})")
                
                # Only promote if under limit
                if current_active >= MAX_ACTIVE_ISSUES:
                    issue_logger.info(f"At/over issue limit ({current_active}/{MAX_ACTIVE_ISSUES}), skipping promotion")
                else:
                    issue_logger.info(f"Found {len(topic_keys)} topics for promotion")
                    
                    remaining_slots = MAX_ACTIVE_ISSUES - current_active
                    issue_logger.info(f"Available slots for new issues: {remaining_slots}")
                    
                    total_promoted = 0
                    # Use parallel promotion from DataProcessor
                    try:
                        total_promoted = processor.promote_issues_for_all_topics(
                            max_active_issues=MAX_ACTIVE_ISSUES,
                            top_n=min(engine.promotion_top_n, 5), # Safety cap
                            max_workers=self.issue_max_workers
                        )
                        issue_logger.info(f"Promoted {total_promoted} issues in parallel.")
                    except Exception as e:
                        issue_logger.error(f"Parallel promotion failed: {e}")
                        total_promoted = 0
                    
                    final_count = session.query(TopicIssue).filter(
                        TopicIssue.is_active == True
                    ).count()
                    
                    if total_promoted > 0:
                        issue_logger.info(f"Issue promotion complete: {total_promoted} clusters promoted across {len(topic_keys)} topics (total active: {final_count})")
                    else:
                        issue_logger.info(f"Issue promotion complete: No clusters were promoted (may need to check cluster eligibility). Total active: {final_count}")
            except Exception as e:
                issue_logger.error(f"Error in issue promotion process: {e}", exc_info=True)
            finally:
                session.close()
        else:
            issue_logger.debug("Promotion mode disabled - issues created directly from clusters")
        
        # Backfill labels and summaries for issues that don't have them
        self._backfill_issue_labels_summaries(engine)
        
        # Backfill metrics for issues that have empty/default values
        self._backfill_issue_metrics(engine)
    
    def _backfill_issue_labels_summaries(self, engine):
        """Backfill labels and summaries for existing issues that don't have them."""
        issue_logger = get_logger('services.issue_detection')
        session = SessionLocal()
        try:
            # Find issues missing label or summary
            issues = session.query(TopicIssue).filter(
                TopicIssue.is_active == True,
                (
                    (TopicIssue.issue_label.is_(None)) |
                    (TopicIssue.issue_summary.is_(None)) |
                    (TopicIssue.issue_label == '') |
                    (TopicIssue.issue_summary == '')
                )
            ).limit(10).all()  # Process 10 at a time to avoid long runs
            
            if not issues:
                issue_logger.debug("No issues need label/summary backfill")
                return
            
            issue_logger.info(f"Backfilling labels/summaries for {len(issues)} issues")
            
            updated = 0
            skipped = 0
            
            for issue in issues:
                try:
                    # Get all mentions for this issue
                    all_mentions = self._get_all_issue_mentions(session, issue)
                    
                    if not all_mentions or len(all_mentions) < 15:
                        issue_logger.debug(f"Skipping issue {issue.issue_slug}: {len(all_mentions) if all_mentions else 0} mentions (need at least 15)")
                        skipped += 1
                        continue
                    
                    if not engine.openai_client:
                        issue_logger.warning("OpenAI client not available, skipping backfill")
                        break
                    
                    # Generate label and summary
                    issue_logger.info(f"Generating label/summary for issue {issue.issue_slug} ({len(all_mentions)} mentions)")
                    label_result = engine._generate_issue_label_and_summary(all_mentions)
                    
                    new_label = label_result.get('title')
                    new_summary = label_result.get('statement')
                    
                    # Update both label and summary if either is missing
                    # This ensures consistency - if we're regenerating, we regenerate both
                    updated_fields = []
                    if new_label:
                        issue.issue_label = new_label
                        updated_fields.append("label")
                    if new_summary:
                        issue.issue_summary = new_summary
                        updated_fields.append("summary")
                    
                    if updated_fields:
                        session.commit()
                        issue_logger.info(f"✓ Updated issue {issue.issue_slug} ({', '.join(updated_fields)})")
                        updated += 1
                    else:
                        issue_logger.warning(f"Failed to generate label/summary for issue {issue.issue_slug}")
                        skipped += 1
                        
                except Exception as e:
                    issue_logger.error(f"Error backfilling issue {issue.issue_slug}: {e}", exc_info=True)
                    session.rollback()
                    skipped += 1
            
            if updated > 0:
                issue_logger.info(f"Backfill complete: {updated} updated, {skipped} skipped")
        except Exception as e:
            issue_logger.error(f"Error in backfill process: {e}", exc_info=True)
        finally:
            session.close()
    
    def _backfill_issue_metrics(self, engine):
        """Backfill metrics (volume, velocity, sentiment, metadata) for existing issues that have empty/default values."""
        issue_logger = get_logger('services.issue_detection')
        session = SessionLocal()
        try:
            # Find issues with empty/default metrics
            # Check for issues where volume is 0, sentiment_index is 50 (default), or emotion_distribution is empty
            issues = session.query(TopicIssue).filter(
                TopicIssue.is_active == True,
                (
                    (TopicIssue.volume_current_window == 0) |
                    (TopicIssue.volume_previous_window == 0) |
                    (TopicIssue.velocity_percent == 0.0) |
                    (TopicIssue.sentiment_index == 50.0) |
                    (TopicIssue.emotion_distribution.is_(None)) |
                    (TopicIssue.emotion_distribution == {})
                )
            ).limit(10).all()  # Process 10 at a time to avoid long runs
            
            if not issues:
                issue_logger.debug("No issues need metrics backfill")
                return
            
            issue_logger.info(f"Backfilling metrics for {len(issues)} issues")
            
            updated = 0
            skipped = 0
            
            for issue in issues:
                try:
                    # Check if issue has any mentions
                    from api.models import IssueMention
                    mention_count = session.query(IssueMention).filter(
                        IssueMention.issue_id == issue.id
                    ).count()
                    
                    if mention_count == 0:
                        issue_logger.debug(f"Skipping issue {issue.issue_slug}: no mentions linked")
                        skipped += 1
                        continue
                    
                    # Recalculate all metrics using the engine's method
                    issue_logger.info(f"Recalculating metrics for issue {issue.issue_slug} ({mention_count} mentions)")
                    engine._recalculate_issue_metrics(session, issue)
                    
                    session.commit()
                    issue_logger.info(f"✓ Updated metrics for issue {issue.issue_slug}")
                    updated += 1
                    
                except Exception as e:
                    issue_logger.error(f"Error backfilling metrics for issue {issue.issue_slug}: {e}", exc_info=True)
                    session.rollback()
                    skipped += 1
            
            if updated > 0:
                issue_logger.info(f"Metrics backfill complete: {updated} updated, {skipped} skipped")
        except Exception as e:
            issue_logger.error(f"Error in metrics backfill process: {e}", exc_info=True)
        finally:
            session.close()
    
    def _get_all_issue_mentions(self, session, issue: TopicIssue) -> list:
        """Get all mentions for an issue with their embeddings."""
        # Get all issue mentions
        issue_mentions = session.query(IssueMention).filter(
            IssueMention.issue_id == issue.id
        ).all()
        
        if not issue_mentions:
            return []
        
        mention_ids = [im.mention_id for im in issue_mentions]
        
        # Fetch sentiment data with embeddings
        mentions = session.query(SentimentData, SentimentEmbedding).outerjoin(
            SentimentEmbedding, SentimentData.entry_id == SentimentEmbedding.entry_id
        ).filter(
            SentimentData.entry_id.in_(mention_ids)
        ).all()
        
        result = []
        for sd, se in mentions:
            embedding = None
            if se and se.embedding:
                embedding = se.embedding
            elif se and se.embedding_vector:
                embedding = se.embedding_vector
            
            # Skip zero vectors
            if embedding and isinstance(embedding, list):
                if all(abs(x) < 1e-6 for x in embedding):
                    continue
            
            result.append({
                'entry_id': sd.entry_id,
                'text': sd.text or '',
                'embedding': embedding,
                'sentiment_score': sd.sentiment_score,
                'sentiment_label': sd.sentiment_label,
                'emotion_label': sd.emotion_label,
                'source_type': sd.source_type,
                'source': sd.source,
                'platform': sd.platform,
                'created_at': sd.created_at
            })
        
        return result


async def main():
    """Main entry point for the streaming service."""
    user_id = os.getenv('STREAMING_USER_ID')
    run_collectors_now = os.getenv('RUN_COLLECTORS_NOW', 'false').lower() == 'true'
    
    service = StreamingCollectionService(user_id=user_id)
    
    try:
        await service.start()
        
        # Optionally run collectors immediately on startup
        if run_collectors_now and service.scheduler:
            logger.info("RUN_COLLECTORS_NOW=true: Triggering all collectors...")
            for collector_name in service.scheduler.collectors.keys():
                logger.info(f"Triggering collector: {collector_name}")
                await service.scheduler.run_collector_now(collector_name)
                
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    finally:
        await service.stop()


async def run_collector(collector_name: str):
    """Utility to run a single collector immediately."""
    from services.scheduler import LocalScheduler
    scheduler = LocalScheduler()
    return await scheduler.run_collector_now(collector_name)


if __name__ == "__main__":
    asyncio.run(main())
