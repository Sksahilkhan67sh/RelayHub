#!/usr/bin/env bash
# RelayHub -- Postgres backup.
#
# Wraps pg_dump with the connection info already used by the app (DATABASE_URL),
# rather than introducing a separate backup-only credential scheme. Produces a
# single compressed custom-format dump, suitable for pg_restore.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/relayhub ./scripts/backup_db.sh [output_dir]
#
# Notes:
#   - Expects a plain `postgresql://` URL (pg_dump's own scheme), not the app's
#     `postgresql+asyncpg://` -- strip the `+asyncpg` if reusing the app's env var.
#   - Not run in this development sandbox (no live Postgres instance available
#     here) -- verify against a real database before relying on it in production.
set -euo pipefail

OUTPUT_DIR="${1:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUTPUT_DIR"

: "${DATABASE_URL:?Set DATABASE_URL (postgresql://user:pass@host:5432/dbname)}"

# Accept either scheme: pg_dump/libpq only understands postgresql:// (or
# postgres://), not the app's own postgresql+asyncpg:// -- normalize here
# instead of just documenting it, since a real backup attempt against
# production failed on exactly this (the secret was configured by reusing
# the app's DATABASE_URL value verbatim, which is a completely reasonable
# thing to do and shouldn't require remembering an extra manual edit).
# Uses sed rather than a bash parameter-expansion glob: a bash
# ${var/postgresql+asyncpg:\/\//postgresql://} substitution against the
# real secret value did not match reliably in this repo's GitHub Actions
# runner even though the literal substring was confirmed present at the
# expected position -- switched to sed's plain (non-extended) regex, where
# '+' is literal, matching on "postgresql+asyncpg" alone (no "://"
# adjacency requirement) for a simpler, more robust substitution.
DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed 's/postgresql+asyncpg/postgresql/')"

OUTPUT_FILE="$OUTPUT_DIR/relayhub-${TIMESTAMP}.dump"

echo "Backing up to $OUTPUT_FILE ..."
pg_dump --format=custom --compress=9 --file="$OUTPUT_FILE" "$DATABASE_URL"
echo "Done: $OUTPUT_FILE ($(du -h "$OUTPUT_FILE" | cut -f1))"

# Retention is deployment-specific (S3 lifecycle policy, cron + find -mtime, etc.)
# -- intentionally not decided here; see docs/self-hosting/README.md's Backup &
# Recovery section for the documented production procedure.
