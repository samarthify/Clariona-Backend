"""
CrisisEvaluator - Evaluates clusters for crisis-level events.

CrisisEvent has no user_id - evaluation is global.
User scope is applied only at notification fan-out in CrisisActionDispatcher.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class CrisisEvent:
    """A crisis-level event (no user scope)."""
    level: str  # e.g. "critical", "high", "medium"
    cluster_id: uuid.UUID
    topic_keys: List[str]
    burst_ratio: float
    count_1m: int
    count_5m: int
    count_15m: int
    cluster_size: int
    cluster_density: float
    triggered_at: datetime


class CrisisEvaluator:
    """
    Evaluates clusters for crisis-level conditions.
    Uses velocity snapshot (from VelocityTracker) and cluster metrics.
    """

    def __init__(
        self,
        burst_threshold_critical: float = 3.0,
        burst_threshold_high: float = 2.0,
        burst_threshold_medium: float = 1.5,
        min_count_1m: int = 5,
    ):
        self.burst_threshold_critical = burst_threshold_critical
        self.burst_threshold_high = burst_threshold_high
        self.burst_threshold_medium = burst_threshold_medium
        self.min_count_1m = min_count_1m

    def evaluate(
        self,
        cluster_id: uuid.UUID,
        topic_keys: List[str],
        velocity_snapshot: Optional[Dict[str, Any]],
        cluster_size: int,
        cluster_density: float,
    ) -> Optional[CrisisEvent]:
        """
        Evaluate a cluster for crisis conditions.
        Returns CrisisEvent if thresholds met, else None.
        """
        count_1m = (velocity_snapshot or {}).get("count_1m", 0) or 0
        count_5m = (velocity_snapshot or {}).get("count_5m", 0) or 0
        count_15m = (velocity_snapshot or {}).get("count_15m", 0) or 0

        if count_1m < self.min_count_1m:
            return None

        # Burst ratio: 1m vs 15m normalized
        burst_ratio = 0.0
        if count_15m and count_15m > 0:
            # Expect ~count_15m/15 in 1m under steady state; burst = 1m / expected
            expected_1m = count_15m / 15.0
            burst_ratio = count_1m / expected_1m if expected_1m > 0 else 0.0

        level = None
        if burst_ratio >= self.burst_threshold_critical:
            level = "critical"
        elif burst_ratio >= self.burst_threshold_high:
            level = "high"
        elif burst_ratio >= self.burst_threshold_medium:
            level = "medium"

        if not level:
            return None

        return CrisisEvent(
            level=level,
            cluster_id=cluster_id,
            topic_keys=list(topic_keys or []),
            burst_ratio=burst_ratio,
            count_1m=count_1m,
            count_5m=count_5m,
            count_15m=count_15m,
            cluster_size=cluster_size or 0,
            cluster_density=cluster_density or 0.0,
            triggered_at=datetime.utcnow(),
        )
