"""
X Tweets Store - Upsert X posts into the tweets table with engagement scoring.

Used by Filtered Stream (Layer 1) and Recent Search jobs (Layers 2-4).
ON CONFLICT (tweet_id): update metrics, last_seen_at, increment seen_count;
never overwrite first_seen_at or first_seen_source.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.api.models import Tweet, SentimentData

logger = logging.getLogger("services.x_tweets_store")

# First-seen source constants (same as plan)
SOURCE_STREAM = "stream"
SOURCE_RISING = "rising"
SOURCE_STABLE = "stable"
SOURCE_SAFETY = "safety"


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (TypeError, ValueError):
        return None


def compute_engagement(
    like_count: Optional[int],
    retweet_count: Optional[int],
    reply_count: Optional[int],
    view_count: Optional[int],
    created_at: Optional[datetime],
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Compute raw score, velocity, and optional engagement_rate.
    Returns (engagement_score, engagement_velocity, engagement_rate).
    """
    likes = _safe_int(like_count) or 0
    retweets = _safe_int(retweet_count) or 0
    replies = _safe_int(reply_count) or 0
    raw = likes + 2 * retweets + 3 * replies
    engagement_score = Decimal(raw) if raw else None

    engagement_velocity = None
    if engagement_score is not None and created_at:
        try:
            if isinstance(created_at, str):
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                created_dt = created_at
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_seconds = (now - created_dt).total_seconds()
            age_minutes = max(1, age_seconds / 60.0)
            engagement_velocity = (engagement_score / Decimal(str(age_minutes))).quantize(Decimal("0.000001"))
        except Exception:
            pass

    engagement_rate = None
    if engagement_score is not None and view_count is not None:
        views = _safe_int(view_count) or 0
        if views > 0:
            engagement_rate = (engagement_score / Decimal(views)).quantize(Decimal("0.00000001"))

    return (engagement_score, engagement_velocity, engagement_rate)


def tweet_row_from_payload(
    tweet_id: str,
    rule_id: Optional[int],
    text: Optional[str],
    author_id: Optional[str],
    created_at: Any,
    like_count: Optional[int],
    reply_count: Optional[int],
    retweet_count: Optional[int],
    view_count: Optional[int],
    first_seen_source: str,
) -> Dict[str, Any]:
    """Build a dict suitable for upsert (includes computed engagement fields)."""
    engagement_score, engagement_velocity, engagement_rate = compute_engagement(
        like_count, retweet_count, reply_count, view_count, created_at
    )
    now = datetime.now(timezone.utc)
    return {
        "tweet_id": str(tweet_id),
        "rule_id": rule_id,
        "text": text,
        "author_id": str(author_id) if author_id else None,
        "created_at": created_at,
        "first_seen_at": now,
        "last_seen_at": now,
        "first_seen_source": first_seen_source,
        "like_count": _safe_int(like_count),
        "reply_count": _safe_int(reply_count),
        "retweet_count": _safe_int(retweet_count),
        "view_count": _safe_int(view_count),
        "engagement_score": engagement_score,
        "engagement_velocity": engagement_velocity,
        "engagement_rate": engagement_rate,
        "last_metrics_update_at": now,
        "seen_count": 1,
    }


def sync_engagement_to_sentiment_data(
    session: Session,
    tweet_id: str,
    like_count: Optional[int],
    reply_count: Optional[int],
    retweet_count: Optional[int],
    view_count: Optional[int],
) -> int:
    """
    Update sentiment_data engagement for the same post (matched by original_id or url).
    Returns number of rows updated (0 or 1). Keeps stream-origin posts in sentiment_data in sync with tweets.
    """
    try:
        updated = session.query(SentimentData).filter(
            (SentimentData.original_id == tweet_id) | (SentimentData.url == f"https://x.com/i/status/{tweet_id}")
        ).update(
            {
                "likes": like_count,
                "comments": reply_count,
                "retweets": retweet_count,
                "direct_reach": view_count,
            },
            synchronize_session=False,
        )
        return updated
    except Exception as e:
        logger.debug("sync_engagement_to_sentiment_data: %s", e)
        return 0


