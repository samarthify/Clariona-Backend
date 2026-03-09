"""
Incremental Cluster Assigner - Assigns mentions to clusters via Pinecone nearest-neighbor.

Consumes from cluster_queue, queries Pinecone for nearest clusters, assigns or creates.
Only runs when use_incremental_clustering=true. Replaces batch DBSCAN for new mentions.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session
from config.config_manager import ConfigManager
from src.api.database import SessionLocal
from src.api.models import (
    ClusterQueue,
    ProcessingCluster,
)
from src.config.logging_config import get_logger
from src.services.pinecone_client import query as pinecone_query, upsert as pinecone_upsert
from src.services.velocity_tracker import VelocityTracker

logger = get_logger(__name__)


class IncrementalClusterAssigner:
    """
    Consumes cluster_queue, assigns mentions to clusters via Pinecone vector search.
    Write-only: uses embedding from event payload only (no DB read for embedding).
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        poll_interval: float = 2.0,
        batch_size: int = 10,
        attach_threshold: Optional[float] = None,
    ):
        self.db = db_session
        self.poll_interval = poll_interval
        self.batch_size = batch_size

        config = ConfigManager()
        self.attach_threshold = attach_threshold or config.get_float(
            "processing.issue.incremental.attach_similarity_threshold", 0.70
        )
        self.velocity_tracker = VelocityTracker()

    def _get_db(self) -> Session:
        if self.db:
            return self.db
        return SessionLocal()

    def _close_db(self, session: Session):
        if not self.db and session:
            session.close()

    def _fetch_pending(self, session: Session) -> List[ClusterQueue]:
        """Fetch pending queue rows with FOR UPDATE SKIP LOCKED."""
        rows = (
            session.query(ClusterQueue)
            .filter(ClusterQueue.status == "pending")
            .order_by(ClusterQueue.created_at)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
            .all()
        )
        return rows

    def _process_one(self, session: Session, row: ClusterQueue) -> Optional[str]:
        """
        Process one cluster_queue event. Returns "assigned", "created", or None on skip/fail.
        Uses embedding from payload only (write-only assigner).
        """
        embedding = row.embedding
        if not embedding or not isinstance(embedding, (list, tuple)):
            logger.warning("cluster_queue id=%s: missing embedding, skipping", row.id)
            row.status = "failed"
            row.retry_count += 1
            return None

        embedding = list(embedding)
        if len(embedding) != 1536:
            logger.warning(
                "cluster_queue id=%s: embedding dim=%s (expected 1536), skipping",
                row.id,
                len(embedding),
            )
            row.status = "failed"
            row.retry_count += 1
            return None

        entry_id = row.entry_id
        topic_key = row.topic_key
        user_id = row.user_id
        topic_keys = list(row.topic_keys) if row.topic_keys else [topic_key]

        # Pinecone filter: global (status only) or legacy (topic_key + user_id)
        user_id_str = str(user_id) if user_id else "null"
        config = ConfigManager()
        use_global = config.use_global_clustering(db_session=session)
        if use_global:
            # Global clustering: no user_id in filter; search across all active clusters
            filter_dict = {"status": {"$eq": "active"}}
        else:
            filter_dict = {
                "topic_key": {"$eq": topic_key},
                "user_id": {"$eq": user_id_str},
                "status": {"$eq": "active"},
            }

        matches = pinecone_query(
            vector=embedding,
            top_k=5,
            filter_dict=filter_dict,
        )

        cluster_uuid = None
        if matches and matches[0]["score"] >= self.attach_threshold:
            cluster_id_str = matches[0]["id"]
            try:
                cluster_uuid = uuid.UUID(cluster_id_str)
            except ValueError:
                logger.warning("Invalid cluster_id from Pinecone: %s", cluster_id_str)
                row.status = "failed"
                return None
            success = self._assign_to_existing(
                session, row, entry_id, topic_key, topic_keys, user_id, embedding, cluster_uuid
            )
        else:
            success, cluster_uuid = self._create_new_cluster(
                session, row, entry_id, topic_key, topic_keys, user_id, embedding
            )

        if success:
            row.status = "completed"
            if cluster_uuid:
                try:
                    self.velocity_tracker.record(cluster_uuid)
                except Exception as ve:
                    logger.debug("VelocityTracker record (non-fatal): %s", ve)
            return "assigned" if matches and matches[0]["score"] >= self.attach_threshold else "created"
        return None

    def _assign_to_existing(
        self,
        session: Session,
        row: ClusterQueue,
        entry_id: int,
        topic_key: str,
        topic_keys: List[str],
        user_id: Optional[uuid.UUID],
        embedding: List[float],
        cluster_id: uuid.UUID,
    ) -> bool:
        """Assign mention to existing cluster. Lock cluster, update sum_vec, upsert Pinecone."""
        cluster = (
            session.query(ProcessingCluster)
            .filter(
                ProcessingCluster.id == cluster_id,
                ProcessingCluster.status == "active",
            )
            .with_for_update()
            .first()
        )
        if not cluster:
            logger.warning("Cluster %s not found or not active", cluster_id)
            return False

        old_size = cluster.size or 0
        old_sum = list(cluster.sum_vec) if cluster.sum_vec else [0.0] * 1536
        if len(old_sum) != 1536:
            old_sum = [0.0] * 1536

        new_sum = [old_sum[i] + embedding[i] for i in range(1536)]
        new_size = old_size + 1
        new_centroid = [s / new_size for s in new_sum]

        cluster.sum_vec = new_sum
        cluster.size = new_size
        cluster.centroid = new_centroid
        cluster.version = (cluster.version or 1) + 1

        # Update topic_keys: union of existing and mention's topics
        existing_keys = set(cluster.topic_keys or [])
        existing_keys.update(topic_keys)
        cluster.topic_keys = list(existing_keys)

        # Upsert to Pinecone (global: topic_keys; legacy: topic_key for backward compat)
        user_id_str = str(user_id) if user_id else "null"
        metadata = {
            "user_id": user_id_str,
            "status": "active",
            "size": new_size,
            "topic_keys": cluster.topic_keys,
        }
        config = ConfigManager()
        if not config.use_global_clustering(db_session=session):
            metadata["topic_key"] = topic_key

        pinecone_upsert(
            vectors=[
                {
                    "id": str(cluster.id),
                    "values": new_centroid,
                    "metadata": metadata,
                }
            ]
        )

        # Idempotent: INSERT cluster_mentions ON CONFLICT DO NOTHING
        try:
            session.execute(
                text(
                    """
                    INSERT INTO cluster_mentions (id, cluster_id, mention_id, similarity_score, created_at)
                    VALUES (gen_random_uuid(), :cluster_id, :mention_id, 1.0, now())
                    ON CONFLICT (cluster_id, mention_id) DO NOTHING
                    """
                ),
                {"cluster_id": str(cluster.id), "mention_id": entry_id},
            )
        except Exception as e:
            logger.warning("cluster_mentions insert: %s", e)

        return True

    def _create_new_cluster(
        self,
        session: Session,
        row: ClusterQueue,
        entry_id: int,
        topic_key: str,
        topic_keys: List[str],
        user_id: Optional[uuid.UUID],
        embedding: List[float],
    ) -> tuple:
        """Create new cluster, upsert to Pinecone, link mention. Returns (success, cluster_id)."""
        cluster = ProcessingCluster(
            id=uuid.uuid4(),
            topic_key=topic_key,
            topic_keys=topic_keys,
            user_id=user_id,
            centroid=embedding,
            sum_vec=embedding,
            size=1,
            version=1,
            status="active",
        )
        session.add(cluster)
        session.flush()

        user_id_str = str(user_id) if user_id else "null"
        metadata = {
            "user_id": user_id_str,
            "status": "active",
            "size": 1,
            "topic_keys": topic_keys,
        }
        config = ConfigManager()
        if not config.use_global_clustering(db_session=session):
            metadata["topic_key"] = topic_key

        pinecone_upsert(
            vectors=[
                {
                    "id": str(cluster.id),
                    "values": embedding,
                    "metadata": metadata,
                }
            ]
        )

        try:
            session.execute(
                text(
                    """
                    INSERT INTO cluster_mentions (id, cluster_id, mention_id, similarity_score, created_at)
                    VALUES (gen_random_uuid(), :cluster_id, :mention_id, 1.0, now())
                    ON CONFLICT (cluster_id, mention_id) DO NOTHING
                    """
                ),
                {"cluster_id": str(cluster.id), "mention_id": entry_id},
            )
        except Exception as e:
            logger.warning("cluster_mentions insert: %s", e)

        return True, cluster.id

    def run_once(self, session: Optional[Session] = None) -> int:
        """Process one batch. Returns count processed."""
        db = session or self._get_db()
        own_session = session is None
        try:
            rows = self._fetch_pending(db)
            ids = [r.id for r in rows]
            if not ids:
                return 0

            # Mark as processing and commit (releases lock)
            db.query(ClusterQueue).filter(ClusterQueue.id.in_(ids)).update(
                {"status": "processing"}, synchronize_session=False
            )
            db.commit()

            # Process each in own transaction
            assigned, created = 0, 0
            for qid in ids:
                row = db.query(ClusterQueue).filter(ClusterQueue.id == qid).first()
                if not row:
                    continue
                try:
                    result = self._process_one(db, row)
                    if result == "assigned":
                        assigned += 1
                    elif result == "created":
                        created += 1
                    db.commit()
                except Exception as e:
                    logger.exception("assigner process id=%s: %s", qid, e)
                    db.rollback()
                    try:
                        db.execute(
                            text(
                                "UPDATE cluster_queue SET status = 'failed', retry_count = retry_count + 1 WHERE id = :id"
                            ),
                            {"id": qid},
                        )
                        db.commit()
                    except Exception:
                        db.rollback()

            logger.info(
                "Processed %d cluster_queue rows: %d assigned to existing, %d new clusters",
                len(ids), assigned, created,
            )
            return len(ids)
        except Exception as e:
            logger.exception("assigner run_once: %s", e)
            db.rollback()
            return 0
        finally:
            if own_session:
                self._close_db(db)

    def run_loop(self, stop_event=None):
        """Run consumer loop until stop_event is set."""
        logger.info("IncrementalClusterAssigner started")
        last_empty_log = 0.0
        EMPTY_LOG_INTERVAL = 60.0  # Log when queue empty at most every 60s
        while stop_event is None or not stop_event.is_set():
            try:
                config = ConfigManager()
                db = self._get_db()
                try:
                    if not config.use_incremental_clustering(db_session=db):
                        time.sleep(self.poll_interval)
                        continue

                    n = self.run_once(session=db)
                finally:
                    self._close_db(db)
                if n == 0:
                    now = time.time()
                    if now - last_empty_log >= EMPTY_LOG_INTERVAL:
                        logger.info("cluster_queue empty, polling")
                        last_empty_log = now
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.exception("assigner loop: %s", e)
                time.sleep(self.poll_interval)
