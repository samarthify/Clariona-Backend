#!/bin/bash
# Production DB migration: OLD → Railway pgvector
# Usage: Set OLD_DATABASE_URL and NEW_DATABASE_URL, then run steps as needed.
#
# Steps:
#   1. ./migrate_to_pgvector.sh dump     - Dump OLD DB to prod.dump
#   2. ./migrate_to_pgvector.sh restore  - Restore prod.dump into NEW DB
#   3. ./migrate_to_pgvector.sh migrate  - Run alembic upgrade on NEW DB
#   4. ./migrate_to_pgvector.sh validate - Validate NEW DB
#
# Or: ./migrate_to_pgvector.sh all  (runs dump → restore → migrate → validate)
#
# IMPORTANT: Do NOT point the app at NEW until validation passes.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DUMP_FILE="${DUMP_FILE:-$SCRIPT_DIR/prod.dump}"

check_urls() {
    if [[ -z "$OLD_DATABASE_URL" ]]; then
        echo "ERROR: OLD_DATABASE_URL not set. Export it first."
        exit 1
    fi
    if [[ -z "$NEW_DATABASE_URL" ]]; then
        echo "ERROR: NEW_DATABASE_URL not set. Export it first."
        exit 1
    fi
}

step_dump() {
    echo "=== Step: Dump OLD DB ==="
    check_urls
    echo "Dumping to $DUMP_FILE (custom format -Fc)"
    pg_dump "$OLD_DATABASE_URL" -Fc -f "$DUMP_FILE"
    echo "Done. Size: $(ls -lh "$DUMP_FILE" | awk '{print $5}')"
}

step_restore() {
    echo "=== Step: Restore into NEW DB ==="
    check_urls
    if [[ ! -f "$DUMP_FILE" ]]; then
        echo "ERROR: Dump file not found: $DUMP_FILE"
        exit 1
    fi
    echo "Restoring from $DUMP_FILE"
    pg_restore \
        --no-owner \
        --no-privileges \
        -d "$NEW_DATABASE_URL" \
        "$DUMP_FILE" || true
    # pg_restore exits 1 on harmless warnings (e.g. extension/owner); data should be restored
    echo "Restore step finished. Review output above for any critical errors."
}

step_migrate() {
    echo "=== Step: Run Alembic on NEW DB ==="
    check_urls
    cd "$PROJECT_ROOT"
    export DATABASE_URL="$NEW_DATABASE_URL"
    alembic -c src/alembic.ini upgrade head
    echo "Migration completed."
}

step_validate() {
    echo "=== Step: Validate NEW DB ==="
    check_urls
    if ! command -v psql &>/dev/null; then
        echo "psql not found. Run validation manually:"
        echo "  psql \"\$NEW_DATABASE_URL\" -f $SCRIPT_DIR/validate_db_migration.sql"
        return 0
    fi
    psql "$NEW_DATABASE_URL" -f "$SCRIPT_DIR/validate_db_migration.sql"
    echo ""
    echo "Compare row counts with OLD DB. If they match, proceed to switch DATABASE_URL."
}

step_version_check() {
    echo "=== Version check (OLD vs NEW) ==="
    check_urls
    echo "OLD DB:"
    psql "$OLD_DATABASE_URL" -t -c "SELECT version();" 2>/dev/null || echo "(cannot connect)"
    echo ""
    echo "NEW DB:"
    psql "$NEW_DATABASE_URL" -t -c "SELECT version();" 2>/dev/null || echo "(cannot connect)"
}

case "${1:-}" in
    dump)     step_dump ;;
    restore)  step_restore ;;
    migrate)  step_migrate ;;
    validate) step_validate ;;
    versions) step_version_check ;;
    all)
        step_dump
        step_restore
        step_migrate
        step_validate
        ;;
    *)
        echo "Usage: $0 {dump|restore|migrate|validate|versions|all}"
        echo ""
        echo "Set env vars: OLD_DATABASE_URL, NEW_DATABASE_URL"
        echo "Optional: DUMP_FILE (default: scripts/prod.dump)"
        exit 1
        ;;
esac
