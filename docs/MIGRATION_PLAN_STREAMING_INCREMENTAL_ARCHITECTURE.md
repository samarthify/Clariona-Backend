# Migration Plan: Streaming Incremental Architecture

This plan aligns the **production-grade streaming architecture** (ingestion → queue → analysis → incremental cluster assigner → PostgreSQL + pgvector) with the **current Clariona system**, retaining all existing tables, APIs, and behaviour. Nothing is removed until the new path is proven; migrations are additive and backward-compatible.

---

## Design goal

**From:** Batch recomputation over stored mentions (poll DB → re-scan → DBSCAN → promote).  
**To:** Streaming incremental intelligence (event-driven analysis → one write → incremental cluster assignment → indexed lookups).

Existing behaviour (topic classification, sentiment, issues, promotion, owner configs, APIs) is preserved; only the **data flow** and **clustering model** change.

---

## Current system mapping (retained)

| Concept in new architecture | Current Clariona mapping | Retained as-is |
|-----------------------------|---------------------------|----------------|
| Mention                     | `sentiment_data` (PK `entry_id`) | Yes |
| Mention embedding           | `sentiment_embeddings` (embedding JSONB) | Yes; add optional `embedding_vec` for pgvector |
| Topic per mention           | `mention_topics` (mention_id, topic_key, topic_confidence, …) | Yes |
| Cluster                     | `processing_clusters` (id, topic_key, centroid, size, status) | Yes; add vector column for centroid |
| Mention ↔ cluster           | `cluster_mentions` (cluster_id, mention_id) | Yes |
| Issue (promoted cluster)    | `topic_issues` + `issue_mentions` | Yes |
| Tenant / owner              | `user_id` on `sentiment_data`; `owner_configs` (topics per owner) | Yes |
| Ingestion                   | DataIngestor, DatasetTailer, XStreamCollector, local collectors | Yes; add enqueue step |

All existing APIs, dashboard queries, and config flows (OwnerConfig, SystemConfiguration, etc.) continue to work against these tables.

---

## Target high-level flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Ingestion (unchanged entry points)                                         │
│  DatasetTailer / XStreamCollector / LocalScheduler → DataIngestor           │
└─────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Option A: Write minimal row + enqueue(entry_id)                            │
│  Option B: Write full raw row + enqueue(entry_id)  [current + queue]         │
└─────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Message queue  (Redis Streams / PG NOTIFY / Kafka)                         │
│  Stream: e.g. "analysis_pending" → { entry_id, [topic_keys], ... }          │
└─────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Analysis worker (stateless consumer)                                       │
│  Read row once by entry_id → embedding + sentiment + topic                   │
│  → Write once: sentiment_data + sentiment_embeddings + mention_topics       │
│  → Enqueue "cluster_pending" { entry_id, topic_key, embedding }              │
└─────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Incremental cluster assigner (replaces batch DBSCAN)                        │
│  For each event: fetch active clusters (topic) by vector distance (pgvector) │
│  → Assign to best cluster if distance < threshold else create cluster      │
│  → Update centroid incrementally; set sentiment_data.cluster_id             │
│  → Insert cluster_mentions row                                               │
└─────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Promotion (unchanged conceptually, lower frequency)                         │
│  Scan processing_clusters (active, by topic) → promote to topic_issues      │
│  when criteria met; create issue_mentions from cluster_mentions             │
│  No re-scan of all mentions; use cluster_id / cluster_mentions only         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Schema and queue (additive only)

### 1.1 Add columns (no drops)

- **sentiment_data**
  - `cluster_id UUID NULL REFERENCES processing_clusters(id) ON DELETE SET NULL`  
  - Index: `(cluster_id)` and optionally `(processing_status, created_at)` for backfill.
- **sentiment_embeddings**
  - `embedding_vec vector(1536) NULL` (pgvector; optional, for distance queries).  
  - Keep `embedding` JSONB for now; backfill `embedding_vec` from `embedding` and use it in the assigner.
