"""blog_posts_and_job_postings

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("excerpt", sa.String(500), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("author_name", sa.String(150), nullable=False),
        sa.Column("author_role", sa.String(150), nullable=False),
        sa.Column("read_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("body", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.String(40), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_blog_posts_slug", "blog_posts", ["slug"])
    op.create_index("ix_blog_posts_status", "blog_posts", ["status"])

    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("team", sa.String(150), nullable=False),
        sa.Column("location", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_postings_is_active", "job_postings", ["is_active"])


def downgrade() -> None:
    op.drop_table("job_postings")
    op.drop_table("blog_posts")
