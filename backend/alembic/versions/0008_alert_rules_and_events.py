"""alert_rules and alert_events

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("channel_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("threshold_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("throttle_window_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alert_rules_organization_id", "alert_rules", ["organization_id"])
    op.create_index("ix_alert_rules_condition_type", "alert_rules", ["condition_type"])

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("delivery_error", sa.String(1000), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alert_events_organization_id", "alert_events", ["organization_id"])
    op.create_index("ix_alert_events_condition_type", "alert_events", ["condition_type"])
    op.create_index("ix_alert_events_resource_id", "alert_events", ["resource_id"])
    op.create_index("ix_alert_events_dedup_key", "alert_events", ["dedup_key"])


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
