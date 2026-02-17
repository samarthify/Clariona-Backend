# Egress and Architecture Analysis: Why the Numbers Explode

This document explains the **architectural** reasons behind extreme database egress (11.9 GB+, 17B index scans on `processing_clusters`, 3.7 GB for 58 rows). It is separate from the **Database Egress Audit** plan (query-level audit), which focuses on concrete query and code fixes.

---

## 1. Core architectural issue: store then re-fetch for analysis

The pipeline is structured as:

1. **Ingest** → write rows into `sentiment_data` (and optionally `sentiment_embeddings`).
2. **Analysis** → later, workers poll the DB for “unprocessed” or “not yet clustered” rows, then **read those same rows again** (plus embeddings) to run sentiment, topic, and issue detection.

So we **store first, then run analysis by re-reading stored data**. That implies:

- Every analysis path does at least one full read of the data it needs (often including large JSONB embeddings).
- “Unprocessed” is defined by **absence** of a row in another table (e.g. no `IssueMention`, no `ClusterMention` + active `ProcessingCluster`), which forces **correlated subqueries** and repeated index lookups.
- There is no single “state” on the mention row (e.g. `cluster_id`) that we can index and filter on; we must re-evaluate relationships every cycle.

That design is the main reason we get **logical query explosion** and **repeated full reads** of the same large data (especially embeddings).

---

## 2. Why 17B index scans on `processing_clusters`?

From the stats:

- `processing_clusters`: **58 rows**
- `idx_scan`: **17,000,000,000**
- `seq_scan`: **249,000**

You do not get 17B index scans from normal, one-off queries. You get that from:

> **A correlated subquery that runs once per row of a large outer query.**

In the codebase this is exactly what happens. In `issue_detection_engine._get_unprocessed_mentions` we have:

```python
subq_active_cluster = (
    select(1)
    .select_from(ClusterMention)
    .join(ProcessingCluster, ClusterMention.cluster_id == ProcessingCluster.id)
    .where(
        ClusterMention.mention_id == SentimentData.entry_id,
        ProcessingCluster.status == 'active',
    )
)
no_active_cluster = ~exists(subq_active_cluster)
```

The outer query is over `SentimentData` joined with `MentionTopic` (filtered by topic and other conditions). For **each** candidate row, the planner must evaluate `NOT EXISTS (subq_active_cluster)`. That implies:

- Look up `ClusterMention` by `mention_id` (index scan on `cluster_mentions`).
- For each match, look up `ProcessingCluster` by `cluster_id` (index scan on `processing_clusters`).

So **every outer row** can trigger one or more index lookups on `processing_clusters`. With:

- Hundreds of thousands of mention rows over time
- Issue detection every 5 minutes
- 20 topics in parallel, each with batches of 300
- Many batches per topic per run

the number of evaluations of this subquery multiplies. That pattern matches **17B index scans** on `processing_clusters` and is a **structural** problem, not just a “slow query” to tune.

---

## 3. Why 249K seq scans on a 58-row table?

If the planner sometimes chooses a sequential scan on `processing_clusters` (e.g. when it thinks the table is tiny), then **every** such scan still has to read the **entire table**. With 3.7 GB for 58 rows (see below), each seq scan can pull 3.7 GB. So:

- 249K seq scans × 3.7 GB ≈ **massive egress** from this table alone.

So the seq scan count is dangerous not because 58 rows is big, but because **each scan is effectively a full read of a 3.7 GB relation** (table + TOAST).

---

## 4. Why 3.7 GB for 58 rows?

A single 1536-dim centroid as JSONB is on the order of **~10–30 KB** per row. So 58 rows should be on the order of **~2 MB**, not 3.7 GB.

So one of the following is true:

1. **Centroid was (or is) stored as a 2D structure**  
   For example, if somewhere we had stored a **list of vectors** (e.g. all embeddings in the cluster) instead of a single averaged vector, that would be huge per row. In the **current** code we only set `centroid = new_centroid.tolist()` or `centroid_json` from `_calculate_centroid()` (which returns `np.mean(embeddings, axis=0)` — a 1D vector). So we do **not** currently append to `centroid` or assign a 2D array. A 2D centroid could still be:
   - From an **older bug** (since fixed) that left bad rows in the table.
   - From a **different code path** that we haven’t inspected.

2. **TOAST and/or table bloat**  
   If the table or its TOAST table has accumulated dead tuples and autovacuum hasn’t kept up, reported “data” size can be much larger than live row size. Then 249K seq scans would be reading a lot of dead/bloated pages.

