"""
X Feed Service - Live, Rising, Trending, Top Today feeds over the tweets table.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.api.models import Tweet

logger = logging.getLogger("services.x_feed_service")

FEED_LIVE = "live"
FEED_RISING = "rising"
FEED_TRENDING = "trending"
FEED_TOP_TODAY = "top_today"


def get_feed(
    session: Session,
    feed_type: str,
    rule_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Return tweets for the given feed. Filters and ordering per spec:
    - Live: ORDER BY created_at DESC
    - Rising: WHERE age < 2h, ORDER BY engagement_velocity DESC
    - Trending: WHERE age < 6h, ORDER BY engagement_score DESC
    - Top Today: WHERE age < 24h, ORDER BY engagement_score DESC
    """
    now = datetime.now(timezone.utc)
    q = session.query(Tweet)
    if rule_id is not None:
        q = q.filter(Tweet.rule_id == rule_id)

    if feed_type == FEED_LIVE:
        q = q.order_by(desc(Tweet.created_at))
    elif feed_type == FEED_RISING:
        cutoff = now - timedelta(hours=2)
        q = q.filter(Tweet.created_at >= cutoff).order_by(desc(Tweet.engagement_velocity))
    elif feed_type == FEED_TRENDING:
        cutoff = now - timedelta(hours=6)
        q = q.filter(Tweet.created_at >= cutoff).order_by(desc(Tweet.engagement_score))
    elif feed_type == FEED_TOP_TODAY:
        cutoff = now - timedelta(hours=24)
        q = q.filter(Tweet.created_at >= cutoff).order_by(desc(Tweet.engagement_score))
    else:
        logger.warning(f"Unknown feed_type={feed_type}, defaulting to live")
        q = q.order_by(desc(Tweet.created_at))

    rows = q.offset(offset).limit(limit).all()
    return [_tweet_to_dict(t) for t in rows]


def _tweet_to_dict(t: Tweet) -> Dict[str, Any]:
    return {
        "tweet_id": t.tweet_id,
        "rule_id": t.rule_id,
        "text": t.text,
        "author_id": t.author_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "first_seen_at": t.first_seen_at.isoformat() if t.first_seen_at else None,
        "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
        "first_seen_source": t.first_seen_source,
        "like_count": t.like_count,
        "reply_count": t.reply_count,
        "retweet_count": t.retweet_count,
        "view_count": t.view_count,
        "engagement_score": float(t.engagement_score) if t.engagement_score is not None else None,
        "engagement_velocity": float(t.engagement_velocity) if t.engagement_velocity is not None else None,
        "engagement_rate": float(t.engagement_rate) if t.engagement_rate is not None else None,
        "seen_count": t.seen_count,
    }
