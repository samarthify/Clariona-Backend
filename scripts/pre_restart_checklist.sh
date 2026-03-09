#!/bin/bash
# Pre-restart checklist: backup, migrations, config flags, Redis check.
# Run from project root. Requires: DATABASE_URL (from config/.env or env), venv, psql. Uses Python redis package for Redis check.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"

cd "$PROJECT_ROOT"

# Load and export DATABASE_URL from config/.env if present
if [ -f config/.env ]; then
  set -a
  # shellcheck source=/dev/null
  source config/.env 2>/dev/null || true
  set +a
  export DATABASE_URL  # ensure it's exported to child processes
fi

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL not set. Export it or ensure config/.env contains it."
  exit 1
fi

echo "=== 1. Backup ==="
echo "Skipped (Railway backups enabled)."

echo ""
echo "=== 2. Migrations ==="
source venv/bin/activate
cd src && alembic upgrade head && cd ..
echo "Migrations complete."

echo ""
echo "=== 3. Set clustering flags to false (use_incremental, use_global, crisis_detector) ==="
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
-- use_incremental_clustering: insert or force to false
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active, default_value, created_at, updated_at)
VALUES ('clustering', 'use_incremental_clustering', 'false'::jsonb, 'bool', 'Incremental clustering via Pinecone', true, 'false'::jsonb, now(), now())
ON CONFLICT (category, config_key) DO UPDATE SET config_value = 'false'::jsonb;

-- use_global_clustering: insert or force to false
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active, default_value, created_at, updated_at)
VALUES ('clustering', 'use_global_clustering', 'false'::jsonb, 'bool',
        'Global clustering (Pinecone user_id-only). Set true only after Pinecone validated.', true, 'false'::jsonb, now(), now())
ON CONFLICT (category, config_key) DO UPDATE SET config_value = 'false'::jsonb;

-- crisis_detector_enabled: insert or force to false
INSERT INTO system_configurations (category, config_key, config_value, config_type, description, is_active, default_value, created_at, updated_at)
VALUES ('clustering', 'crisis_detector_enabled', 'false'::jsonb, 'bool',
        'Crisis evaluator/dispatcher. Set true only when validated.', true, 'false'::jsonb, now(), now())
ON CONFLICT (category, config_key) DO UPDATE SET config_value = 'false'::jsonb;
SQL
echo "Config flags set (all three false)."

echo ""
echo "=== 4. Redis check ==="
if python -c "
import os
import sys
try:
    import redis
    url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    r = redis.from_url(url, decode_responses=True)
    r.ping()
    sys.exit(0)
except Exception as e:
    print(f'Redis: not responding ({e}). VelocityTracker will degrade gracefully.', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
  echo "Redis: OK"
else
  echo "Redis: not responding (VelocityTracker will degrade gracefully)"
fi

echo ""
echo "=== Checklist complete. Next: pm2 restart all && pm2 logs --lines 100 ==="