def upsert_tweet(session: Session, row: Dict[str, Any]) -> str:
    """
    Insert or update one tweet. On conflict (tweet_id): update metrics, last_seen_at, increment seen_count.
    Also syncs engagement to sentiment_data if that row exists (so stream-origin posts stay up to date).
    Returns: 'inserted' | 'updated'.
    """
    stmt = pg_insert(Tweet).values(**row)
    update_dict = {
        "rule_id": stmt.excluded.rule_id,
        "text": stmt.excluded.text,
        "author_id": stmt.excluded.author_id,
        "like_count": stmt.excluded.like_count,
        "reply_count": stmt.excluded.reply_count,
        "retweet_count": stmt.excluded.retweet_count,
        "view_count": stmt.excluded.view_count,
        "engagement_score": stmt.excluded.engagement_score,
        "engagement_velocity": stmt.excluded.engagement_velocity,
        "engagement_rate": stmt.excluded.engagement_rate,
        "last_metrics_update_at": stmt.excluded.last_metrics_update_at,
        "last_seen_at": stmt.excluded.last_seen_at,
        "seen_count": text("tweets.seen_count + 1"),
    }
    stmt = stmt.on_conflict_do_update(index_elements=["tweet_id"], set_=update_dict)
    session.execute(stmt)
    # Keep sentiment_data in sync: same post may have been ingested from stream
    sync_engagement_to_sentiment_data(
        session,
        row["tweet_id"],
        row.get("like_count"),
        row.get("reply_count"),
        row.get("retweet_count"),
        row.get("view_count"),
    )
    session.commit()
    return "updated"


def upsert_tweets_batch(session: Session, rows: List[Dict[str, Any]]) -> int:
    """
    Batch upsert. On conflict: same as single upsert. Also syncs engagement to sentiment_data for each row.
    Returns number of rows processed.
    """
    if not rows:
        return 0
    for row in rows:
        stmt = pg_insert(Tweet).values(**row)
        update_dict = {
            "rule_id": stmt.excluded.rule_id,
            "text": stmt.excluded.text,
            "author_id": stmt.excluded.author_id,
            "like_count": stmt.excluded.like_count,
            "reply_count": stmt.excluded.reply_count,
            "retweet_count": stmt.excluded.retweet_count,
            "view_count": stmt.excluded.view_count,
            "engagement_score": stmt.excluded.engagement_score,
            "engagement_velocity": stmt.excluded.engagement_velocity,
            "engagement_rate": stmt.excluded.engagement_rate,
            "last_metrics_update_at": stmt.excluded.last_metrics_update_at,
            "last_seen_at": stmt.excluded.last_seen_at,
            "seen_count": text("tweets.seen_count + 1"),
        }
        stmt = stmt.on_conflict_do_update(index_elements=["tweet_id"], set_=update_dict)
        session.execute(stmt)
        sync_engagement_to_sentiment_data(
            session,
            row["tweet_id"],
            row.get("like_count"),
            row.get("reply_count"),
            row.get("retweet_count"),
            row.get("view_count"),
        )
    session.commit()
    return len(rows)


def parse_x_stream_payload_to_row(
    payload: Dict[str, Any],
    rule_id: Optional[int],
    first_seen_source: str = SOURCE_STREAM,
) -> Optional[Dict[str, Any]]:
    """
    From X API Filtered Stream (or Recent Search) payload, build a row for tweets table.
    Expects payload with data.id, data.author_id, data.text, data.created_at, data.public_metrics.
    """
    data = payload.get("data") or {}
    tweet_id = data.get("id")
    if not tweet_id:
        return None
    tweet_id = str(tweet_id)
    pm = data.get("public_metrics") or {}
    text = data.get("text") or ""
    note_tweet = data.get("note_tweet") or {}
    if isinstance(note_tweet, dict) and note_tweet.get("text"):
        text = note_tweet.get("text") or text
    created_at = data.get("created_at")
    view_count = pm.get("impression_count") or pm.get("view_count")
    return tweet_row_from_payload(
        tweet_id=tweet_id,
        rule_id=rule_id,
        text=text,
        author_id=data.get("author_id"),
        created_at=created_at,
        like_count=pm.get("like_count"),
        reply_count=pm.get("reply_count"),
        retweet_count=pm.get("retweet_count"),
        view_count=view_count,
        first_seen_source=first_seen_source,
    )
