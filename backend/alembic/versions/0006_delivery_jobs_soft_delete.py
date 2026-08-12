"""add deleted_at to delivery_jobs (DLQ soft delete)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_jobs", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("delivery_jobs", "deleted_at")
