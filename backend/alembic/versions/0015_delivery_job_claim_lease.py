"""delivery_jobs: claimed_by_worker_id, claimed_at

Phase 2 reliability hardening, follow-up: ties reconcile_stuck_jobs' stuck-job
detection to the real worker_heartbeats table (added in 0014) instead of relying
solely on a time-based heuristic over DeliveryJob.updated_at. These columns record
which worker process claimed a job and when, so reconciliation can ask "is the
specific worker holding this job still alive" rather than only "how long has it
been processing".

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_jobs", sa.Column("claimed_by_worker_id", sa.String(200), nullable=True))
    op.add_column("delivery_jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_delivery_jobs_claimed_by_worker_id", "delivery_jobs", ["claimed_by_worker_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_jobs_claimed_by_worker_id", table_name="delivery_jobs")
    op.drop_column("delivery_jobs", "claimed_at")
    op.drop_column("delivery_jobs", "claimed_by_worker_id")