**Recommendation:** Run the verification SQL in the audit plan (e.g. `pg_column_size(centroid)`, `jsonb_typeof`, `jsonb_array_length`) on a few rows. If `pg_column_size(centroid)` is in the **megabytes** per row, the 3.7 GB is from this column; if it’s 1D but large, it’s still wrong; if it’s small, the problem is bloat. Also run:

```sql
SELECT relname, n_dead_tup, n_live_tup, vacuum_count, autovacuum_count
FROM pg_stat_user_tables
WHERE relname IN ('processing_clusters', 'sentiment_embeddings', 'cluster_mentions');
```

If `n_dead_tup` is huge and `autovacuum_count` is low, bloat is a major factor.

---

## 5. Why 11.9 GB egress from `sentiment_embeddings`?

The table is **11.9 GB** (609K rows). Every time we `SELECT` the `embedding` column (or the whole row), we pull a large JSONB payload per row (~20 KB). The pipeline:

- **Issue detection:** `_get_unprocessed_mentions` loads 300 embeddings per batch, per topic; multiple batches per topic, 20 topics; then `_get_cluster_mentions` loads full embeddings again for every cluster considered for promotion; backfill loads full embeddings for issue mentions.
- So the **same embedding rows** can be read **many times** across batches, topics, and cycles.

So the 11.9 GB egress is not “read the table once”; it’s **repeated full reads** of the same large column. That is again **architectural**: we keep answering “what needs clustering?” by re-scanning and re-joining, and we store embeddings in a format (JSONB) that forces full payload transfer every time.

---

## 6. Design: reconciliation loop vs incremental / event-driven

Today the system behaves like a **reconciliation loop**:

- Every 5 minutes we ask: “What is unprocessed?”
- We scan for mentions that don’t have an issue, don’t have an active cluster, etc.
- We re-load clusters, issues, embeddings, and re-evaluate relationships.

That works at small scale (tens of thousands of rows) but **explodes** at hundreds of thousands of mentions and 20 concurrent topic workers: repeated scans, repeated joins, repeated embedding reads.

The alternative is **incremental, stateful progression** (or event-driven):

- When a mention is ingested and analyzed, we **mark** it (e.g. “has topic”, “has cluster_id” when assigned).
- “Unprocessed” becomes a simple filter on the mention table (e.g. `WHERE cluster_id IS NULL`), with no correlated subquery.
- Clustering can be triggered **per batch of new mentions** (or by event) instead of “scan all topics every 5 minutes”.

So the issue is not only “too many queries” but **the model of computation**: global re-evaluation every N minutes vs. incremental updates and explicit state on the row.

---

## 7. JSONB for embeddings: cost at scale

Embeddings are stored as JSONB in:

- `sentiment_embeddings.embedding`
- `processing_clusters.centroid`
- `topic_issues.cluster_centroid_embedding`

Implications:

- Every `SELECT` that returns these columns transfers the **full** JSON payload; there is no “partial read” of a vector.
- No native vector index (e.g. for similarity search); everything is application-side.
- TOAST and parsing add CPU and I/O.
- Wire size and egress are maximized for every row touched.

So even “one read per mention” of 600K rows with embeddings is already on the order of **11.9 GB**. Doing that repeatedly (multiple batches, topics, and cycles) matches the observed egress. This is an **architectural** choice (JSONB vs. native vector / `float4[]`), not only a query-tuning issue.

---

## 8. Hypothesis ranking (most likely first)

