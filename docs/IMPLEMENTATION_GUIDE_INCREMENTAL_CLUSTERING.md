# Implementation Guide: Incremental Clustering Migration

**Start here for the next chat session.**

---

## Progress Tracker

| Phase | Component | Status | Deploy Safe? | Notes |
|-------|-----------|--------|--------------|-------|
| 0 | Prerequisites | ✅ DONE | N/A | Pinecone account, env vars, pip installed |
| 1 | Feature Flag | ✅ DONE | ✅ YES | DB row + ConfigManager helper |
| 2 | Schema Changes | ✅ DONE | ✅ YES | Alembic migration (additive only) |
| 3 | Pinecone Setup | ✅ DONE | ✅ YES | Init script + client wrapper |
| 4 | Incremental Assigner | ✅ DONE | ✅ YES | Core worker (gated, won't start) |
| 5 | Analysis Worker | ✅ DONE | ✅ YES | Queue consumer (gated) |
| 6 | DataIngestor | ✅ DONE | ✅ YES | Enqueue after insert (gated) |
| 7 | Main.py Integration | ✅ DONE | ✅ YES | Start workers when flag=true |
| 8 | Promotion Changes | ✅ DONE | ✅ YES | Add user_id filter |
| 9 | Testing | 🔲 TODO | ⚠️ DEV/STAGING | Unit + integration tests |
| 10 | Backfill Scripts | 🔲 TODO | ✅ YES | Manual scripts (run later) |
| 11 | **CUTOVER** | 🔲 TODO | ⚠️ **MONITOR** | Flip flag, watch metrics |

**Status Legend:** ✅ DONE | 🔄 IN PROGRESS | 🔲 TODO | ⚠️ BLOCKED  
**Current Phase:** Phase 9 (Testing)

---

## Context

- **Backend:** EC2 with PM2 running on **Test branch (production)**
- **Database:** Railway PostgreSQL (no pgvector support)
- **Migrations:** Always run with venv active: `source .venv/bin/activate && alembic upgrade head`
- **Vector Store:** Pinecone (managed, external)
- **Strategy:** Feature-flag gated deployment (all new code inactive until flag=true)

---

## Critical Safety Rule

**ALL new code must check the feature flag:**

```python
use_incremental = config.get('clustering.use_incremental_clustering', False)

if use_incremental:
    # New path: Pinecone + queue + incremental assigner
    pass
else:
    # Old path: batch DBSCAN ← production keeps running here
    pass
```

**Flag defaults to `false`** in database. Even after code is deployed and PM2 restarts, production continues using old batch DBSCAN path. Only when flag is flipped to `true` does new system activate.

---

## Phase 0: Prerequisites (Do Before Building)

### ✅ Pinecone Account
1. Sign up at pinecone.io (free tier for dev)
2. Create project
3. Get API key from dashboard
4. Note environment (e.g. `us-east-1-aws`)

### ✅ Add Environment Variables to EC2
On the EC2 instance, add to your `.env` or PM2 ecosystem config:

```bash
PINECONE_API_KEY=your-actual-key-here
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=clariona-clusters-dev  # or prod
```

After adding, restart PM2: `pm2 restart all`

### ✅ Install Python Package
```bash
cd /home/ubuntu/Clariona-1.5/Clariona-Backend
pip install pinecone-client
# Add to requirements.txt
echo "pinecone-client>=2.2.0" >> requirements.txt
```

---

## Implementation Phases (In Order)

### Phase 1: Feature Flag (Deploy First)
**File:** SQL migration or manual insert
**Action:** Insert feature flag row into `system_configurations` table with `config_value='false'`
**Safety:** All new code will be dormant until this is flipped to true
**Deploy:** Safe immediately

---

### Phase 2: Schema Changes
**Files:** New Alembic migration
**Changes:**
- `sentiment_data.cluster_id` (UUID, nullable, FK)
- `processing_clusters.user_id` (UUID, nullable, FK)
- `processing_clusters.sum_vec` (JSONB, nullable)
- `processing_clusters.version` (INT, default 1)
- Indexes: `(topic_key, user_id, status)`, `(status, updated_at)`, `(cluster_id)`
- Queue tables: `analysis_queue`, `cluster_queue`

**Safety:** All additive; existing code ignores new columns
**Deploy:** Run migrations with venv active: `source .venv/bin/activate && alembic upgrade head`, then deploy code

---

### Phase 3: Pinecone Setup
**Files:**
- `scripts/init_pinecone_index.py` (create index)
- `src/services/pinecone_client.py` (wrapper with retry/circuit breaker)

**Safety:** External service; no impact on production
**Deploy:** Run init script once, deploy client wrapper (not called unless flag=true)

---

### Phase 4: Incremental Cluster Assigner
**File:** `src/services/incremental_cluster_assigner.py`

**Core logic:**
1. Consume from `cluster_queue` (or PG queue table)
2. Check feature flag; if false, exit
3. Query Pinecone with tenant+topic filter
4. If match found: lock cluster (optimistic), update centroid, upsert Pinecone
5. If no match: create new cluster in PG + Pinecone
6. Link mention: set `cluster_id`, insert `cluster_mentions` (idempotent)
7. Commit PG, ACK queue message

**Safety:** Worker doesn't start in main.py unless flag=true
**Deploy:** Code deployed but dormant

---

### Phase 5: Analysis Worker Changes
**File:** `src/services/analysis_worker.py`

**Changes:**
- Add queue consumer (gated by flag)
- After writing sentiment+embedding+topics: if flag=true, enqueue cluster events (with embedding in payload)
- Keep old polling path as fallback (if flag=false)

**Safety:** Flag=false means old path continues
**Deploy:** Backward compatible

---

### Phase 6: DataIngestor Changes
**File:** `src/services/data_ingestor.py`

**Change:** After insert/batch commit, if flag=true, enqueue to `analysis_queue`

**Safety:** Flag=false means no enqueue; zero overhead
**Deploy:** Backward compatible

---

### Phase 7: Main.py Integration
**File:** `src/services/main.py`

**Change:** 
```python
if config.use_incremental_clustering():
    start_analysis_queue_consumer()
    start_cluster_assigner_worker()
# Old batch DBSCAN loop continues if flag=false
```

**Safety:** Workers don't start unless flag=true
**Deploy:** Safe

---

### Phase 8: Promotion Changes
**File:** `src/processing/issue_detection_engine.py`

**Change:** Add `user_id` filter to cluster queries in `promote_clusters_for_topic()`

**Safety:** Backward compatible (user_id nullable)
**Deploy:** Safe for both paths

---

### Phase 9: Testing & Validation
- Unit tests (Pinecone client, assigner logic)
- Integration test: insert mention → verify cluster_id set
- Dev/staging: flip flag=true, validate end-to-end
- **Don't flip flag in production yet**

---

### Phase 10: Backfill & Reconciliation Scripts
**Files:**
- `scripts/backfill_cluster_assignments.py` (throttled, manual)
- `scripts/reconcile_pinecone.py` (sync PG → Pinecone)
- `scripts/compact_clusters.py` (archive small/stale)

**When to run:** After flag=true in production and validated

---

### Phase 11: Production Cutover
1. Verify all code deployed with flag=false; production stable
2. Monitor baseline: DB load, latency, errors
3. **Flip flag to true:**
   ```sql
   UPDATE system_configurations 
   SET config_value = 'true' 
   WHERE category = 'clustering' AND config_key = 'use_incremental_clustering';
   ```
4. Restart PM2: `pm2 restart all` (or workers re-read config)
5. Watch metrics: Pinecone latency, queue lag, cluster creation rate, errors
6. If stable after 1 hour → let run
7. **If issues: flip flag back to false** (instant rollback)

---

## Quick Reference: What Gets Built

| Component | File | Gated by Flag? |
|-----------|------|----------------|
| Feature flag row | `system_configurations` table | N/A (is the flag) |
| Schema migration | Alembic migration | No (additive) |
| Queue tables | Alembic migration | No (passive until used) |
| Pinecone index | `init_pinecone_index.py` | No (external) |
| Pinecone client | `pinecone_client.py` | Yes (not called unless flag=true) |
| Incremental assigner | `incremental_cluster_assigner.py` | Yes (doesn't start unless flag=true) |
| Analysis worker queue | `analysis_worker.py` changes | Yes (gated in code) |
| DataIngestor enqueue | `data_ingestor.py` changes | Yes (gated in code) |
| Main.py workers | `main.py` changes | Yes (workers don't start unless flag=true) |
| Promotion user_id filter | `issue_detection_engine.py` | No (backward compatible) |
| Backfill script | `backfill_cluster_assignments.py` | Manual (run when ready) |
| Reconciliation script | `reconcile_pinecone.py` | Manual |
| Compaction script | `compact_clusters.py` | Manual |

---

## Expected Timeline

| Phase | Duration | Can Deploy to Production? |
|-------|----------|---------------------------|
| 0. Prerequisites | 10 min | N/A |
| 1. Feature flag | 30 min | ✅ YES (deploy immediately) |
| 2. Schema | 1 day | ✅ YES (additive only) |
| 3. Pinecone setup | 1 day | ✅ YES (external, dormant code) |
| 4. Assigner | 2-3 days | ✅ YES (gated, won't start) |
| 5. Analysis worker | 1-2 days | ✅ YES (gated) |
| 6. DataIngestor | 1 day | ✅ YES (gated) |
| 7. Main.py | 1 day | ✅ YES (gated) |
| 8. Promotion | 1 day | ✅ YES (backward compatible) |
| 9. Testing | 2-3 days | ⚠️ Test in dev/staging first |
| 10. Scripts | 2 days | ✅ YES (manual scripts) |
| 11. **CUTOVER** | 1 hour | ⚠️ **Flip flag, monitor closely** |

**Total build time:** ~2 weeks  
**Can deploy incrementally:** YES, every phase is production-safe

---

## Rollback Plan

If anything goes wrong after flipping flag to true:

1. **Instant rollback (no code change):**
   ```sql
   UPDATE system_configurations SET config_value = 'false' 
   WHERE category = 'clustering' AND config_key = 'use_incremental_clustering';
   ```
   Then `pm2 restart all`

2. Old batch DBSCAN resumes processing
3. Investigate issue, fix, redeploy
4. Flip flag back to true when ready

---

## Monitoring Checklist (After Cutover)

- [ ] Pinecone API latency (p50, p95, p99)
- [ ] Pinecone error rate
- [ ] Queue depth (`analysis_queue`, `cluster_queue`)
- [ ] Cluster assignment rate (mentions/sec)
- [ ] Clusters created vs assigned (ratio)
- [ ] Database CPU and memory (should decrease)
- [ ] Database egress (should drop 60-80%)
- [ ] Promotion rate (issues created)
- [ ] PM2 process health

---

## Production Hardening Checklist

These critical items from the hardening review MUST be included:

- [ ] **Phase 4**: Embedding mandatory in cluster events (write-only assigner)
- [ ] **Phase 4**: Cluster locking (SELECT FOR UPDATE or optimistic version)
- [ ] **Phase 2,4**: Tenant isolation (user_id in clusters + queries)
- [ ] **Phase 4**: Centroid math (sum_vec + count, NOT incremental avg)
- [ ] **Phase 4**: Idempotency (ON CONFLICT DO NOTHING on cluster_mentions)
- [ ] **Phase 10**: Backfill throttling (200-500/min max)
- [ ] **Phase 8**: Promotion min cluster size check
- [ ] **Phase 10**: Compaction job (archive small/stale clusters)
- [ ] **Phase 9**: Observability metrics (assign rate, queue lag, latency)
- [ ] **All phases**: Feature flag checks in all new code paths

---

## Next Chat: Start Here

**Current Phase:** Phase 9 (Testing)

**Say:** "Let's build Phase 1" or "Start Phase 1"

I'll immediately:
1. Add feature flag to DB (SQL insert or migration)
2. Update ConfigManager with helper method
3. Update progress tracker
4. Then ask if you want to continue to Phase 2

All changes will be feature-flag protected and safe to deploy on live Test branch.

---

## Quick Commands

**Migrations (always use venv):** `source .venv/bin/activate && alembic upgrade head`  
**Check progress:** Show me the tracker  
**Continue:** Let's do Phase N  
**Deploy:** All phases 1-8 deployed, ready to test  
**Cutover:** Flip the flag (after Phase 9 validated)  
**Rollback:** Flip flag back to false

---

**End of guide. Copy this file path for next chat:**
`/home/ubuntu/Clariona-1.5/Clariona-Backend/docs/IMPLEMENTATION_GUIDE_INCREMENTAL_CLUSTERING.md`