- **processing_clusters**
  - `centroid_vec vector(1536) NULL` (pgvector).  
  - Keep `centroid` JSONB for now; maintain both until migration is done.  
  - Add index: `CREATE INDEX ON processing_clusters USING ivfflat (centroid_vec vector_cosine_ops) WITH (lists = 100);` (or HNSW) for `WHERE topic_key = ? AND status = 'active' ORDER BY centroid_vec <-> :embedding LIMIT K`.

Add Alembic migration(s); all existing code paths ignore new columns until used.

### 1.2 Message queue

- **Choice 1 (simplest):** PostgreSQL `LISTEN/NOTIFY` with a small helper table `analysis_queue (entry_id, created_at)` or `INSERT … RETURNING` + NOTIFY. Analysis worker uses `SELECT … FOR UPDATE SKIP LOCKED` and processes by `entry_id`.
- **Choice 2:** Redis Streams stream `analysis_pending`; producers XADD after insert; workers XREADGROUP.
- **Choice 3:** Kafka topic(s) for scale.

Recommendation: start with **Choice 1** (PG) so no new infra; switch to Redis/Kafka later if needed. No change to ingestion API: still call `DataIngestor.insert_record` / `insert_batch`; inside the ingestor, after a successful insert/upsert, enqueue `entry_id` (or list of ids for batch).

---

## Phase 2: Analysis worker (consume, single read, single write)

### 2.1 Current behaviour (retained conceptually)

- Input: rows in `sentiment_data` with `processing_status = 'pending'` (and optional 24h window).
- For each row: run sentiment (and embedding), topic classification, then write:
  - `sentiment_data`: sentiment_label, sentiment_score, emotion_*, influence_weight, processing_status, etc.
  - `sentiment_embeddings`: embedding (and when present, `embedding_vec`).
  - `mention_topics`: one row per (mention_id, topic_key) with topic_confidence, keyword_score, embedding_score.

### 2.2 New behaviour (same logic, different trigger)

- **Trigger:** consume from queue (e.g. get `entry_id` from PG queue table or Redis/Kafka).
- **Single read:** `SELECT … FROM sentiment_data WHERE entry_id = :id` (and optionally join sentiment_embeddings if we need to avoid overwriting). Fetch only columns needed for analysis (text, content, title, description, date, source_type, etc.).
- **Compute:** same as today: embedding model → topic classifier (with embedding) → sentiment/emotion.
- **Single write:** one transaction:
  - UPDATE sentiment_data SET sentiment_label = …, processing_status = 'completed', …
  - INSERT/UPDATE sentiment_embeddings (embedding, embedding_vec if used).
  - INSERT mention_topics (bulk for all topic_keys).
- **Then:** enqueue for cluster assigner: e.g. `{ entry_id, topic_keys[], embedding }` or just `entry_id` (assigner loads embedding from DB). Prefer passing embedding in the event to avoid an extra read in the assigner.

Existing AnalysisWorker can stay in parallel: either it only processes rows that were **not** enqueued (e.g. backfill), or we switch it off once queue-based throughput is sufficient. That way nothing breaks.

---

## Phase 3: Incremental cluster assigner (replaces batch DBSCAN)

### 3.1 Input

- Event: `{ entry_id, topic_key, embedding }` (or entry_id; then assigner loads embedding once from sentiment_embeddings.embedding_vec or embedding).

### 3.2 Algorithm (per mention, per topic)

- **Step 1:** Fetch active clusters for topic (pgvector):

  ```sql
  SELECT id, centroid_vec, size
  FROM processing_clusters
  WHERE topic_key = :topic_key AND status = 'active'
  ORDER BY centroid_vec <-> :embedding
  LIMIT 5;
  ```

- **Step 2:** If best distance < threshold (e.g. 1 - cosine_sim >= threshold → use cosine distance):  
  - Assign mention to that cluster:  
    - UPDATE sentiment_data SET cluster_id = :cluster_id WHERE entry_id = :entry_id.  
    - INSERT cluster_mentions (cluster_id, mention_id, similarity_score).  
  - Update cluster centroid incrementally:

    ```text
    new_centroid = (old_centroid * size + new_embedding) / (size + 1)
    ```

    UPDATE processing_clusters SET centroid = :new_centroid, centroid_vec = :new_centroid_vec, size = size + 1, updated_at = now() WHERE id = :cluster_id.  
  - Keep `centroid` JSONB in sync for backward compatibility.

