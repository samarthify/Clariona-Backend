# X (Twitter) data flow – trace from stream to analysis

End-to-end path for X Filtered Stream tweets: collection → ingestion → DB → analysis worker.

---

## 1. Collection (X API → app)

| Step | Where | What happens |
|------|--------|----------------|
| 1.1 | `main.py` | If `X_STREAM_ENABLED` (default true), creates `XStreamRulesManager`, syncs rules to X API, then creates `XStreamCollector(ingestor)` and starts `x_stream_collector_task`. |
| 1.2 | `x_stream_collector.py` | `run_forever()` → `_run_stream()`. Opens long-lived GET to `https://api.x.com/2/tweets/search/stream` with `Bearer` token. |
| 1.3 | Same | Reads NDJSON line-by-line (`resp.iter_lines()`). For each line: `json.loads` → `_flatten_x_api_post(payload)` → flat dict with `url`, `text`, `date`, `platform=twitter`, `source=x_api_filtered_stream`, engagement, author. |
| 1.4 | Same | For each record with `url`: `self.ingestor.insert_record(record, commit=True, log_stored=False)`. Counts posts and logs every 10: “XStreamCollector: ingested N posts”. |
| 1.5 | Same | On stream error (e.g. “Response ended prematurely”): logs error, closes response, sleeps `reconnect_delay`, then reconnects (same loop). |

**Logs:** `logs/x_stream_collector.log` — e.g. “ingested 10 posts”, “ingested 20 posts”, “reconnecting in 5.0s”, errors.

---

## 2. Ingestion (record → DB)

| Step | Where | What happens |
|------|--------|----------------|
| 2.1 | `data_ingestor.py` | `insert_record(raw_record)` → `normalize_record(raw_record)`. |
| 2.2 | Same | Normalize: sets `run_timestamp = now` if missing, `processing_status = 'pending'` if missing, `platform`/`source` from X payload, maps X fields (e.g. `like_count`→`likes`, `impressions`→`direct_reach`). |
| 2.3 | Same | Upsert into `SentimentData` on `url` (unique). **New row:** insert with `processing_status='pending'`, `run_timestamp=now`. **Existing row:** update only engagement/user fields; `processing_status` and other PROTECTED_FIELDS are left unchanged. |
| 2.4 | Same | `commit=True` → `self.session.commit()` so the row is visible to other sessions (e.g. analysis worker) immediately. |

**Logs:** `logs/data_ingestor.log` — “Batch inserted N” from other collectors; X stream uses `insert_record` per tweet with `log_stored=False`, so you don’t see one line per X post there unless you add it.

**DB:** `sentiment_data` row: `url` (e.g. `https://x.com/i/status/...`), `platform=twitter`, `source=x_api_filtered_stream`, `processing_status=pending`, `run_timestamp`, `text`, etc.

---

## 3. Analysis worker (DB → sentiment/topics)

| Step | Where | What happens |
|------|--------|----------------|
| 3.1 | `analysis_worker.py` | `run_forever()` loop. Calls `_claim_records(limit)` via `asyncio.to_thread` (with 30s timeout). |
| 3.2 | Same | `_claim_records`: selects rows in `sentiment_data` with `processing_status='pending'` and (date or run_timestamp) in last 24h, ordered by date desc, entry_id desc, `limit` rows. Sets those rows to `processing_status='processing'` and commits. Returns list of stubs `{entry_id, text_content}`. |
| 3.3 | Same | For each stub, submits `_analyze_record(stub)` to the thread pool. Each task: loads record, runs sentiment agent, topic classifier, writes back sentiment/topics and sets `processing_status='completed'`. |
| 3.4 | Same | If `_claim_records` returns [] (no pending in 24h window): logs “No work; sleeping 2.0s” and keeps looping (never exits). |

**Logs:** `logs/analysis_worker.log` — “Claiming up to N pending records”, “Claimed N records”, “Submitted N tasks”, “✓ Analyzed [entry_id]”, “*** KEEPALIVE ***”, “No work; sleeping”.

---

## 4. Flow summary (one X tweet)

```
X API stream (NDJSON)
  → x_stream_collector._run_stream()
  → _flatten_x_api_post(payload)  →  record
  → ingestor.insert_record(record, commit=True)
       → normalize_record (run_timestamp, processing_status=pending)
       → upsert SentimentData ON url, commit
  → DB: sentiment_data row with processing_status='pending'

Analysis worker (separate asyncio task, separate DB sessions)
  → _claim_records(25)  →  SELECT pending, 24h window, UPDATE to 'processing'
  → _analyze_record(stub)  →  sentiment + topics, UPDATE to 'completed'
  → logs: "✓ Analyzed [entry_id] | Sentiment: X | Topics: N"
```

---

## 5. Where to look when debugging

| Symptom | Check |
|--------|--------|
| No X posts in app | `logs/x_stream_collector.log`: “ingested N posts” increasing? X_BEARER_TOKEN set? Stream errors / reconnect? |
| X posts in stream but not in DB | `data_ingestor`: normalize/insert errors (e.g. missing url). Optional: temporarily set `log_stored=True` for X in `x_stream_collector.py` to see “STORED in DB” in data_ingestor.log. |
| In DB but not analyzed | `analysis_worker.log`: “No pending records” vs “Claimed N records”. Confirm row has `processing_status='pending'` and `run_timestamp`/`date` within last 24h. |
| Analysis worker stops | Same log: “*** KEEPALIVE ***” every 10s? “No work; sleeping” when queue empty? Main service watchdog (main.py) restarts worker if task exits. |

---

## 6. Key files

| Path | Role |
|------|------|
| `src/services/main.py` | Wires ingestor, starts XStreamCollector and AnalysisWorker. |
| `src/services/x_stream_collector.py` | Stream client, flatten, `ingestor.insert_record()` per tweet. |
| `src/services/data_ingestor.py` | normalize_record, upsert SentimentData, sets pending. |
| `src/services/analysis_worker.py` | Polls pending, claims, analyzes, completes. |
| `src/api/models.py` | SentimentData (url, run_timestamp, processing_status, etc.). |
