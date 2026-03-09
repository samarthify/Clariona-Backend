# X (Twitter) Data Ingestion Guide

How to ingest X data correctly into the Clariona database. This document describes how the X collector works so you can build an ingestor that follows the same patterns.

---

## 1. Overview

X data can be ingested into **two tables**:

| Table | Purpose | When to Use |
|-------|---------|-------------|
| **`tweets`** | Raw X posts from Filtered Stream or Recent Search. Used for X feeds, engagement scoring, deduplication. | Always — Layer 1, all X sources |
| **`sentiment_data`** | Unified content table for sentiment/topic analysis. Used by the analysis worker. | Optional — when you want posts analyzed for sentiment/topics |

The X Stream Collector does **both**:
1. **Layer 1 (always):** upsert into `tweets` via `x_tweets_store`
2. **Layer 2 (optional):** upsert into `sentiment_data` via `DataIngestor` (when `X_STREAM_ALSO_INGEST_SENTIMENT=true`)

---

## 2. X API Payload Shape

Both **Filtered Stream** and **Recent Search** return tweets in the same shape:

```json
{
  "data": {
    "id": "1234567890",
    "author_id": "9876543210",
    "text": "Tweet text here",
    "created_at": "2025-02-19T10:00:00.000Z",
    "lang": "en",
    "public_metrics": {
      "like_count": 10,
      "retweet_count": 2,
      "reply_count": 1,
      "impression_count": 500,
      "quote_count": 0
    },
    "note_tweet": { "text": "..." }
  },
  "includes": {
    "users": [
      {
        "id": "9876543210",
        "username": "handle",
        "name": "Display Name",
        "profile_image_url": "https://...",
        "location": "Lagos, Nigeria"
      }
    ]
  },
  "matching_rules": [{"id": "12345", "tag": "..."}]
}
```

- **Stream:** One NDJSON line per tweet.
- **Recent Search:** `data.data[]` array, each item merged with `includes.users` to form a single payload per tweet.

---

## 3. Layer 1: Ingesting into `tweets` Table

### 3.1 Row Format

Use `parse_x_stream_payload_to_row()` in `src/services/x_tweets_store.py`:

```python
from src.services.x_tweets_store import (
    parse_x_stream_payload_to_row,
    upsert_tweet,
    SOURCE_STREAM,   # or SOURCE_RISING, SOURCE_STABLE, SOURCE_SAFETY
)

payload = {"data": {...}, "includes": {"users": [...]}}  # X API shape
rule_id = 1  # x_stream_rules.id, or None
row = parse_x_stream_payload_to_row(payload, rule_id, first_seen_source=SOURCE_STREAM)
if row:
    upsert_tweet(session, row)
```

### 3.2 Tweet Row Fields

| Field | Source | Notes |
|-------|--------|-------|
| `tweet_id` | `data.id` | PK, string |
| `rule_id` | `x_stream_rules.id` from `matching_rules` | Nullable FK |
| `text` | `data.text` or `data.note_tweet.text` | Long posts use note_tweet |
| `author_id` | `data.author_id` | String |
| `created_at` | `data.created_at` | Parsed datetime |
| `first_seen_at` | `now()` | Set on insert only |
| `last_seen_at` | `now()` | Updated on every upsert |
| `first_seen_source` | `stream` \| `rising` \| `stable` \| `safety` | Never overwritten |
| `like_count` | `public_metrics.like_count` | |
| `reply_count` | `public_metrics.reply_count` | |
| `retweet_count` | `public_metrics.retweet_count` | |
| `view_count` | `public_metrics.impression_count` or `view_count` | |
| `engagement_score` | Computed: `likes + 2*retweets + 3*replies` | |
| `engagement_velocity` | `engagement_score / age_minutes` | |
| `engagement_rate` | `engagement_score / views` if views > 0 | |
| `seen_count` | Incremented on conflict | |

### 3.3 Upsert Behavior

- **On conflict (tweet_id):** Update metrics, `last_seen_at`, `seen_count`. Do **not** overwrite `first_seen_at` or `first_seen_source`.
- **Bonus:** `upsert_tweet` also calls `sync_engagement_to_sentiment_data` — if a matching `sentiment_data` row exists (by `original_id` or `url`), engagement is synced there too.

