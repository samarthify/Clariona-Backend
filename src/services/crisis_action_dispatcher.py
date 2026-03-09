"""
CrisisActionDispatcher - Fan-out crisis events to subscribed users.

User scope appears only here. Resolves subscribed users via:
  users u JOIN owner_configs oc ON u.owner_key = oc.owner_key
  WHERE oc.topics && issue.topic_keys AND oc.is_active = true

Per-user cooldown: crisis:{cluster_id}:{level}:{user_id}
"""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Redis (lazy)
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning("Redis not available for CrisisActionDispatcher: %s", e)
        return None


class CrisisActionDispatcher:
    """
    Dispatches crisis events to users whose owner_configs.topics overlap with event topic_keys.
    """

    COOLDOWN_SECONDS = 3600  # 1 hour per user per cluster/level

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self._redis = _get_redis()

    def _get_session(self) -> Session:
        if self.db:
            return self.db
        from api.database import SessionLocal
        return SessionLocal()

    def get_subscribed_user_ids(self, session: Session, topic_keys: List[str]) -> List[uuid.UUID]:
        """
        Users with owner_configs.topics overlapping issue topic_keys.
        Uses GIN index on owner_configs(topics) for &&.
        """
        if not topic_keys:
            return []
        stmt = text("""
            SELECT DISTINCT u.id
            FROM users u
            JOIN owner_configs oc ON u.owner_key = oc.owner_key
            WHERE oc.topics && :topic_keys
              AND oc.is_active = true
              AND u.owner_key IS NOT NULL
        """)
        result = session.execute(stmt, {"topic_keys": topic_keys})
        return [row[0] for row in result.fetchall()]

    def _cooldown_key(self, cluster_id: uuid.UUID, level: str, user_id: uuid.UUID) -> str:
        return f"crisis:{cluster_id}:{level}:{user_id}"

    def _check_cooldown(self, key: str) -> bool:
        if not self._redis:
            return False
        try:
            return self._redis.exists(key) > 0
        except Exception:
            return False

    def _set_cooldown(self, key: str) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(key, self.COOLDOWN_SECONDS, "1")
        except Exception as e:
            logger.warning("Failed to set cooldown %s: %s", key, e)

    def dispatch(
        self,
        cluster_id: uuid.UUID,
        topic_keys: List[str],
        level: str,
        burst_ratio: float,
        count_1m: int,
        count_5m: int,
        count_15m: int,
        cluster_size: int,
        cluster_density: float,
        db_session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fan-out crisis event to subscribed users.
        Returns list of {user_id, routed_to, alert_event_id} for each user notified.
        """
        session = db_session or self._get_session()
        own_session = db_session is None
        results = []

        try:
            user_ids = self.get_subscribed_user_ids(session, topic_keys)
            logger.info("Crisis fan-out: %d users subscribed to topic_keys %s", len(user_ids), topic_keys[:5])

            for user_id in user_ids:
                cooldown_key = self._cooldown_key(cluster_id, level, user_id)
                if self._check_cooldown(cooldown_key):
                    continue

                # Fire notification (placeholder - integrate Slack/email/webhook per user prefs)
                routed_to: Dict[str, Any] = {"channel": "placeholder"}
                # TODO: Apply user alert preferences (Slack, email, webhook)

                # Insert alert_events row
                from api.models import AlertEvent
                ae = AlertEvent(
                    user_id=user_id,
                    cluster_id=cluster_id,
                    topic_keys=topic_keys,
                    severity=level,
                    burst_ratio=burst_ratio,
                    count_1m=count_1m,
                    count_5m=count_5m,
                    count_15m=count_15m,
                    fired_at=datetime.utcnow(),
                    routed_to=routed_to,
                    cooldown_key=cooldown_key,
                )
                session.add(ae)
                session.flush()

                self._set_cooldown(cooldown_key)
                results.append({
                    "user_id": str(user_id),
                    "routed_to": routed_to,
                    "alert_event_id": str(ae.id),
                })
                logger.info("Crisis dispatched to user %s (alert_event %s)", user_id, ae.id)

            session.commit()
            return results

        except Exception as e:
            logger.exception("CrisisActionDispatcher dispatch failed: %s", e)
            session.rollback()
            return []
        finally:
            if own_session and session:
                session.close()
