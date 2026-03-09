# Transaction Leak Audit — Root Cause Analysis

## Summary

Two distinct leak patterns were identified from the `pg_stat_activity` "idle in transaction" observations:

1. **system_configurations** — Long-lived shared session in main service
2. **sentiment_data** — Heavy I/O (API calls) inside open transaction in analysis worker

---

## 1. system_configurations Leak

### Location
`src/services/main.py` lines 176, 221

### Root Cause
The main streaming service creates **one session at startup** and keeps it for the service lifetime:

```python
# Line 176
self.db_session = SessionLocal()

# Line 221 - reads system_configurations using that session
flag_value = config.use_incremental_clustering(db_session=self.db_session)
```

`use_incremental_clustering` runs `SELECT ... FROM system_configurations WHERE category='clustering' AND config_key='use_incremental_clustering'`. That starts a transaction. The session is **shared** with DataIngestor and XStreamRulesManager. If no write + commit happens soon after, the transaction stays open — "idle in transaction" with last query = system_configurations.

### Fix
Do not use the long-lived `db_session` for the config read. Use a short-lived session or config file only:

```python
# Option A: Use config file (no DB)
flag_value = config.use_incremental_clustering(db_session=None)

# Option B: Use a throwaway session for the config read
with SessionLocal() as tmp:
    flag_value = config.use_incremental_clustering(db_session=tmp)
```

---

## 2. sentiment_data Leak (Heavy I/O Sandwich)

### Location
`src/services/analysis_worker.py` — `_analyze_record` (lines ~241–430)

### Root Cause
The transaction is opened with a `SELECT sentiment_data` and held open during all API calls:

```
1. with SessionLocal() as db:
2.   record = db.query(SentimentData).filter(...).first()   ← Transaction starts
3.   agent.sentiment_analyzer.analyze(text_content)         ← OpenAI API call (slow)
4.   agent.topic_classifier.classify(...)                   ← Up to 90s timeout!
5.   # ... MentionTopic storage, ClusterQueue enqueue ...
6.   db.commit()                                            ← Transaction ends
```

Steps 2–5 run inside one transaction. During 3–4 the DB sees "idle in transaction" because no SQL is running while the process waits on external APIs.

### Fix
Split into read → process → write:

```python
# Phase 1: Short read transaction
with SessionLocal() as db:
    record = db.query(SentimentData).filter(...).first()
    if not record: return
    # Detach: copy needed fields to plain dict
    data = {"entry_id": record.entry_id, "text": record.text or record.content or ..., ...}
    db.commit()  # Release immediately

# Phase 2: Heavy I/O outside transaction
result = agent.sentiment_analyzer.analyze(data["text"])
topics = agent.topic_classifier.classify(...)

# Phase 3: Short write transaction
with SessionLocal() as db:
    record = db.query(SentimentData).filter(...).first()
    record.sentiment_label = result["sentiment_label"]
    # ... store topics, ClusterQueue, etc.
    db.commit()
```

---

## 3. IncrementalClusterAssigner — Lock Contention (not a leak)

### Location
`src/services/incremental_cluster_assigner.py` — `_assign_to_existing_cluster` (lines 159–228)

### Issue
`FOR UPDATE` is held during the Pinecone upsert:

```python
cluster = session.query(ProcessingCluster).with_for_update().first()  # Lock acquired
# ... update cluster ...
pinecone_upsert(...)  # Network call while lock held!
session.execute(...)  # cluster_mentions insert
# commit happens later
```

Other queries on `processing_clusters` can block until this transaction commits.

### Fix (with Lost-Update protection)
Moving Pinecone outside the transaction risks a **Lost Update**: two workers read the same cluster, both call Pinecone, both write — the second overwrites the first. Use **Optimistic Concurrency** (version check):

1. Read cluster and its `version` (ProcessingCluster already has `version` column).
2. Do Pinecone work **outside** the transaction.
3. Update with: `WHERE id = :id AND version = :old_version`.
4. If `rowcount == 0`, someone else updated; roll back and retry.

```python
# Atomic flip pattern
cluster = session.query(ProcessingCluster).filter(...).first()
old_version = cluster.version
# ... Pinecone upsert (no lock held) ...
stmt = update(ProcessingCluster).where(
    ProcessingCluster.id == cluster.id,
    ProcessingCluster.version == old_version
).values(centroid=..., size=..., version=old_version + 1)
result = session.execute(stmt)
if result.rowcount == 0:
    session.rollback()
    # Retry from step 1
```

Alternatively, use `with_for_update(skip_locked=True)` so workers skip locked rows instead of blocking.

---

## 4. ConfigManager — use_global_clustering Session Handling

### Location
`src/config/config_manager.py` — `use_global_clustering` (lines 803–839)

### Note
When `db_session=None`, `use_global_clustering` creates its own session and **closes it** in `finally`. Good.

`use_incremental_clustering` does **not** create its own session when `db_session` is provided — it uses the caller's session and never closes it. So callers must not pass a long-lived session if they want short transactions.

---

## 5. DetachedInstanceError Gotcha (Fix #2)

When copying record data to a plain dict for Phase 2 (outside the session), **do not access lazy-loaded relationships** after the session closes. Use `joinedload()` for any related data needed in Phase 2:

```python
record = db.query(SentimentData).options(
    joinedload(SentimentData.embedding)  # Eager load; copy embedding.embedding to dict
).filter(...).first()
# Copy embedding to list before commit — record.embedding.embedding is safe while session is open
emb = list(record.embedding.embedding) if record.embedding else None
db.commit()
# Phase 2: use emb, data['text_content'] — never record.embedding (would raise DetachedInstanceError)
```

---

## 6. Session Cleanup Utility

`src/api/session_utils.py` provides `session_scope()` — a context manager that guarantees commit/rollback/close:

```python
from src.api.session_utils import session_scope

with session_scope() as db:
    record = db.query(Model).first()
    record.name = "updated"
# commit + close happen here; rollback on exception
```

Use for any block that performs DB work to prevent regression.

---

## 7. Implementation Status

| Item | Status |
|------|--------|
| main.py: `db_session=None` for config check | ✅ Done |
| analysis_worker: Read → Process → Write | ✅ Done |
| database: `application_name` (env: PG_APPLICATION_NAME) | ✅ Done |
| session_utils.py | ✅ Created |
| incremental_cluster_assigner: Optimistic concurrency | Pending |

---

## 8. Recommended Next Steps

1. **incremental_cluster_assigner.py** — Implement optimistic concurrency (version check) or `skip_locked=True`; move Pinecone outside locked section.
2. **SQLAlchemy echo** — Temporarily enable `echo=True` in development to trace BEGIN/COMMIT/ROLLBACK.
3. **Per-service application names** — Set `PG_APPLICATION_NAME=analysis_worker` (etc.) when running dedicated processes for finer `pg_stat_activity` visibility.