### 3.4 Rule ID Resolution

For Filtered Stream, resolve `matching_rules` to our `x_stream_rules.id`:

```python
def _resolve_rule_id(session, matching_rules):
    if not matching_rules:
        return None
    x_rule_id = matching_rules[0].get("id")  # X API rule ID
    from src.api.models import XStreamRule
    row = session.query(XStreamRule.id).filter(
        XStreamRule.x_rule_id == str(x_rule_id)
    ).first()
    return row[0] if row else None
```

---

## 4. Layer 2: Ingesting into `sentiment_data` (Analysis Pipeline)

### 4.1 Record Format

Use `_flatten_x_api_post()` in `src/services/x_stream_collector.py` to produce the flat record expected by `DataIngestor`:

```python
# In x_stream_collector.py
record = _flatten_x_api_post(payload)
```

### 4.2 Required Field Mappings (X API → SentimentData)

| SentimentData Field | Incoming Key(s) | Notes |
|---------------------|-----------------|-------|
| **url** (required) | Built: `https://x.com/i/status/{tweet_id}` | Must be present; upsert key |
| **text** | `data.text` or `data.note_tweet.text` | Fallback: title, content, description |
| **original_id** | `data.id` | For matching engagement sync |
| **date** | `data.created_at` | Parsed by ingestor |
| **published_at** | `data.created_at` | Same |
| **platform** | `"twitter"` | Fixed for X |
| **source** | `"x_api_filtered_stream"` or custom | Identifies ingestion path |
| **language** | `data.lang` | |

### 4.3 Engagement Field Mappings

`DataIngestor.normalize_record` maps these automatically. Use these **incoming** keys:

| Incoming Key | SentimentData Column |
|--------------|----------------------|
| `like_count` or `likeCount` | `likes` |
| `retweet_count` or `retweetCount` | `retweets` |
| `reply_count` or `replyCount` | `comments` |
| `impressions` or `impression_count` or `view_count` | `direct_reach` |
| `quoteCount` | Added to `comments` |
| `bookmarkCount` | Added to `likes` |

### 4.4 User Fields

| Incoming | SentimentData |
|----------|---------------|
| `user_handle` or `author.username` | `user_handle` |
| `user_name` or `author.name` | `user_name` |
| `user_avatar` or `author.profile_image_url` | `user_avatar` |
| `user_location` or `author.location` | `user_location` |

### 4.5 Flattened Record Example

```python
record = {
    "original_id": "1234567890",
    "url": "https://x.com/i/status/1234567890",
    "text": "Tweet text",
    "date": "2025-02-19T10:00:00.000Z",
    "published_at": "2025-02-19T10:00:00.000Z",
    "platform": "twitter",
    "source": "x_api_filtered_stream",
    "like_count": 10,
    "retweet_count": 2,
    "reply_count": 1,
    "impressions": 500,
    "quoteCount": 0,
    "bookmarkCount": 5,
    "language": "en",
    "user_handle": "handle",
    "user_name": "Display Name",
    "user_avatar": "https://...",
    "user_location": "Lagos, Nigeria",
}
```

### 4.6 Insert via DataIngestor

```python
from src.services.data_ingestor import DataIngestor

ingestor = DataIngestor(session, user_id=optional_user_id)
status = ingestor.insert_record(record, commit=True, log_stored=False)
# Returns: 'inserted' | 'updated' | 'failed'
```

### 4.7 Upsert Rules (SentimentData)

- **Conflict key:** `url` (unique)
- **UPDATABLE_FIELDS (always overwritten on conflict):** `likes`, `retweets`, `comments`, `direct_reach`, `cumulative_reach`, `domain_reach`, `user_avatar`, `user_name`, `user_handle`
- **PROTECTED_FIELDS (never overwritten):** `sentiment_label`, `sentiment_score`, `sentiment_justification`, `emotion_*`, `location_*`, `issue_*`, `processing_status`, `processing_completed_at`
- **BACKFILL_FIELDS (only if DB value is NULL):** `date`, `published_at`, `published_date`, `platform`
- **SINGLE_MODE_BACKFILL (only if NULL):** `source`, `source_url`, `title`, `description`, `content`, `text`, `user_location`

