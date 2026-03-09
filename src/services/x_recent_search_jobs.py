"""
X Recent Search jobs: Rising (20 min), Stabilization (30 min), Safety Net (6 h).

Same rules as Filtered Stream (x_stream_rules). Each job runs per active rule,
calls Recent Search with rule.value as query, upserts into tweets, updates throttling state.
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.api.models import XStreamRule, XRuleRunState
from src.services.x_recent_search_client import search_recent
from src.services.x_tweets_store import (
    SOURCE_RISING,
    SOURCE_SAFETY,
    SOURCE_STABLE,
    parse_x_stream_payload_to_row,
    upsert_tweets_batch,
)

logger = logging.getLogger("services.x_recent_search_jobs")

# Config (env or constants)
RISING_MIN_VIEWS = int(os.environ.get("X_RISING_MIN_VIEWS", "200"))
RISING_MIN_AGE_MINUTES = 10


def _get_existing_tweet_ids(session: Session, tweet_ids: List[str]) -> set:
    from src.api.models import Tweet
    if not tweet_ids:
        return set()
    existing = session.query(Tweet.tweet_id).filter(Tweet.tweet_id.in_(tweet_ids)).all()
    return {r[0] for r in existing}


def _get_or_create_run_state(session: Session, rule_id: int, layer: str) -> XRuleRunState:
    state = session.query(XRuleRunState).filter(
        XRuleRunState.rule_id == rule_id,
        XRuleRunState.layer == layer,
    ).first()
    if state is None:
        state = XRuleRunState(rule_id=rule_id, layer=layer)
        session.add(state)
        session.flush()
    return state


def _should_skip_rule(session: Session, rule_id: int, layer: str) -> bool:
    state = session.query(XRuleRunState).filter(
        XRuleRunState.rule_id == rule_id,
        XRuleRunState.layer == layer,
    ).first()
    if state is None or state.skip_until is None:
        return False
    now = datetime.now(timezone.utc)
    return now < state.skip_until


def _age_minutes(created_at: Any) -> Optional[float]:
    if not created_at:
        return None
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except Exception:
        return None


def run_rising(session: Session) -> Tuple[int, int]:
    """
    Rising layer: created_at between now-2h and now-5m, max_results=10, sort_order=relevancy.
    Optional filter: view_count > 200, age > 10 min. Returns (tweets_processed, rules_skipped).
    """
    now = datetime.now(timezone.utc)
    end_time = now - timedelta(minutes=5)
    start_time = now - timedelta(hours=2)
    rules = session.query(XStreamRule).filter(XStreamRule.is_active == True).all()
    processed = 0
    skipped = 0
    for rule in rules:
        if _should_skip_rule(session, rule.id, "rising"):
            skipped += 1
            continue
        payloads = search_recent(
            rule.value,
            start_time=start_time,
            end_time=end_time,
            max_results=10,
            sort_order="relevancy",
        )
        tweet_ids = []
        for p in payloads:
            d = p.get("data") or {}
            tid = d.get("id")
            if tid:
                tweet_ids.append(str(tid))
        existing = _get_existing_tweet_ids(session, tweet_ids)
        new_count = len(tweet_ids) - len(existing)

        rows = []
        for p in payloads:
            d = p.get("data") or {}
            view_count = (d.get("public_metrics") or {}).get("impression_count") or (d.get("public_metrics") or {}).get("view_count")
            age_min = _age_minutes(d.get("created_at"))
            if view_count is not None and view_count < RISING_MIN_VIEWS:
                continue
            if age_min is not None and age_min < RISING_MIN_AGE_MINUTES:
                continue
            row = parse_x_stream_payload_to_row(p, rule.id, SOURCE_RISING)
            if row:
                rows.append(row)
        if rows:
            upsert_tweets_batch(session, rows)
            processed += len(rows)

        state = _get_or_create_run_state(session, rule.id, "rising")
        state.last_run_at = now
        state.last_new_unique_count = new_count
        state.skip_until = (now + timedelta(minutes=20)) if new_count < 2 else None
        session.commit()

    return (processed, skipped)


def run_stabilization(session: Session) -> Tuple[int, int]:
    """
    Stabilization: created_at > now-6h, max_results=20. No strict filter.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=6)
    rules = session.query(XStreamRule).filter(XStreamRule.is_active == True).all()
    processed = 0
    skipped = 0
    for rule in rules:
        if _should_skip_rule(session, rule.id, "stable"):
            skipped += 1
            continue
        payloads = search_recent(
            rule.value,
            start_time=start_time,
            end_time=now,
            max_results=20,
            sort_order="relevancy",
        )
        tweet_ids = [str((p.get("data") or {}).get("id")) for p in payloads if (p.get("data") or {}).get("id")]
        existing = _get_existing_tweet_ids(session, tweet_ids)
        new_count = len(tweet_ids) - len(existing)

        rows = []
        for p in payloads:
            row = parse_x_stream_payload_to_row(p, rule.id, SOURCE_STABLE)
            if row:
                rows.append(row)
        if rows:
            upsert_tweets_batch(session, rows)
            processed += len(rows)

        state = _get_or_create_run_state(session, rule.id, "stable")
        state.last_run_at = now
        state.last_new_unique_count = new_count
        state.skip_until = (now + timedelta(minutes=30)) if new_count < 2 else None
        session.commit()

    return (processed, skipped)


def run_safety_net(session: Session) -> Tuple[int, int]:
    """
    Safety Net: created_at > now-24h, max_results=50. No filter.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=24)
    rules = session.query(XStreamRule).filter(XStreamRule.is_active == True).all()
    processed = 0
    skipped = 0
    for rule in rules:
        if _should_skip_rule(session, rule.id, "safety"):
            skipped += 1
            continue
        payloads = search_recent(
            rule.value,
            start_time=start_time,
            end_time=now,
            max_results=50,
            sort_order="relevancy",
        )
        tweet_ids = [str((p.get("data") or {}).get("id")) for p in payloads if (p.get("data") or {}).get("id")]
        existing = _get_existing_tweet_ids(session, tweet_ids)
        new_count = len(tweet_ids) - len(existing)

        rows = []
        for p in payloads:
            row = parse_x_stream_payload_to_row(p, rule.id, SOURCE_SAFETY)
            if row:
                rows.append(row)
        if rows:
            upsert_tweets_batch(session, rows)
            processed += len(rows)

        state = _get_or_create_run_state(session, rule.id, "safety")
        state.last_run_at = now
        state.last_new_unique_count = new_count
        state.skip_until = (now + timedelta(hours=6)) if new_count < 2 else None
        session.commit()

    return (processed, skipped)
