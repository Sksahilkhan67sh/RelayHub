"""add github_id to users (GitHub OAuth login)

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_id", sa.String(32), nullable=True))
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_column("users", "github_id")