### 4.8 Analysis Worker Requirements

For a row to be picked up by the analysis worker:

- `processing_status = 'pending'` (ingestor sets this on new inserts)
- `date` or `run_timestamp` within last 24 hours

---

## 5. Step-by-Step: Building an X Ingestor

### 5.1 Filtered Stream Ingestor (like XStreamCollector)

1. **Connect** to `https://api.x.com/2/tweets/search/stream` with Bearer token.
2. **Stream params:** `tweet.fields=created_at,author_id,text,public_metrics,lang,note_tweet`, `expansions=author_id`, `user.fields=username,name,profile_image_url,location`.
3. **Read** NDJSON lines; skip `errors`, empty lines.
4. **For each payload:**
   - Resolve `rule_id` from `matching_rules` (optional).
   - **Layer 1:** `row = parse_x_stream_payload_to_row(payload, rule_id, SOURCE_STREAM)` → `upsert_tweet(session, row)`.
   - **Layer 2 (optional):** `record = _flatten_x_api_post(payload)` → `ingestor.insert_record(record, commit=True)`.
5. **Use a dedicated DB session** per connection (thread-safe).
6. **Reconnect** on stream disconnect with backoff.

### 5.2 Recent Search Ingestor (like x_recent_search_jobs)

1. **Call** `search_recent(query, start_time, end_time, max_results, sort_order)`.
2. **Normalize** each item to `{ "data": {...}, "includes": {"users": [...]} }` (same as stream).
3. **For each payload:**
   - `row = parse_x_stream_payload_to_row(payload, rule.id, SOURCE_RISING | SOURCE_STABLE | SOURCE_SAFETY)`.
   - `upsert_tweet(session, row)` or `upsert_tweets_batch(session, rows)`.
4. Optionally feed to SentimentData via `_flatten_x_api_post` + `insert_record`.

### 5.3 Batch / File Ingestor

1. **Parse** your source (CSV, JSON, API response) into X API-like payloads or flat records.
2. **For tweets table:** Build rows with `tweet_row_from_payload()` or equivalent, then `upsert_tweets_batch()`.
3. **For sentiment_data:** Build records with correct keys (see §4.2–4.5), then `insert_record()` per row or use `insert_records_batch()`.

---

## 6. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Missing `url` | Record is rejected. Use `https://x.com/i/status/{tweet_id}`. |
| Wrong date format | Use ISO 8601; `DataIngestor` parses via `parse_datetime()`. |
| Overwriting analysis | Never put sentiment/issue/processing fields in your input; they are PROTECTED. |
| Duplicate tweets | `tweets`: upsert on `tweet_id`; `sentiment_data`: upsert on `url`. Both deduplicate. |
| View count field | X API uses `impression_count`; map to `view_count` (tweets) or `impressions` → `direct_reach` (sentiment_data). |
| Note tweets | Check `data.note_tweet.text` for long posts; `parse_x_stream_payload_to_row` and `_flatten_x_api_post` both handle this. |

---

## 7. Reference: Key Files

| File | Role |
|------|------|
| `src/services/x_stream_collector.py` | Stream client, `_flatten_x_api_post`, dual-write logic |
| `src/services/x_tweets_store.py` | `parse_x_stream_payload_to_row`, `tweet_row_from_payload`, `upsert_tweet`, `upsert_tweets_batch`, `sync_engagement_to_sentiment_data` |
| `src/services/data_ingestor.py` | `normalize_record`, `insert_record`, field mappings, upsert rules |
| `src/services/x_recent_search_client.py` | `search_recent()` — returns normalized payloads |
| `src/services/x_recent_search_jobs.py` | Rising, Stable, Safety jobs — `parse_x_stream_payload_to_row` + `upsert_tweets_batch` |
| `src/api/models.py` | `Tweet`, `SentimentData`, `XStreamRule` |

---

## 8. Environment

| Variable | Purpose |
|----------|---------|
| `X_BEARER_TOKEN` | X API v2 Bearer token |
| `X_STREAM_ALSO_INGEST_SENTIMENT` | `true` (default) to also write to SentimentData |
| `X_STREAM_ENABLED` | Enable/disable X stream in main service |