- **Step 3:** Else (no close cluster):  
  - INSERT new row in processing_clusters (topic_key, centroid_vec = embedding, centroid = embedding::jsonb, size = 1, status = 'active').  
  - UPDATE sentiment_data SET cluster_id = :new_cluster_id.  
  - INSERT cluster_mentions (cluster_id, mention_id, similarity_score = 1.0).

All in one transaction per mention (or per batch of mentions for same topic to reduce round-trips). No full table scan; no NOT EXISTS over cluster_mentions + processing_clusters for “unprocessed”.

### 3.3 Cluster lifecycle (retained and clarified)

- **Seal cluster:** when `last_updated` older than X hours or size >= max_size, set `status = 'sealed'` (or keep `expired`). New mentions no longer assigned to it.
- **Promotion:** existing promotion logic runs on `processing_clusters` with status `active`; creates/updates `topic_issues` and `issue_mentions` from `cluster_mentions`. No change to TopicIssue/IssueMention schema; only the source of “which mentions belong to which cluster” changes from batch DBSCAN to incremental assignment.

---

## Phase 4: Ingestion integration (no breaking changes)

### 4.1 DataIngestor

- After successful `insert_record` or `insert_batch`: for each inserted/updated `entry_id`, enqueue that id (and optionally topic_hint/source if we have it) to the analysis queue.  
- Behaviour of `insert_record` / `insert_batch` (normalize, upsert, PROTECTED_FIELDS, etc.) unchanged.

### 4.2 DatasetTailer, XStreamCollector, local collectors

- No API change: they still call `ingestor.insert_batch` or `ingestor.insert_record`. Only the ingestor’s internal “post-commit” step adds an enqueue. If queue is down, either log and retry or fall back to “analysis worker polls by processing_status” so ingestion still succeeds.

---

## Phase 5: Promotion and issue detection (keep behaviour, remove batch re-scan)

### 5.1 What stays

- Promotion: select from `processing_clusters` where status = 'active', rank by size/density/growth, promote to `topic_issues`, create `issue_mentions` from `cluster_mentions`.  
- Merge similar issues (by centroid), archive excess issues, backfill labels/summaries for issues.  
- All of this can run on a **timer** (e.g. every 5–15 min) but without re-scanning `sentiment_data` or re-running DBSCAN.

### 5.2 What is removed (after incremental assigner is stable)

- **Removed:** `_get_unprocessed_mentions` (the NOT EXISTS over cluster_mentions + processing_clusters) and the batch DBSCAN loop in `detect_issues`.  
- **Removed:** Periodic “detect_issues_for_all_topics” that drains all unprocessed mentions per topic.  
- **Kept:** Promotion job that (1) reads `processing_clusters` (and optionally topic_issues for merge), (2) creates/updates topic_issues and issue_mentions from cluster_mentions, (3) backfills labels/summaries. This job no longer needs to read sentiment_data or sentiment_embeddings except for backfill (e.g. LLM summary), and only for the few promoted issues.

---

## Phase 6: Backfill and dual run

### 6.1 Existing rows without cluster_id

- Backfill job: select sentiment_data.entry_id where cluster_id IS NULL and processing_status = 'completed' (and optional date window), in batches (e.g. 500). For each batch, load embedding (from sentiment_embeddings.embedding_vec or embedding), then run the **same incremental assigner logic** (fetch clusters by vector distance, assign or create). This is O(K) per mention, not O(N²).  
- Optionally backfill during low load so it doesn’t contend with live traffic.

### 6.2 Dual run

- Run **incremental assigner** in parallel with the existing issue detection loop.  
- Use a flag or config: “use_incremental_clustering = true” for new mentions (enqueued), and let batch loop only process “old” mentions (e.g. where cluster_id IS NULL and created_at < cutover_date).  
- Compare counts: mentions with cluster_id set by assigner vs by batch; then switch off batch loop and remove `_get_unprocessed_mentions` / DBSCAN from the hot path.

