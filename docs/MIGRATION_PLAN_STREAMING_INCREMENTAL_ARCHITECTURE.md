# Migration Plan: Streaming Incremental Architecture

This plan aligns the **production-grade streaming architecture** (ingestion → queue → analysis → incremental cluster assigner → PostgreSQL + Pinecone) with the **current Clariona system**, retaining all existing tables, APIs, and behaviour. Nothing is removed until the new path is proven; migrations are additive and backward-compatible.

**Vector Store:** Pinecone is used for cluster centroid indexing and nearest-neighbor search (Railway PostgreSQL does not support pgvector natively).

**Deployment Strategy:** Backend runs on **EC2 with PM2 on Test branch (production)**. All changes are **feature-flag gated** (default=false) so code can be safely deployed to the live Test branch without breaking production. The incremental clustering path only activates when the flag is flipped to `true` in the database.

---

## Design goal

**From:** Batch recomputation over stored mentions (poll DB → re-scan → DBSCAN → promote).  
**To:** Streaming incremental intelligence (event-driven analysis → one write → incremental cluster assignment → indexed lookups).

Existing behaviour (topic classification, sentiment, issues, promotion, owner configs, APIs) is preserved; only the **data flow** and **clustering model** change.

---

## Current system mapping (retained)

| Concept in new architecture | Current Clariona mapping | Retained as-is |
|-----------------------------|---------------------------|----------------|
| Mention                     | `sentiment_data` (PK `entry_id`) | Yes; **add `cluster_id` column** |
| Mention embedding           | `sentiment_embeddings` (embedding JSONB) | Yes (JSONB only; no vector column needed) |
| Topic per mention           | `mention_topics` (mention_id, topic_key, topic_confidence, …) | Yes |
| Cluster (metadata)          | `processing_clusters` (id, topic_key, centroid JSONB, size, status, **user_id**) | Yes; **add `user_id`, `sum_vec` JSONB, optional `version`** |
| Cluster (vector index)      | **Pinecone index** (cluster_id → centroid vector + metadata) | New; centroids stored in Pinecone for nearest-neighbor search |
| Mention ↔ cluster           | `cluster_mentions` (cluster_id, mention_id) | Yes |
| Issue (promoted cluster)    | `topic_issues` + `issue_mentions` | Yes |
| Tenant / owner              | `user_id` on `sentiment_data`; `owner_configs` (topics per owner); **`user_id` on `processing_clusters`** | Yes; **tenant isolation enforced** |
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
│  For each event: query Pinecone for nearest clusters (by tenant + topic)    │
│  → Assign to best cluster if distance < threshold else create cluster      │
│  → Update centroid in Pinecone + PG metadata; set sentiment_data.cluster_id │
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

## Phase 0: Feature Flag (Deploy First for Safety)

### 0.1 Add feature flag to database

Insert the master switch that controls incremental clustering:

```sql
INSERT INTO system_configurations 
(category, config_key, config_value, config_type, description, is_active, default_value)
VALUES 
('clustering', 'use_incremental_clustering', 'false', 'bool', 
 'Enable incremental clustering with Pinecone and queue-based processing (vs batch DBSCAN). Set to true only after full migration is deployed and validated.', 
 true, 'false');
```

### 0.2 Add helper method to ConfigManager

Add method to read the flag easily:
```python
def use_incremental_clustering(self) -> bool:
    """Check if incremental clustering is enabled."""
    return self.get('clustering.use_incremental_clustering', False)
```

**Deploy this first.** All subsequent code will check this flag before executing new paths. Old system continues running unchanged.

---

## Phase 1: Schema and Pinecone setup (additive only)

### 1.1 Add columns (no drops, no vector columns)

- **sentiment_data**
  - `cluster_id UUID NULL REFERENCES processing_clusters(id) ON DELETE SET NULL`  
  - Index: `(cluster_id)` and `(processing_status, created_at)` for backfill queue/scan.
- **sentiment_embeddings**
  - **No changes.** Keep `embedding` JSONB only (no `embedding_vec` needed since Pinecone handles vectors).
- **processing_clusters**
  - **Add `user_id UUID NULL`** (tenant isolation; nullable for backward compat).
  - **Add `sum_vec JSONB NULL`** (stores running sum as array `[float, ...]` for centroid computation).
  - **Add `version INT NOT NULL DEFAULT 1`** (optimistic locking; increment on every update).
  - Keep `centroid` JSONB (for audit/display and backward compat).
  - **Remove pgvector references:** No `centroid_vec` column; centroids live in Pinecone.
  - Index: `(topic_key, user_id, status)` composite for tenant-scoped cluster lookups.
  - Index: `(status, updated_at)` for compaction queries.

