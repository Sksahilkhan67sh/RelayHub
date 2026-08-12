"""admin: feature_flags, feature_flag_overrides, abuse_reports

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("is_enabled_globally", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "feature_flag_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("flag_id", "organization_id", name="uq_flag_org_override"),
    )
    op.create_index("ix_feature_flag_overrides_flag_id", "feature_flag_overrides", ["flag_id"])
    op.create_index("ix_feature_flag_overrides_organization_id", "feature_flag_overrides", ["organization_id"])

    op.create_table(
        "abuse_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("reported_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.String(2000), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_abuse_reports_organization_id", "abuse_reports", ["organization_id"])


def downgrade() -> None:
    op.drop_table("abuse_reports")
    op.drop_table("feature_flag_overrides")
    op.drop_table("feature_flags")
