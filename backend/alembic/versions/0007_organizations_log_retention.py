"""add log_retention_days to organizations

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("log_retention_days", sa.Integer, nullable=False, server_default="30")
    )


def downgrade() -> None:
    op.drop_column("organizations", "log_retention_days")
