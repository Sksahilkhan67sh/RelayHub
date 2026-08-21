"""worker_heartbeats

Phase 2 reliability hardening: replaces the "not tracked yet" worker-health gap
documented in admin/service.py with a real per-worker liveness table.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("hostname", sa.String(200), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_worker_heartbeats_worker_id", "worker_heartbeats", ["worker_id"], unique=True)
    op.create_index("ix_worker_heartbeats_last_heartbeat_at", "worker_heartbeats", ["last_heartbeat_at"])


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
