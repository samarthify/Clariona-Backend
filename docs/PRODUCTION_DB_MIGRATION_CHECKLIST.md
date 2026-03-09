# Production DB Migration: Railway pgvector Cutover Checklist

**⚠️ This is a controlled DB migration, not a feature toggle. Treat it as a production cutover.**

---

## Pre-flight: What You Must Have

- [ ] `pg_dump` and `pg_restore` installed (PostgreSQL client tools)
- [ ] Network access to both OLD and NEW databases
- [ ] OLD database URL (current production)
- [ ] NEW database URL (Railway pgvector instance)
- [ ] Rollback plan: **point `DATABASE_URL` back to OLD if anything goes wrong**
- [ ] **Do NOT delete OLD database until 24h+ of stability**

---

## Step 1 — Add pgvector DB (Do NOT switch yet)

1. In Railway: Add **pgvector** template (or PostgreSQL with pgvector extension)
2. Let it deploy fully
3. Copy the `DATABASE_URL` from the new pgvector service → this is `NEW_DATABASE_URL`
4. **Do nothing else.** App still uses OLD database. No risk.

---

## Step 2 — Verify PostgreSQL Version Match

On your local machine or a shell with DB access:

```bash
# OLD DB version
psql "$OLD_DATABASE_URL" -t -c "SELECT version();"

# NEW DB version
psql "$NEW_DATABASE_URL" -t -c "SELECT version();"
```

**Confirm major versions match** (e.g. both 15.x or both 16.x). Different major versions can cause subtle issues.

---

## Step 3 — Dump Production DB

From your local machine (or a server with access to production):

```bash
# Set your production DB URL
export OLD_DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Custom format (-Fc) is safer for restore
pg_dump "$OLD_DATABASE_URL" -Fc -f prod.dump
```

Verify dump file:

```bash
ls -la prod.dump
# Should be non-empty, reasonable size
```

---

## Step 4 — Restore Into pgvector DB

```bash
# Set NEW Railway pgvector DB URL
export NEW_DATABASE_URL="postgresql://user:pass@host:port/railway"

pg_restore \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  -d "$NEW_DATABASE_URL" \
  prod.dump
```

**Expected:** Some warnings (e.g. "extension already exists") are OK. **Errors about missing objects** may indicate a conflict; review before proceeding.

---

## Step 5 — Run Alembic Migration on NEW DB

Run migrations **against the NEW database only**:

```bash
# From Clariona-Backend root
cd /home/ubuntu/Clariona-1.5/Clariona-Backend

# Point Alembic to NEW DB
export DATABASE_URL="$NEW_DATABASE_URL"
alembic -c src/alembic.ini upgrade head
```

This will:
- Enable `vector` extension (if not already)
- Add `cluster_id`, `embedding_vec`, `centroid_vec`, queue tables
- Create indexes

---

## Step 6 — Validate Before Switching

Run the validation script (see `scripts/validate_db_migration.sql`):

```bash
psql "$NEW_DATABASE_URL" -f scripts/validate_db_migration.sql
```

Or run these checks manually:

```sql
-- Row counts (compare with OLD DB)
SELECT 'sentiment_data' AS tbl, count(*) FROM sentiment_data
UNION ALL
SELECT 'processing_clusters', count(*) FROM processing_clusters
UNION ALL
SELECT 'sentiment_embeddings', count(*) FROM sentiment_embeddings
UNION ALL
SELECT 'cluster_mentions', count(*) FROM cluster_mentions
UNION ALL
SELECT 'topic_issues', count(*) FROM topic_issues;

-- pgvector extension
SELECT extname FROM pg_extension WHERE extname = 'vector';

-- New columns exist
SELECT column_name FROM information_schema.columns
WHERE table_name = 'sentiment_data' AND column_name = 'cluster_id';
```

**Confirm:**
- [ ] Row counts match OLD DB
- [ ] `vector` extension exists
- [ ] `cluster_id` column exists on `sentiment_data`

---

## Step 7 — Switch App to New DB

1. In Railway (or wherever `DATABASE_URL` is set):
   - Change `DATABASE_URL` to the **NEW** pgvector database URL
   - Ensure `USE_INCREMENTAL_CLUSTERING=0` (or unset)
2. Restart PM2 (or your process manager):
   ```bash
   pm2 restart all
   ```
3. System should behave **exactly like before** (DBSCAN, no streaming yet).

---

## Step 8 — Post-Switch Smoke Test

- [ ] API responds
- [ ] No errors in logs
- [ ] Sample queries return expected data
- [ ] Ingestion still works
- [ ] Dashboard loads

---

## Step 9 — Run Stable for 24h

- [ ] Monitor logs
- [ ] No missing data
- [ ] No migration anomalies
- [ ] Queries normal

**Do not enable streaming until this is confirmed.**

---

## Step 10 — Enable Streaming (Optional, after stability)

When confident:

1. Set `USE_INCREMENTAL_CLUSTERING=1`
2. Restart:
   ```bash
   pm2 restart all
   ```
3. Queue and assigner start; shadow mode begins
4. DBSCAN still active for now

---

## Rollback Plan

If anything goes wrong **before** you're confident:

1. Point `DATABASE_URL` back to **OLD** database
2. Restart PM2
3. Investigate; fix; retry migration when ready

**Do not delete OLD database until 24h+ of stability on NEW.**

---

## What You Must NOT Do

- ❌ Run `CREATE EXTENSION vector` on Railway default Postgres if it's unsupported
- ❌ Run incremental assigner without pgvector
- ❌ Drop OLD database before validation and stability
- ❌ Point app at NEW DB without dump → restore → migrate
- ❌ Skip validation steps

---

## Quick Reference: Environment Variables

| Variable | When |
|----------|------|
| `OLD_DATABASE_URL` | Current production DB (for dump) |
| `NEW_DATABASE_URL` | Railway pgvector DB (for restore, migrate, then app) |
| `DATABASE_URL` | What the app uses; switch only after Steps 1–6 |
| `USE_INCREMENTAL_CLUSTERING` | Keep `0` until Step 10 |

---

## Related Docs

- [MIGRATION_PLAN_STREAMING_INCREMENTAL_ARCHITECTURE.md](./MIGRATION_PLAN_STREAMING_INCREMENTAL_ARCHITECTURE.md) — Architecture and phases
- [scripts/migrate_to_pgvector.sh](../scripts/migrate_to_pgvector.sh) — Semi-automated dump/restore script
