"""
Topic Backfill Service: when new topics are added to the topics table,
run the topic classifier on last week's data for those new topics only,
and add MentionTopic rows only for the new topic(s) that match (existing
topic assignments are left unchanged).
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Set, Optional

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import Topic, SentimentData, SentimentEmbedding, MentionTopic
from processing.topic_classifier import TopicClassifier
from processing.topic_embedding_generator import TopicEmbeddingGenerator

from src.config.logging_config import get_logger

logger = get_logger("services.topic_backfill")


class TopicBackfillService:
    """
    Polls the topics table for new topics. When one or more new topics appear,
    generates embeddings for them (merged into topic_embeddings.json), then
    runs the topic classifier only for those new topic keys on last N days of
    mentions, and only adds MentionTopic rows for the new topic(s) that match.
    """

    def __init__(
        self,
        poll_interval_seconds: float = 300.0,
        lookback_days: int = 1,
        lookback_hours: Optional[int] = None,
        batch_size: int = 200,
        min_backfilled_count: int = 500,
    ):
        self.poll_interval_seconds = poll_interval_seconds
        self.lookback_days = lookback_days
        self.lookback_hours = lookback_hours
        self.batch_size = batch_size
        # Topic is "already backfilled" only if it has at least this many MentionTopic rows (avoids re-run on restart)
        self.min_backfilled_count = min_backfilled_count
        self._running = False
        self._last_known_topic_keys: Set[str] = set()
        self._initialized = False

    def _get_current_topic_keys(self, session: Session) -> Set[str]:
        """Return set of active topic keys from DB."""
        rows = session.query(Topic.topic_key).filter(Topic.is_active == True).all()
        return {r[0] for r in rows}

    def _get_newly_created_topic_keys(
        self, session: Session, since: datetime
    ) -> Set[str]:
        """Return active topic keys that were created on or after `since` (for first run / restart)."""
        from sqlalchemy import and_
        rows = (
            session.query(Topic.topic_key)
            .filter(
                and_(
                    Topic.is_active == True,
                    Topic.created_at >= since,
                )
            )
            .all()
        )
        return {r[0] for r in rows}

    def _ensure_embeddings_for_new_topics(self, new_topic_keys: Set[str]) -> int:
        """Generate and merge embeddings for new topics only. Returns count added."""
        if not new_topic_keys:
            return 0
        generator = TopicEmbeddingGenerator()
        return generator.generate_embeddings_for_topic_keys(list(new_topic_keys))

    @staticmethod
    def _add_mention_topic(session: Session, mention_id: int, topic: dict) -> None:
        """Insert one MentionTopic row (topic dict from TopicClassifier)."""
        import numpy as np
        def _float(v):
            if v is None:
                return None
            if isinstance(v, (np.integer, np.floating)):
                return float(v)
            return float(v) if isinstance(v, (int, float)) else None
        session.add(MentionTopic(
            mention_id=mention_id,
            topic_key=topic["topic"],
            topic_confidence=_float(topic.get("confidence")) or 0.0,
            keyword_score=_float(topic.get("keyword_score")),
            embedding_score=_float(topic.get("embedding_score")),
        ))

    def _run_backfill(self) -> None:
        """Sync backfill: run classifier on last week data and replace MentionTopic rows."""
        backfill_logger = get_logger("services.topic_backfill")
        session = SessionLocal()
        try:
            current_keys = self._get_current_topic_keys(session)
            if not self._initialized:
                # First run or after restart: treat topics created in last lookback window as "new"
                _delta = timedelta(hours=self.lookback_hours) if self.lookback_hours is not None else timedelta(days=self.lookback_days)
                since = datetime.now(timezone.utc) - _delta
                new_keys = self._get_newly_created_topic_keys(session, since)
                self._last_known_topic_keys = current_keys
                self._initialized = True
                if not new_keys:
                    backfill_logger.info(
                        f"Topic backfill: initialized with {len(current_keys)} topic(s). "
                        "No topics created in lookback window; will detect new topics on next poll."
                    )
                    return
                _win = f"{self.lookback_hours}h" if self.lookback_hours else f"{self.lookback_days}d"
                backfill_logger.info(
                    f"Topic backfill: first run — {len(new_keys)} topic(s) created in last {_win} (will skip any already backfilled)."
                )
            else:
                # Normal poll: new = currently active topics we haven't seen before
                new_keys = current_keys - self._last_known_topic_keys
                if not new_keys:
                    return
                backfill_logger.info(
                    f"Topic backfill: detected {len(new_keys)} new topic(s): {sorted(new_keys)}."
                )

            # Skip topics that already have >= min_backfilled_count MentionTopic rows (e.g. already backfilled)
            from sqlalchemy import func
            counts = (
                session.query(MentionTopic.topic_key, func.count(MentionTopic.mention_id).label("cnt"))
                .filter(MentionTopic.topic_key.in_(list(new_keys)))
                .group_by(MentionTopic.topic_key)
                .all()
            )
            already_backfilled = {r[0] for r in counts if r[1] >= self.min_backfilled_count}
            new_keys = new_keys - already_backfilled
            if already_backfilled:
                backfill_logger.info(
                    f"Topic backfill: skipping {len(already_backfilled)} topic(s) already backfilled (≥{self.min_backfilled_count} rows): {sorted(already_backfilled)}"
                )
            if not new_keys:
                backfill_logger.info("Topic backfill: no topics left to backfill (all already have data).")
                return

            # Update snapshot so we don't re-backfill these on next poll
            self._last_known_topic_keys = current_keys

            backfill_logger.info(
                "Topic backfill: ensuring embeddings and running classifier for new topics only on last week data."
            )

            # Ensure embeddings for new topics (merge into topic_embeddings.json)
            added = self._ensure_embeddings_for_new_topics(new_keys)
            if added > 0:
                backfill_logger.info(f"Topic backfill: merged {added} new topic embedding(s).")

            # TopicClassifier with use_spacy=False so we never load spaCy (same fast path as analysis worker)
            backfill_logger.info(
                "Topic backfill: creating TopicClassifier (use_spacy=False). "
                "If this hangs, check logs/analysis_worker.log for last TopicClassifier.__init__ step."
            )
            _tc0 = time.time()
            classifier = TopicClassifier(use_spacy=False)
            _tc_elapsed = time.time() - _tc0
            backfill_logger.info(f"Topic backfill: TopicClassifier created in {_tc_elapsed:.1f}s")
            new_keys_list = list(new_keys)

            # Last N days/hours of sentiment_data with optional embedding — fetch in batches to avoid loading all into memory
            _delta = timedelta(hours=self.lookback_hours) if self.lookback_hours is not None else timedelta(days=self.lookback_days)
            since = datetime.now(timezone.utc) - _delta
            base_query = (
                session.query(SentimentData, SentimentEmbedding)
                .outerjoin(
                    SentimentEmbedding,
                    SentimentData.entry_id == SentimentEmbedding.entry_id,
                )
                .filter(SentimentData.created_at >= since)
                .order_by(SentimentData.entry_id)
            )
            _window = f"{self.lookback_hours}h" if self.lookback_hours else f"{self.lookback_days} days"
            backfill_logger.info(
                f"Topic backfill: querying last {_window} in batches of {self.batch_size}..."
            )
            start_time = time.time()
            processed = 0
            added_rows = 0
            errors = 0
            offset = 0

            while True:
                batch = base_query.limit(self.batch_size).offset(offset).all()
                if not batch:
                    if offset == 0:
                        backfill_logger.info("Topic backfill: no mentions in lookback window, nothing to do.")
                    break
                if offset == 0:
                    backfill_logger.info(
                        f"Topic backfill: classifying mentions for {len(new_keys_list)} new topic(s) (batch size {self.batch_size})..."
                    )
                batch_done = 0
                for idx, (sd, se) in enumerate(batch):
                    try:
                        if idx == 0:
                            backfill_logger.info(f"Topic backfill: processing first of {len(batch)} in batch (entry_id={sd.entry_id})...")
                        entry_id = sd.entry_id
                        text = (sd.text or sd.content or sd.title or sd.description or "").strip()
                        if not text:
                            continue
                        embedding = None
                        if se and se.embedding:
                            emb = se.embedding
                            if isinstance(emb, list) and len(emb) == 1536:
                                embedding = emb
                        if embedding and isinstance(embedding, list) and all(
                            abs(x) < 1e-6 for x in embedding
                        ):
                            embedding = None

                        # Classify only for the new topic keys
                        topic_result = classifier.classify_for_topic_keys(
                            text, embedding, topic_keys=new_keys_list
                        )
                        if not topic_result:
                            processed += 1
                            batch_done += 1
                            continue
                        # Only add MentionTopic for the new topic(s) that matched; don't touch existing
                        for topic in topic_result:
                            existing = session.query(MentionTopic).filter(
                                MentionTopic.mention_id == entry_id,
                                MentionTopic.topic_key == topic["topic"],
                            ).first()
                            if not existing:
                                self._add_mention_topic(session, entry_id, topic)
                                added_rows += 1
                        processed += 1
                        batch_done += 1
                    except Exception as e:
                        errors += 1
                        batch_done += 1
                        backfill_logger.warning(
                            f"Topic backfill: error for entry_id={getattr(sd, 'entry_id', None)}: {e}"
                        )
                    # Log every 25 mentions in this batch so we see progress (avoids looking stuck)
                    if batch_done > 0 and batch_done % 25 == 0:
                        backfill_logger.info(
                            f"Topic backfill: batch progress — {batch_done}/{len(batch)} in batch, "
                            f"total processed {processed}, added {added_rows} new topic row(s)"
                        )

                session.commit()
                offset += len(batch)
                backfill_logger.info(
                    f"Topic backfill: finished batch — {len(batch)} mention(s), total so far: processed {processed}, added {added_rows} new topic row(s)"
                )
                if (offset // self.batch_size) % 10 == 0 and offset > 0:
                    backfill_logger.info(f"Topic backfill: progress — processed {processed} mention(s), added {added_rows} new topic row(s) so far")

            elapsed = time.time() - start_time
            backfill_logger.info(
                f"Topic backfill: done. Processed {processed} mention(s), added {added_rows} new topic row(s) "
                f"in {elapsed:.1f}s (errors={errors})."
            )
        except Exception as e:
            backfill_logger.error(f"Topic backfill: run failed: {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()

    async def run_forever(self) -> None:
        """Run the poll loop: periodically check for new topics and backfill when needed."""
        backfill_logger = get_logger("services.topic_backfill")
        _lb = f"{self.lookback_hours}h" if self.lookback_hours else f"{self.lookback_days} days"
        backfill_logger.info(
            f"Topic backfill service started (poll every {self.poll_interval_seconds}s, lookback {_lb})."
        )
        self._running = True
        while self._running:
            try:
                await asyncio.to_thread(self._run_backfill)
            except asyncio.CancelledError:
                break
            except Exception as e:
                backfill_logger.error(f"Topic backfill poll error: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval_seconds)

        backfill_logger.info("Topic backfill service stopped.")

    def stop(self) -> None:
        """Signal the service to stop."""
        self._running = False
