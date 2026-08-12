"""endpoints and endpoint_secrets

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False, server_default="test"),
        sa.Column("custom_headers", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="15"),
        sa.Column("subscribed_event_types", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("ip_allowlist", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tls_verification_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("max_retry_attempts", sa.Integer, nullable=True),
        sa.Column("health_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("consecutive_failure_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_endpoints_organization_id", "endpoints", ["organization_id"])

    op.create_table(
        "endpoint_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_secret", sa.String(500), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_endpoint_secrets_endpoint_id", "endpoint_secrets", ["endpoint_id"])


def downgrade() -> None:
    op.drop_table("endpoint_secrets")
    op.drop_table("endpoints")
