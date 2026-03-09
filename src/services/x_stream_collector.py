"""
XStreamCollector - Connects to X API Filtered Stream and ingests posts.

Parses NDJSON stream, writes to tweets table (Layer 1), optionally to SentimentData via DataIngestor.
Uses same rules as x_stream_rules (matching_rules in payload -> rule_id).
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    from src.api.database import SessionLocal
    from src.services.data_ingestor import DataIngestor
except ImportError:
    pass

logger = logging.getLogger("services.x_stream_collector")

STREAM_URL = "https://api.x.com/2/tweets/search/stream"

# Optional dual-write to SentimentData (existing analysis pipeline)
X_STREAM_ALSO_INGEST_SENTIMENT = os.getenv("X_STREAM_ALSO_INGEST_SENTIMENT", "true").lower() == "true"


def _resolve_rule_id_from_matching_rules(session, matching_rules: List[Dict[str, Any]]) -> Optional[int]:
    """Map X API matching_rules (x_rule_id) to our x_stream_rules.id."""
    if not matching_rules or not session:
        return None
    from src.api.models import XStreamRule
    x_rule_id = matching_rules[0].get("id") if matching_rules else None
    if not x_rule_id:
        return None
    row = session.query(XStreamRule.id).filter(XStreamRule.x_rule_id == str(x_rule_id)).first()
    return row[0] if row else None


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
        logger.info("XStreamCollector started (X API Filtered Stream); connecting...")

        while self._running:
            if not self.bearer_token:
                logger.warning("X_BEARER_TOKEN not set - XStreamCollector idle (will retry in 60s)")
                await asyncio.sleep(60)
                continue

            try:
                logger.info("XStreamCollector connecting to %s ...", STREAM_URL)
                # Offload the blocking stream processing to a separate thread
                await asyncio.to_thread(self._run_stream_sync)
                if self._running:
                    logger.warning("XStreamCollector stream connection closed (will reconnect)")
            except asyncio.CancelledError:
                logger.info("XStreamCollector cancelled (shutting down)")
                break
            except Exception as e:
                logger.error("XStreamCollector error: %s", e, exc_info=True)

            if not self._running:
                break

            logger.info("XStreamCollector reconnecting in %.1fs (backoff max %.1fs)...", delay, self.backoff_max)
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, self.backoff_max)

        logger.info("XStreamCollector stopped.")

    def _run_stream_sync(self):
        """
        Connect to stream and process posts synchronously in a separate thread.
        Manages its own DB session to be thread-safe.
        """
        # Create a dedicated session for this stream connection
        with SessionLocal() as session:
            from src.api.models import XStreamRule
            active_rules = session.query(XStreamRule).filter(XStreamRule.is_active == True).count()
            # Create a dedicated ingestor for this thread
            thread_ingestor = DataIngestor(session, user_id=self.ingestor.user_id)

            resp = requests.get(
                STREAM_URL,
                headers=self._headers(),
                params=self._stream_params(),
                stream=True,
                timeout=90,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"Stream HTTP {resp.status_code}: {resp.text[:500]}")

            logger.info(
                "XStreamCollector connected (HTTP 200), %d active rules; streaming tweets (batch progress every 10).",
                active_rules,
            )
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

                    matching_rules = payload.get("matching_rules") or []
                    # Use the thread-local session
                    rule_id = _resolve_rule_id_from_matching_rules(session, matching_rules)

                    # Layer 1: always upsert into tweets table
                    try:
                        from src.services.x_tweets_store import (
                            parse_x_stream_payload_to_row,
                            upsert_tweet,
                            SOURCE_STREAM,
                        )
                        row = parse_x_stream_payload_to_row(payload, rule_id, first_seen_source=SOURCE_STREAM)
                        if row:
                            # Use thread-local session
                            upsert_tweet(session, row)
                            count += 1
                            if count % 10 == 0:
                                logger.info("XStreamCollector: tweets stored %d posts (this connection)", count)
                    except Exception as e:
                        logger.error(f"XStreamCollector tweets upsert error: {e}")

                    # Optional: also ingest into SentimentData for existing analysis pipeline
                    if X_STREAM_ALSO_INGEST_SENTIMENT:
                        record = _flatten_x_api_post(payload)
                        if record.get("url"):
                            try:
                                # Use thread-local ingestor
                                thread_ingestor.insert_record(record, commit=True, log_stored=False)
                            except Exception as e:
                                logger.error(f"XStreamCollector ingest error: {e}")
            finally:
                resp.close()

    def stop(self):
        """Stop the collector."""
        self._running = False
