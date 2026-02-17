"""
XStreamCollector - Connects to X API Filtered Stream and ingests posts.

Parses NDJSON stream, transforms X API payloads to SentimentData shape,
and forwards to DataIngestor. Handles reconnect on disconnect.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load env
try:
    from dotenv import load_dotenv
    for p in [Path(__file__).resolve().parent.parent.parent / "config" / ".env",
              Path(__file__).resolve().parent.parent.parent / ".env"]:
        if p.exists():
            load_dotenv(p, override=False)
except ImportError:
    pass

logger = logging.getLogger("services.x_stream_collector")

STREAM_URL = "https://api.x.com/2/tweets/search/stream"


def _flatten_x_api_post(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform X API Filtered Stream payload to flat record for DataIngestor.
    X API format: { data: {...}, includes: { users: [...] }, matching_rules: [...] }
    """
    data = payload.get("data") or {}
    includes = payload.get("includes") or {}
    users = includes.get("users") or []
    users_by_id = {u["id"]: u for u in users}

    tweet_id = data.get("id")
    author_id = data.get("author_id")
    user = users_by_id.get(author_id) if author_id else None

    # Text: standard or note_tweet for long posts
    text = data.get("text") or ""
    note_tweet = data.get("note_tweet") or {}
    if isinstance(note_tweet, dict) and note_tweet.get("text"):
        text = note_tweet["text"]

    # Public metrics (X API snake_case)
    pm = data.get("public_metrics") or {}

    record = {
        "original_id": str(tweet_id) if tweet_id else None,
        "url": f"https://x.com/i/status/{tweet_id}" if tweet_id else None,
        "text": text or "",
        "date": data.get("created_at"),
        "published_at": data.get("created_at"),
        "platform": "twitter",
        "source": "x_api_filtered_stream",
        # Engagement - DataIngestor maps: like_count->likes, retweet_count->retweets,
        # reply_count->comments, impressions->direct_reach
        "like_count": pm.get("like_count"),
        "retweet_count": pm.get("retweet_count"),
        "reply_count": pm.get("reply_count"),
        "impressions": pm.get("impression_count"),  # ingestor checks "impressions" for direct_reach
        "quoteCount": pm.get("quote_count"),  # ingestor adds to comments
        "bookmarkCount": pm.get("bookmark_count"),  # ingestor adds to likes
        "language": data.get("lang"),  # SentimentData.language column
    }

    if user:
        record["author"] = {
            "username": user.get("username"),
            "name": user.get("name"),
            "profile_image_url": user.get("profile_image_url"),
        }
        record["user_handle"] = user.get("username")
        record["user_name"] = user.get("name")
        record["user_avatar"] = user.get("profile_image_url")
        record["user_location"] = user.get("location")

    return record


class XStreamCollector:
    """Connect to X Filtered Stream and ingest posts via DataIngestor."""

    def __init__(
        self,
        ingestor,
        bearer_token: Optional[str] = None,
        reconnect_delay: float = 5.0,
        backoff_max: float = 60.0,
    ):
        self.ingestor = ingestor
        self.bearer_token = bearer_token or os.environ.get("X_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
        self.reconnect_delay = reconnect_delay
        self.backoff_max = backoff_max
        self._running = False

    def _session(self) -> requests.Session:
        s = requests.Session()
        retries = Retry(total=0, backoff_factor=0)  # no retries for stream
        s.mount("https://", HTTPAdapter(max_retries=retries))
        return s

    def _stream_params(self) -> dict:
        return {
            "tweet.fields": "created_at,author_id,text,public_metrics,lang,note_tweet",
            "expansions": "author_id",
            "user.fields": "username,name,profile_image_url,location",
        }

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.bearer_token}"}

    async def run_forever(self):
        """Main loop: connect, stream, reconnect on disconnect."""
        self._running = True
        delay = self.reconnect_delay

        while self._running:
            if not self.bearer_token:
                logger.warning("X_BEARER_TOKEN not set - XStreamCollector idle")
                await asyncio.sleep(60)
                continue

            try:
                await self._run_stream()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"XStreamCollector error: {e}", exc_info=True)

            if not self._running:
                break

            logger.info(f"XStreamCollector reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, self.backoff_max)

        logger.info("XStreamCollector stopped.")

    async def _run_stream(self):
        """Connect to stream and process posts. Runs in executor to avoid blocking."""
        loop = asyncio.get_event_loop()

        def _sync_stream():
            resp = requests.get(
                STREAM_URL,
                headers=self._headers(),
                params=self._stream_params(),
                stream=True,
                timeout=90,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Stream HTTP {resp.status_code}: {resp.text[:500]}")
            return resp

        resp = await loop.run_in_executor(None, _sync_stream)
        count = 0

        try:
            for line in resp.iter_lines():
                if not self._running:
                    break
                if not line:
                    continue
                try:
                    payload = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                if "errors" in payload:
                    logger.warning(f"X stream error: {payload.get('errors')}")
                    continue

                record = _flatten_x_api_post(payload)
                if not record.get("url"):
                    continue

                try:
                    status = self.ingestor.insert_record(record, commit=True, log_stored=False)
                    count += 1
                    if count % 10 == 0:
                        logger.info(f"XStreamCollector: ingested {count} posts")
                except Exception as e:
                    logger.error(f"XStreamCollector ingest error: {e}")
        finally:
            resp.close()

    def stop(self):
        """Stop the collector."""
        self._running = False
