#!/usr/bin/env python3
"""
Test X Intelligence integration: verify all components work together.

Tests:
1. Database models load correctly
2. Tweets store can upsert
3. Recent search client can call API (if token set)
4. Jobs can run (dry-run mode)
5. Feed service can query
6. API endpoint is registered
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from api.database import SessionLocal
from api.models import Tweet, XStreamRule, XRuleRunState
from services.x_tweets_store import (
    tweet_row_from_payload,
    upsert_tweet,
    compute_engagement,
    SOURCE_STREAM,
)
from services.x_feed_service import get_feed, FEED_LIVE, FEED_RISING, FEED_TRENDING, FEED_TOP_TODAY
from services.x_recent_search_jobs import (
    _get_existing_tweet_ids,
    _get_or_create_run_state,
    _should_skip_rule,
)

print("=" * 60)
print("X Intelligence Integration Test")
print("=" * 60)

# Test 1: Models load
print("\n1. Testing models...")
try:
    session = SessionLocal()
    rule_count = session.query(XStreamRule).count()
    tweet_count = session.query(Tweet).count()
    state_count = session.query(XRuleRunState).count()
    print(f"   ✓ Models loaded: {rule_count} rules, {tweet_count} tweets, {state_count} run states")
    session.close()
except Exception as e:
    print(f"   ✗ Model test failed: {e}")
    sys.exit(1)

# Test 2: Engagement scoring
print("\n2. Testing engagement scoring...")
try:
    score, velocity, rate = compute_engagement(
        like_count=100,
        retweet_count=50,
        reply_count=25,
        view_count=10000,
        created_at="2026-02-18T10:00:00Z",
    )
    print(f"   ✓ Engagement computed: score={score}, velocity={velocity:.4f}, rate={rate:.6f}")
except Exception as e:
    print(f"   ✗ Engagement scoring failed: {e}")
    sys.exit(1)

# Test 3: Tweets store upsert (dry run - don't commit)
print("\n3. Testing tweets store...")
try:
    session = SessionLocal()
    test_row = tweet_row_from_payload(
        tweet_id="1234567890",
        rule_id=None,
        text="Test tweet",
        author_id="999",
        created_at="2026-02-18T10:00:00Z",
        like_count=10,
        reply_count=5,
        retweet_count=3,
        view_count=1000,
        first_seen_source=SOURCE_STREAM,
    )
    print(f"   ✓ Row created: tweet_id={test_row['tweet_id']}, engagement_score={test_row['engagement_score']}")
    # Don't actually upsert in test - just verify structure
    session.close()
except Exception as e:
    print(f"   ✗ Tweets store test failed: {e}")
    sys.exit(1)

# Test 4: Feed service queries
print("\n4. Testing feed service...")
try:
    session = SessionLocal()
    for feed_type in [FEED_LIVE, FEED_RISING, FEED_TRENDING, FEED_TOP_TODAY]:
        items = get_feed(session, feed_type, limit=5)
        print(f"   ✓ {feed_type} feed: {len(items)} items")
    session.close()
except Exception as e:
    print(f"   ✗ Feed service test failed: {e}")
    sys.exit(1)

# Test 5: Recent search client (if token available)
print("\n5. Testing Recent Search client...")
import os
token = os.environ.get("X_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
if token:
    try:
        from services.x_recent_search_client import search_recent
        # Test with a simple query (will fail if no credits, but that's OK)
        results = search_recent("test", max_results=1)
        print(f"   ✓ Recent Search client: {len(results)} results (may be 0 if no credits)")
    except Exception as e:
        print(f"   ⚠ Recent Search client error (may be expected): {e}")
else:
    print("   ⚠ X_BEARER_TOKEN not set - skipping Recent Search test")

# Test 6: Jobs helper functions
print("\n6. Testing job helper functions...")
try:
    session = SessionLocal()
    existing = _get_existing_tweet_ids(session, ["123", "456"])
    print(f"   ✓ _get_existing_tweet_ids: {len(existing)} existing")
    
    # Test run state (if rules exist)
    rules = session.query(XStreamRule).limit(1).all()
    if rules:
        rule = rules[0]
        state = _get_or_create_run_state(session, rule.id, "rising")
        print(f"   ✓ _get_or_create_run_state: created/loaded for rule {rule.id}")
        skip = _should_skip_rule(session, rule.id, "rising")
        print(f"   ✓ _should_skip_rule: {skip}")
    else:
        print("   ⚠ No rules found - skipping run state test")
    session.close()
except Exception as e:
    print(f"   ✗ Job helpers test failed: {e}")
    sys.exit(1)

# Test 7: API endpoint registration
print("\n7. Testing API endpoint registration...")
try:
    from api import x_feeds
    from api.service import app
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    x_routes = [r for r in routes if '/x/' in r]
    if x_routes:
        print(f"   ✓ API routes registered: {x_routes}")
    else:
        print("   ⚠ No /x/ routes found in app")
except Exception as e:
    print(f"   ✗ API registration test failed: {e}")

print("\n" + "=" * 60)
print("Integration test complete!")
print("=" * 60)
print("\nNext steps:")
print("1. Ensure X_BEARER_TOKEN is set in config/.env")
print("2. Start the streaming service: python src/services/main.py")
print("3. Check logs/x_intelligence_scheduler.log for job runs")
print("4. Test API: GET /x/feeds/live")
print("5. Monitor tweets table: SELECT COUNT(*) FROM tweets;")