Add Alembic migration; all existing code paths ignore new columns until used.

### 1.2 Pinecone index setup

- **Create Pinecone index** (one-time, via script or admin tool):
  - **Name:** e.g. `clariona-clusters-prod` (or per-environment: `clariona-clusters-dev`)
  - **Dimension:** 1536 (OpenAI embeddings)
  - **Metric:** cosine
  - **Metadata schema (indexed fields):** `topic_key` (string), `user_id` (string, nullable), `status` (string), `size` (int, optional)
  
- **Namespace strategy:** Use one index with metadata filtering (simpler than per-topic namespaces). Pinecone will filter by `topic_key` and `user_id` in query.

- **Index initialization script:** `scripts/init_pinecone_index.py` — creates index if not exists; idempotent.

Add Alembic migration(s); all existing code paths ignore new columns until used.

### 1.3 Message queue (gated by feature flag)

- **Choice 1 (recommended):** PostgreSQL `LISTEN/NOTIFY` with a small helper table `analysis_queue (entry_id, created_at, status)` or `INSERT … RETURNING` + NOTIFY. Analysis worker uses `SELECT … FOR UPDATE SKIP LOCKED` and processes by `entry_id`.
- **Choice 2:** Redis Streams stream `analysis_pending`; producers XADD after insert; workers XREADGROUP.
- **Choice 3:** Kafka topic(s) for scale.

**Recommendation:** start with **Choice 1** (PG queue) — no new infra, transactional coupling with DB writes, simplest ops. Switch to Redis/Kafka later if throughput exceeds ~2k events/sec or you need durable replay.

**Queue schema (if PG):**
```sql
CREATE TABLE analysis_queue (
  id SERIAL PRIMARY KEY,
  entry_id INT NOT NULL REFERENCES sentiment_data(entry_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'failed'
  retry_count INT NOT NULL DEFAULT 0,
  UNIQUE(entry_id)
);
CREATE INDEX ON analysis_queue(status, created_at) WHERE status = 'pending';

CREATE TABLE cluster_queue (
  id SERIAL PRIMARY KEY,
  entry_id INT NOT NULL,
  topic_key TEXT NOT NULL,
  user_id UUID,
  embedding JSONB NOT NULL,  -- array of 1536 floats
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'pending',
  retry_count INT NOT NULL DEFAULT 0
);
CREATE INDEX ON cluster_queue(status, created_at) WHERE status = 'pending';
```

**Safety:** Tables created by migration but not used unless `use_incremental_clustering=true`. No change to ingestion API: still call `DataIngestor.insert_record` / `insert_batch`; inside the ingestor, enqueue only if flag is true.

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
- **Single read:** `SELECT … FROM sentiment_data WHERE entry_id = :id` (and optionally join sentiment_embeddings if we need to avoid overwriting). Fetch only columns needed for analysis (text, content, title, description, date, source_type, **user_id**, etc.).
- **Compute:** same as today: embedding model → topic classifier (with embedding) → sentiment/emotion.
- **Single write:** one transaction:
  - UPDATE sentiment_data SET sentiment_label = …, processing_status = 'completed', …
  - INSERT/UPDATE sentiment_embeddings (embedding JSONB).
  - INSERT mention_topics (bulk for all topic_keys).
  - **Cap topics:** Take at most top 3 topics by confidence (prevents topic explosion and event storm).
  - **Filter topics:** Use only topics in the owner's `OwnerConfig.topics` set (already supported by TopicClassifier).
- **Then enqueue for cluster assigner (MANDATORY payload):**
  ```json
  {
    "entry_id": 123,
    "topic_key": "health",
    "user_id": "uuid-or-null",
    "embedding": [1536 floats from in-memory result],
    "created_at": "ISO8601"
  }
  ```
  **One event per (entry_id, topic_key).** Embedding **must** be in the event (from the in-memory result of the embedding model) so the assigner never reads the DB for it. If multiple topics, enqueue multiple events (one per topic).

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
- **Kept:** Promotion job that (1) reads `processing_clusters` (filtered by `user_id` for tenant isolation and by `status = 'active'`), (2) creates/updates topic_issues and issue_mentions from cluster_mentions, (3) backfills labels/summaries. This job no longer needs to read sentiment_data or sentiment_embeddings except for backfill (e.g. LLM summary), and only for the few promoted issues.

