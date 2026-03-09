"""
X Recent Search API client - GET /2/tweets/search/recent.

Same rules (query = rule.value) as Filtered Stream. Used by Rising, Stabilization, Safety Net jobs.
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:
    from dotenv import load_dotenv
    for p in [Path(__file__).resolve().parent.parent.parent / "config" / ".env",
              Path(__file__).resolve().parent.parent.parent / ".env"]:
        if p.exists():
            load_dotenv(p, override=False)
except ImportError:
    pass

logger = logging.getLogger("services.x_recent_search_client")

BASE_URL = "https://api.x.com"
RECENT_SEARCH_URL = f"{BASE_URL}/2/tweets/search/recent"


def _format_time(dt: datetime) -> str:
    """ISO 8601 for X API (YYYY-MM-DDTHH:mm:ssZ)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def search_recent(
    query: str,
    *,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    max_results: int = 10,
    sort_order: Optional[str] = None,
    bearer_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Call GET /2/tweets/search/recent. Returns list of tweet payloads (data + includes).
    Each item is in same shape as Filtered Stream: { "data": {...}, "includes": { "users": [...] } }.
    """
    token = bearer_token or os.environ.get("X_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
    if not token:
        logger.warning("X_BEARER_TOKEN not set - cannot call Recent Search")
        return []

    params: Dict[str, Any] = {
        "query": query,
        "max_results": min(100, max(10, max_results)),
        "tweet.fields": "created_at,author_id,text,public_metrics,lang,note_tweet",
        "expansions": "author_id",
        "user.fields": "username,name,profile_image_url,location",
    }
    if start_time is not None:
        params["start_time"] = _format_time(start_time)
    if end_time is not None:
        params["end_time"] = _format_time(end_time)
    if sort_order is not None:
        params["sort_order"] = sort_order

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(RECENT_SEARCH_URL, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            logger.error(f"X Recent Search HTTP {resp.status_code}: {resp.text[:500]}")
            return []
        data = resp.json()
    except Exception as e:
        logger.error(f"X Recent Search request error: {e}")
        return []

    tweets_data = data.get("data") or []
    includes = data.get("includes") or {}
    users = includes.get("users") or []
    users_by_id = {u["id"]: u for u in users}

    # Normalize to same shape as stream: one payload per tweet with data + includes
    result: List[Dict[str, Any]] = []
    for t in tweets_data:
        author_id = t.get("author_id")
        user_list = [users_by_id[author_id]] if author_id and author_id in users_by_id else []
        result.append({
            "data": t,
            "includes": {"users": user_list},
        })
    return result
