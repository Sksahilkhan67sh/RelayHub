#!/usr/bin/env bash
# RelayHub -- Postgres restore, from a dump produced by scripts/backup_db.sh.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/relayhub ./scripts/restore_db.sh <dump_file>
#
# This restores into whatever database DATABASE_URL points at. For a real
# recovery drill, point it at a *new, empty* database first and verify the
# application boots and reads correctly before ever pointing it at production.
#
# Not run in this development sandbox (no live Postgres instance available
# here) -- verify against a real database before relying on it in production.
set -euo pipefail

DUMP_FILE="${1:?Usage: restore_db.sh <dump_file>}"
: "${DATABASE_URL:?Set DATABASE_URL (postgresql://user:pass@host:5432/dbname)}"

if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

echo "Restoring $DUMP_FILE into $(echo "$DATABASE_URL" | sed -E 's#://[^@]+@#://***:***@#') ..."
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$DATABASE_URL" "$DUMP_FILE"
echo "Restore complete. Run 'alembic upgrade head' next to apply any migrations newer than the dump."