### 5.3 Tenant isolation in promotion

- **Current state:** Promotion filters only by `topic_key` and `status` — cross-tenant clustering possible.
- **New behaviour:** All promotion queries **must filter by `user_id`** (or run per-tenant in a loop). Example:
  ```python
  clusters = session.query(ProcessingCluster).filter(
      ProcessingCluster.topic_key == topic_key,
      ProcessingCluster.user_id == user_id,  # NEW: tenant isolation
      ProcessingCluster.status == 'active'
  ).all()
  ```
  This ensures one tenant's clusters never promote into another tenant's issues.

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

- All tables (additive only: `cluster_id`, `user_id`, `sum_vec`, `version` on relevant tables; **no vector columns in PG**).
- All APIs and dashboard queries.
- Topic classification and MentionTopic.
- Sentiment, emotion, influence_weight, processing_status.
- TopicIssue, IssueMention, ProcessingCluster, ClusterMention.
- OwnerConfig, user_id, multi-owner topic filtering (tenant isolation enforced in clustering and promotion).
- DataIngestor contract (insert_record, insert_batch, normalize, upsert).
- Promotion and merge logic (operating on clusters and cluster_mentions, now tenant-scoped).

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
| Analysis (poll-based) | `analysis_worker.py` | Add queue consumer path; single read by entry_id, single write; enqueue for assigner **with embedding + user_id in payload**. Keep poll path for backfill or until cutover. |
| Issue detection (batch) | `issue_detection_engine.py`, `data_processor.py`, `main._run_issue_detection` | Replace `_get_unprocessed_mentions` + DBSCAN with incremental assigner; keep promotion/merge/backfill logic (fed from clusters only, **filtered by user_id**). |
| Clustering | `issue_clustering_service.py` (DBSCAN) | New: incremental assigner (new module, e.g. `incremental_cluster_assigner.py`) using **Pinecone** for vector search; DBSCAN only for optional backfill or deprecated. |
| Models | `api/models.py` | Add columns: `SentimentData.cluster_id`, `ProcessingCluster.user_id`, `sum_vec` (JSONB), `version`. **No vector columns** (Pinecone handles vectors). |
| Pinecone client | New module: `services/pinecone_client.py` or `utils/pinecone_client.py` | Wrapper for Pinecone query/upsert; retry + backoff; error handling. |
| Main entry | `main.py` | Start queue consumer(s) and incremental assigner; optionally stop or gate `_issue_detection_loop` batch path based on feature flag. |
| Backfill | New script: `scripts/backfill_cluster_assignments.py` | Throttled backfill (200–500/min); group by (topic_key, user_id); same assigner logic. |
| Reconciliation | New script: `scripts/reconcile_pinecone.py` | Sync PG clusters → Pinecone (for missed upserts). |
| Compaction | New script or job in `main.py`: `scripts/compact_clusters.py` | Archive small/stale clusters; update Pinecone metadata or delete vectors. |

---

---

## New external dependencies

| Type | What | Why |
|------|------|-----|
| **Pinecone** | Managed vector database (SaaS) | Railway PostgreSQL lacks pgvector; Pinecone provides managed vector indexing and nearest-neighbor search for cluster centroids. |
| **Python library** | `pinecone-client` (or latest SDK) | Pinecone API client. |
| **Config/env** | `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME` | Credentials and index name for Pinecone. |
| **Network** | Outbound HTTPS to Pinecone API | Ensure Railway allows; add retry + circuit breaker. |
| **Queue (optional)** | Redis or Kafka (if not using PG queue) | If PG queue insufficient for throughput. |

**Cost estimate (Pinecone):**
- Free tier: 1 index, 1M vectors, limited QPS (good for dev/staging).
- Starter (~$70/mo): 1 pod, 100k QPS, suitable for < 100k clusters.
- Standard: Scales with pods and usage.

For governance pipeline with expected **< 100k active clusters** and **< 1k assigns/sec**, starter tier is sufficient.

---

## Related docs

- **EGRESS_AND_ARCHITECTURE_ANALYSIS.md** — Why the current design causes 17B index scans and 11.9 GB egress; architectural fixes (state on row, vector index, event-driven).
- **Database Egress Audit plan** — Tactical query/code fixes (rewrite NOT EXISTS, reduce embedding reads, single fetch in AnalysisWorker) that can be done before or in parallel with this migration.