---

## What we eliminate (without breaking existing behaviour)

- Write → read loop for “what is unprocessed?” (replaced by queue + cluster_id).
- Batch DBSCAN over all mentions in a window (replaced by incremental assign).
- Correlated NOT EXISTS on cluster_mentions + processing_clusters (no longer needed for “unprocessed”).
- Repeated full-table scans of sentiment_embeddings for clustering (replaced by indexed vector lookup and single-row updates).
- O(N²) similarity in batch; replaced by O(K) per mention.

---

## What we keep

- All tables and columns (additive only: cluster_id, embedding_vec, centroid_vec).
- All APIs and dashboard queries.
- Topic classification and MentionTopic.
- Sentiment, emotion, influence_weight, processing_status.
- TopicIssue, IssueMention, ProcessingCluster, ClusterMention.
- OwnerConfig, user_id, multi-owner topic filtering.
- DataIngestor contract (insert_record, insert_batch, normalize, upsert).
- Promotion and merge logic (operating on clusters and cluster_mentions).

---

## Implementation order (summary)

1. **Schema:** Add `sentiment_data.cluster_id`, `sentiment_embeddings.embedding_vec`, `processing_clusters.centroid_vec`; create vector index(s).  
2. **Queue:** Implement PG-based or Redis/Kafka queue; enqueue in DataIngestor after insert.  
3. **Analysis worker (queue-driven):** Consume by entry_id, single read, single write, enqueue for assigner.  
4. **Incremental assigner:** New service: consume events, pgvector nearest-cluster, assign or create, update centroid incrementally, write cluster_id and cluster_mentions.  
5. **Promotion:** Keep current promotion code; ensure it uses only cluster_mentions and processing_clusters (no re-scan of sentiment_data for “unprocessed”).  
6. **Backfill:** Batch backfill of cluster_id for existing rows using same assigner logic.  
7. **Cutover:** Disable batch issue detection loop; remove or feature-flag `_get_unprocessed_mentions` and DBSCAN from the hot path.  
8. **Optional:** Migrate embedding storage from JSONB to pgvector-only and drop JSONB after backfill; same for centroid.

This keeps the system production-grade, aligned with the streaming incremental design, while retaining all current mappings and functionality and avoiding breaking changes.

---

## Quick reference: current components and changes

| Component | Current file(s) | Change |
|-----------|------------------|--------|
| Ingestion | `DataIngestor`, `dataset_tailer`, `x_stream_collector`, `scheduler` + collectors | Add enqueue after insert; no change to callers. |
| Analysis (poll-based) | `analysis_worker.py` | Add queue consumer path; single read by entry_id, single write; enqueue for assigner. Keep poll path for backfill or until cutover. |
| Issue detection (batch) | `issue_detection_engine.py`, `data_processor.py`, `main._run_issue_detection` | Replace `_get_unprocessed_mentions` + DBSCAN with incremental assigner; keep promotion/merge/backfill logic, fed from clusters only. |
| Clustering | `issue_clustering_service.py` (DBSCAN) | New: incremental assigner (new module or inside issue_detection_engine) using pgvector distance; DBSCAN only for optional backfill or deprecated. |
| Models | `api/models.py` | Add columns: `SentimentData.cluster_id`, `SentimentEmbedding.embedding_vec`, `ProcessingCluster.centroid_vec`. |
| Main entry | `main.py` | Start queue consumer(s) and incremental assigner; optionally stop or gate `_issue_detection_loop` batch path. |

---

## Related docs

- **EGRESS_AND_ARCHITECTURE_ANALYSIS.md** — Why the current design causes 17B index scans and 11.9 GB egress; architectural fixes (state on row, pgvector, event-driven).
- **Database Egress Audit plan** — Tactical query/code fixes (rewrite NOT EXISTS, reduce embedding reads, single fetch in AnalysisWorker) that can be done before or in parallel with this migration.
