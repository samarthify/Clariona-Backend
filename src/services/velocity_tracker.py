"""
VelocityTracker - Real-time mention velocity per cluster (Redis-backed).

Redis key pattern: vel:{cluster_id}:1m, vel:{cluster_id}:5m, vel:{cluster_id}:15m
No user_id - cluster-level only for global clustering.
"""

import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Redis client (lazy import)
_redis_client = None


def _get_redis():
    """Lazy Redis client. Returns None if Redis unavailable."""
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
        logger.warning("Redis not available for VelocityTracker: %s", e)
        return None


class VelocityTracker:
    """
    Track mention velocity per cluster over 1m, 5m, 15m windows.
    Uses Redis sorted sets (score = timestamp) for time-window counts.
    """

    TTL_1M = 120  # seconds
    TTL_5M = 360
    TTL_15M = 960

    def __init__(self, redis_client=None):
        self._redis = redis_client or _get_redis()

    def record(self, cluster_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Record a new mention for the cluster.
        Returns snapshot {count_1m, count_5m, count_15m} or None if Redis unavailable.
        """
        if not self._redis:
            return None
        cid = str(cluster_id)
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe = self._redis.pipeline()
        for suffix, ttl in [("1m", self.TTL_1M), ("5m", self.TTL_5M), ("15m", self.TTL_15M)]:
            key = f"vel:{cid}:{suffix}"
            pipe.zadd(key, {member: now})
            pipe.expire(key, ttl)
        try:
            pipe.execute()
        except Exception as e:
            logger.warning("VelocityTracker record failed: %s", e)
            return None
        return self.get_snapshot(cluster_id)

    def get_snapshot(self, cluster_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get current velocity counts for 1m, 5m, 15m windows.
        Returns {count_1m, count_5m, count_15m} or None.
        """
        if not self._redis:
            return None
        cid = str(cluster_id)
        now = time.time()
        cutoffs = [
            ("1m", now - 60),
            ("5m", now - 300),
            ("15m", now - 900),
        ]
        try:
            pipe = self._redis.pipeline()
            for suffix, cutoff in cutoffs:
                key = f"vel:{cid}:{suffix}"
                pipe.zcount(key, cutoff, "+inf")
            counts = pipe.execute()
            return {
                "count_1m": counts[0] or 0,
                "count_5m": counts[1] or 0,
                "count_15m": counts[2] or 0,
            }
        except Exception as e:
            logger.warning("VelocityTracker get_snapshot failed: %s", e)
            return None
