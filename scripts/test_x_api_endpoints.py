#!/usr/bin/env python3
"""
Test script for X API Filtered Stream endpoints.

Tests:
  1. GET  /2/tweets/search/stream/rules  - List current rules
  2. POST /2/tweets/search/stream/rules  - Add rules
  3. POST /2/tweets/search/stream/rules  - Delete rules
  4. GET  /2/tweets/search/stream        - Connect to stream (receives a few posts)

Usage:
  1. Set X_BEARER_TOKEN in config/.env
  2. Run: python scripts/test_x_api_endpoints.py

Options:
  --stream-only N  : Skip rule tests, just connect to stream and print N posts (default: 3)
  --no-stream      : Test rules only, do not connect to stream
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load .env from config/ and project root
try:
    from dotenv import load_dotenv
    for env_path in [project_root / "config" / ".env", project_root / ".env"]:
        if env_path.exists():
            load_dotenv(env_path, override=False)
except ImportError:
    pass

import requests

BASE_URL = "https://api.x.com"
RULES_URL = f"{BASE_URL}/2/tweets/search/stream/rules"
STREAM_URL = f"{BASE_URL}/2/tweets/search/stream"


def get_bearer_token() -> str:
    """Get Bearer token from env."""
    token = os.environ.get("X_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
    if not token or token.strip() == "":
        print("ERROR: X_BEARER_TOKEN or BEARER_TOKEN not set.")
        print("Add it to config/.env and try again.")
        sys.exit(1)
    return token.strip()


def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Endpoint 1: GET rules ---
def test_get_rules(token: str) -> list:
    """GET /2/tweets/search/stream/rules - List current rules."""
    print("\n" + "=" * 60)
    print("1. GET /2/tweets/search/stream/rules")
    print("=" * 60)
    resp = requests.get(RULES_URL, headers=get_headers(token), timeout=10)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return []

    data = resp.json()
    rules = data.get("data") or []
    meta = data.get("meta", {})

    print(f"Rules count: {len(rules)}")
    if meta:
        print(f"Meta: {json.dumps(meta, indent=2)}")
    if rules:
        for r in rules:
            print(f"  - id={r.get('id')} tag={r.get('tag')} value={r.get('value')[:50]}...")

    return rules


# --- Endpoint 2: POST add rules ---
def test_add_rules(token: str, rules: list = None) -> list:
    """POST /2/tweets/search/stream/rules - Add rules."""
    print("\n" + "=" * 60)
    print("2. POST /2/tweets/search/stream/rules (add)")
    print("=" * 60)

    if rules is None:
        rules = [
            {"value": "cat has:images", "tag": "test-cats-images"},
            {"value": "(happy OR amazing) lang:en -is:retweet", "tag": "test-sentiment"},
        ]

    payload = {"add": rules}
    print(f"Adding rules: {json.dumps(payload, indent=2)}")

    resp = requests.post(RULES_URL, headers=get_headers(token), json=payload, timeout=10)
    print(f"Status: {resp.status_code}")

    if resp.status_code not in (200, 201):
        print(f"Error: {resp.text}")
        return []

    data = resp.json()
    meta = data.get("meta", {})
    errors = data.get("errors", [])

    if meta:
        print(f"Summary: {json.dumps(meta, indent=2)}")
    if errors:
        print(f"Errors: {json.dumps(errors, indent=2)}")

    # Response may include created rules with ids in data
    return data.get("data") or []


# --- Endpoint 3: POST delete rules ---
def test_delete_rules(token: str, rule_ids: list):
    """POST /2/tweets/search/stream/rules - Delete rules by ID."""
    print("\n" + "=" * 60)
    print("3. POST /2/tweets/search/stream/rules (delete)")
    print("=" * 60)

    if not rule_ids:
        print("No rule IDs to delete.")
        return

    payload = {"delete": {"ids": rule_ids}}
    print(f"Deleting rule IDs: {rule_ids}")

    resp = requests.post(RULES_URL, headers=get_headers(token), json=payload, timeout=10)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return

    data = resp.json()
    meta = data.get("meta", {})
    print(f"Result: {json.dumps(meta, indent=2)}")


# --- Endpoint 4: GET stream ---
def test_stream(token: str, max_posts: int = 3):
    """GET /2/tweets/search/stream - Connect and receive posts."""
    print("\n" + "=" * 60)
    print("4. GET /2/tweets/search/stream")
    print("=" * 60)
    print(f"Connecting... (will print up to {max_posts} posts, then exit)")
    print("Press Ctrl+C to stop earlier.\n")

    # Request fields for useful data
    params = {
        "tweet.fields": "created_at,author_id,text,public_metrics,lang",
        "expansions": "author_id",
        "user.fields": "username,name,profile_image_url",
    }

    try:
        resp = requests.get(
            STREAM_URL,
            headers=get_headers(token),
            params=params,
            stream=True,
            timeout=60,
        )

        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            print(resp.text)
            return

        count = 0
        for line in resp.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                try:
                    obj = json.loads(line_str)
                except json.JSONDecodeError:
                    print(f"Raw line: {line_str[:200]}...")
                    continue

                # Skip error objects (stream can send errors inline)
                if "errors" in obj:
                    print(f"Stream error: {obj}")
                    continue

                count += 1
                print(f"\n--- Post #{count} ---")
                print(json.dumps(obj, indent=2, default=str)[:1500])
                if count >= max_posts:
                    print(f"\nReceived {count} posts. Stopping.")
                    break
        else:
            if count == 0:
                print("No posts received. Rules may not match any recent activity, or stream may be quiet.")
            else:
                print(f"\nStream ended. Received {count} posts total.")

    except requests.exceptions.Timeout:
        print("Stream timeout (expected if no matching posts).")
    except KeyboardInterrupt:
        print("\nStopped by user.")


def main():
    parser = argparse.ArgumentParser(description="Test X API Filtered Stream endpoints")
    parser.add_argument("--stream-only", type=int, metavar="N", default=None,
                        help="Skip rule tests, just stream N posts (default: 3)")
    parser.add_argument("--no-stream", action="store_true", help="Test rules only, do not connect to stream")
    args = parser.parse_args()

    token = get_bearer_token()
    print("Bearer token found (masked).")

    if args.stream_only is not None:
        # Just stream
        test_stream(token, max_posts=args.stream_only)
        return

    # Full test: rules + stream
    existing_rules = test_get_rules(token)
    existing_ids = [r["id"] for r in existing_rules if r.get("id")]

    # Add test rules
    new_rules_data = test_add_rules(token)
    new_ids = [r["id"] for r in new_rules_data if r.get("id")]

    # Fallback: if add response didn't return ids, GET rules and find ours by tag
    if not new_ids:
        rules_after = test_get_rules(token)
        test_tags = {"test-cats-images", "test-sentiment"}
        new_ids = [r["id"] for r in rules_after if r.get("tag") in test_tags]

    if not args.no_stream:
        test_stream(token, max_posts=3)

    # Cleanup: delete the rules we added
    if new_ids:
        test_delete_rules(token, new_ids)

    # If there were existing rules, we deleted ours; if user had rules before, they're gone.
    # Re-add any that were there? No - we only delete what we added (new_ids).
    # Actually we're only deleting new_ids which we just created. Good.

    print("\n" + "=" * 60)
    print("Done. All endpoints tested.")
    print("=" * 60)


if __name__ == "__main__":
    main()
