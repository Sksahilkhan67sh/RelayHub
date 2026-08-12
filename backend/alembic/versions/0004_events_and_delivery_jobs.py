"""event_types, events, delivery_jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("version", sa.String(10), nullable=False, server_default="v1"),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_event_type_name"),
    )
    op.create_index("ix_event_types_organization_id", "event_types", ["organization_id"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(150), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False, server_default="test"),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_org_idempotency_key"),
    )
    op.create_index("ix_events_organization_id", "events", ["organization_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_request_id", "events", ["request_id"])

    op.create_table(
        "delivery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_delivery_jobs_organization_id", "delivery_jobs", ["organization_id"])
    op.create_index("ix_delivery_jobs_event_id", "delivery_jobs", ["event_id"])
    op.create_index("ix_delivery_jobs_endpoint_id", "delivery_jobs", ["endpoint_id"])
    op.create_index("ix_delivery_jobs_status", "delivery_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("delivery_jobs")
    op.drop_table("events")
    op.drop_table("event_types")
