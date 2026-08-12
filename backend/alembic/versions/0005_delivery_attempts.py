"""delivery_attempts

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("response_headers", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("response_body_truncated", sa.String(4096), nullable=True),
        sa.Column("error_category", sa.String(30), nullable=False, server_default="none"),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("worker_id", sa.String(100), nullable=False),
        sa.Column("region", sa.String(50), nullable=False, server_default="local"),
        sa.Column("destination_ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_delivery_attempts_delivery_job_id", "delivery_attempts", ["delivery_job_id"])
    op.create_index("ix_delivery_attempts_organization_id", "delivery_attempts", ["organization_id"])


def downgrade() -> None:
    op.drop_table("delivery_attempts")
