"""
Phase 2 (database disaster recovery hardening). Wraps `alembic upgrade head`
in a Postgres session-level advisory lock.

Why this exists: during the 2026-09-12 database cutover, Render briefly ran
two container instances of this same service at once (the tail end of the
previous deploy shutting down while the new one started) -- both attempting
`alembic upgrade head` against the same database within seconds of each
other (see docs/RELIABILITY.md's Render deploy-flakiness note and
docs/operations/DATABASE_RECOVERY.md section 20's audit). That specific
incident's actual crash was a separate DATABASE_URL/driver issue, not a
migration collision -- but the *window* for a genuine concurrent-migration
race is real on this architecture (a single Render instance whose deploys
briefly overlap old and new containers), and Alembic has no built-in
protection against two processes both deciding "the current revision needs
upgrading" at the same moment.

A session-level Postgres advisory lock (`pg_advisory_lock`) is the smallest
fix that closes this window: the second process simply blocks until the
first finishes and releases the lock (by disconnecting), rather than racing
it. No new infrastructure, no new dependency (asyncpg is already a
dependency), no change to the migrations themselves.

The lock is intentionally coarse (one fixed key for "run migrations on this
database") -- there is exactly one thing this needs to serialize.
"""
import asyncio
import os
import subprocess
import sys

import asyncpg

# Arbitrary fixed key. Only needs to be unique enough not to collide with
# some other advisory lock user on the same database -- there is none here.
MIGRATION_LOCK_KEY = 872_346_501


async def _run_with_lock() -> int:
    database_url = os.environ["DATABASE_URL"]
    # asyncpg needs a plain postgresql:// URL (or postgres://), not the
    # app's postgresql+asyncpg:// -- strip the driver suffix the same way
    # scripts/backup_db.sh's docstring already tells operators to.
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(dsn)
    try:
        print(f"Acquiring migration advisory lock ({MIGRATION_LOCK_KEY})...", flush=True)
        await conn.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_KEY)
        print("Lock acquired. Running alembic upgrade head...", flush=True)
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])
        return result.returncode
    finally:
        # Session-level pg_advisory_lock is released automatically when the
        # connection closes, but release explicitly first for a clean log line
        # and to free the lock immediately rather than waiting on GC/network
        # teardown timing.
        try:
            await conn.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_KEY)
        except Exception:
            pass  # connection may already be in a bad state if alembic crashed hard; closing below still releases it
        await conn.close()
        print("Migration lock released.", flush=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(_run_with_lock()))
