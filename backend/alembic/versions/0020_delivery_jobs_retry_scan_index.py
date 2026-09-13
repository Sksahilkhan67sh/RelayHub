"""add composite (status, next_attempt_at) index on delivery_jobs

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-13

Phase 1 reliability hardening. app/modules/retry/scheduler.py's
enqueue_due_retries runs every 10 seconds (celery beat, forever) with:

    WHERE status = 'retrying' AND next_attempt_at IS NOT NULL AND next_attempt_at <= :now

`delivery_jobs.status` already has its own single-column index, so this query
is not doing a full table scan today -- but it is doing an index scan on
`status` and then filtering `next_attempt_at` row-by-row, which degrades as
the retrying-job count grows. This composite index lets Postgres do a single
index range scan for exactly the rows due right now.

Evidence this is the specific query pattern justifying it (not a speculative
index): see the docstring on `enqueue_due_retries` and the accompanying
`test_scanner_enqueues_only_due_jobs` test.

Deliberately NOT adding an (organization_id, status, completed_at) index in
this migration: no query in the current codebase filters on that exact triple.
The nearest real query (logs/retention.py's cleanup_expired_delivery_logs)
filters organization_id + completed_at only, with no status predicate
(completed_at IS NOT NULL already implies a terminal job), and at current
production data volumes (single-digit to low-hundreds of delivery_jobs per
org) isn't yet a demonstrated bottleneck. See docs/RELIABILITY.md.
"""
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_delivery_jobs_status_next_attempt_at",
        "delivery_jobs",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_jobs_status_next_attempt_at", table_name="delivery_jobs")