| # | Hypothesis | Evidence | How to verify |
|---|------------|----------|----------------|
| 1 | Correlated NOT EXISTS causes 17B index scans on `processing_clusters` | Subquery in `_get_unprocessed_mentions` runs per outer row; scan counts match. | Rewrite to precompute “mention_ids with active cluster” and filter without correlated subquery; re-check `pg_stat_user_tables.idx_scan` after a few hours. |
| 2 | 3.7 GB for 58 rows = 2D centroid bug or TOAST/bloat | Expected ~2 MB for 1D centroids; 3.7 GB implies wrong shape or bloat. | Run `pg_column_size(centroid)`, `jsonb_typeof`, `jsonb_array_length`; check `n_dead_tup` and `autovacuum_count` for `processing_clusters`. |
| 3 | JSONB embeddings cause massive egress (11.9 GB) | Every read pulls full payload; repeated reads in issue detection and backfill. | Add temporary logging of “embedding rows read per cycle”; compare to 11.9 GB / ~20 KB; after reducing embedding reads, measure egress again. |
| 4 | Global 5-minute re-scan design amplifies all of the above | Code structure: poll all topics, many batches, re-load clusters/issues/embeddings. | Compare egress before/after introducing a per-topic or per-run cap and after moving to “state on row” (e.g. cluster_id) so we don’t re-scan globally. |
| 5 | Table/index bloat (autovacuum not keeping up) | 281 MB for 8.7K `cluster_mentions` rows, 592 MB indexes; 3.7 GB for 58 rows. | `pg_stat_user_tables` for `n_dead_tup`, `vacuum_count`, `autovacuum_count`; run `VACUUM ANALYZE` (and if needed `VACUUM FULL` after fixing data) and re-check sizes. |
| 6 | Double-fetch in AnalysisWorker | Claim loads full row, then `_analyze_record` loads same row again. | Code inspection; after removing second fetch, compare sentiment_data scan growth. |

---

## 9. Proposed architectural changes (separate from query tweaks)

These address the **model** of the system, not only individual queries.

### 9.1 Stop re-scanning for “unprocessed” via correlated subquery

- Add explicit state on the mention so we don’t need NOT EXISTS (ClusterMention + ProcessingCluster).
- **Option A:** Add `cluster_id` (nullable FK to `processing_clusters`) to `sentiment_data`. When a mention is assigned to a cluster, set `cluster_id`. “Unprocessed” becomes `WHERE cluster_id IS NULL` (and topic/other filters). No join to `cluster_mentions` or `processing_clusters` for this filter.
- **Option B:** Add a boolean `is_clustered` (or similar) and set it when the mention is linked to a cluster. Same idea: simple indexed filter, no correlated subquery.

That alone should remove the vast majority of the 17B index scans on `processing_clusters` and simplify the planner.

### 9.2 Store embeddings in a vector-friendly type (not JSONB)

- Use **pgvector** (`vector(1536)`) or **`float4[]`** for:
  - `sentiment_embeddings.embedding`
  - `processing_clusters.centroid`
  - `topic_issues.cluster_centroid_embedding`
- Benefits: smaller storage, no JSON parse/serialize, possible vector index for similarity, lower wire size and egress per row. Migration can be done in steps (e.g. add column, backfill, switch reads, then drop JSONB).

### 9.3 Move toward event-driven / incremental issue detection

- Instead of “every 5 minutes, scan all topics and re-evaluate everything”:
  - On ingest (or after analysis), enqueue or mark “new mentions for clustering.”
  - Clustering runs on **new** mentions (and optionally a bounded set of “recent unclustered”) instead of a global scan.
  - Promotion can be triggered by thresholds or a separate, less frequent job.
- This reduces the **multiplier** (batches × topics × cycles) and aligns with “state on row” (e.g. cluster_id).

### 9.4 Cap cluster growth

- If clusters can grow without bound, centroid and promotion logic keep loading more mentions and embeddings per cluster. Add a **max size** (or split strategy) so that one cluster doesn’t dominate embedding reads and storage.

### 9.5 Fix vacuum and bloat

- Ensure autovacuum is enabled and appropriate for the workload.
- Run the dead-tuple and vacuum stats query above; if needed, run `VACUUM ANALYZE` and, after fixing any bad centroid data, `VACUUM FULL` on `processing_clusters` so that 58 rows don’t sit in a 3.7 GB relation.

---

## 10. How this doc relates to the audit plan

- **This document** explains **why** the numbers explode (store-then-re-fetch, correlated subquery, JSONB, reconciliation loop, bloat) and proposes **architectural** changes (state on row, vector type, event-driven, cap, vacuum).
- The **audit plan** (database egress audit) focuses on **concrete, incremental fixes**: rewrite NOT EXISTS, reduce embedding reads in promotion/backfill, single fetch in AnalysisWorker, batching X stream, etc.

You can:

- **Short term:** Apply the audit plan’s verification steps and query/code fixes to immediately reduce egress and confirm hypotheses.
- **Medium term:** Implement the architectural changes here (denormalize cluster_id, pgvector, incremental/event-driven design, vacuum) so that the system scales without re-scanning the whole world every 5 minutes.

Together, the two give you both a **path to prove** what is wrong (verification + hypothesis ranking) and **two layers of fix**: tactical (audit plan) and structural (this document).
