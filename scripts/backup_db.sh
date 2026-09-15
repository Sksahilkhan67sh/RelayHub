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

# Accept whatever scheme is present (app's postgresql+asyncpg://, plain
# postgresql://, or anything else) -- pg_dump/libpq only understands
# postgresql:// or postgres://. Rather than matching the scheme text
# literally (a bash glob substitution AND a sed literal-text substitution
# both failed to match against the real secret in this repo's GitHub
# Actions runner, despite the text visually appearing correct in every
# diagnostic -- most likely an invisible/lookalike character introduced by
# a copy-paste somewhere along the way, e.g. a non-ASCII '+' look-alike),
# unconditionally discard everything up to and including the first "://"
# (reliably locatable regardless of what the scheme text actually
# contains) and prepend a known-good "postgresql://". This sidesteps the
# scheme-matching problem entirely instead of trying to further diagnose
# an encoding issue in a value this script should never print or store.
DATABASE_URL="postgresql://$(printf '%s' "$DATABASE_URL" | sed 's#.*://##')"

OUTPUT_FILE="$OUTPUT_DIR/relayhub-${TIMESTAMP}.dump"

echo "Backing up to $OUTPUT_FILE ..."
pg_dump --format=custom --compress=9 --file="$OUTPUT_FILE" "$DATABASE_URL"
echo "Done: $OUTPUT_FILE ($(du -h "$OUTPUT_FILE" | cut -f1))"

# Retention is deployment-specific (S3 lifecycle policy, cron + find -mtime, etc.)
# -- intentionally not decided here; see docs/self-hosting/README.md's Backup &
# Recovery section for the documented production procedure.
