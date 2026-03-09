"""X Intelligence feeds API: Live, Rising, Trending, Top Today."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from services.x_feed_service import (
    get_feed,
    FEED_LIVE,
    FEED_RISING,
    FEED_TRENDING,
    FEED_TOP_TODAY,
)

router = APIRouter(prefix="/x", tags=["x-intelligence"])

VALID_FEEDS = (FEED_LIVE, FEED_RISING, FEED_TRENDING, FEED_TOP_TODAY)


@router.get("/feeds/{feed_type}")
def x_feed(
    feed_type: str,
    rule_id: int | None = Query(None, description="Filter by rule id"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get X tweets feed. feed_type: live | rising | trending | top_today.
    - Live: latest by created_at
    - Rising: age < 2h, ordered by engagement_velocity
    - Trending: age < 6h, ordered by engagement_score
    - Top Today: age < 24h, ordered by engagement_score
    """
    if feed_type not in VALID_FEEDS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid feed_type. Use one of: {', '.join(VALID_FEEDS)}",
        )
    items = get_feed(db, feed_type, rule_id=rule_id, limit=limit, offset=offset)
    return {"feed_type": feed_type, "count": len(items), "items": items}
