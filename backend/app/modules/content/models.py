"""
Platform-global content: blog posts and job postings shown on the public marketing
site. Unlike almost every other model in this codebase, these are NOT org-scoped
(no organization_id) -- they belong to the RelayHub platform itself, not to any
customer's organization, so they're managed exclusively through platform-admin-only
routes (require_platform_admin), the same guard used for feature flags and abuse
reports in app/modules/admin.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.db.types import StringList


class ContentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class BlogPost(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "blog_posts"

    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    author_name: Mapped[str] = mapped_column(String(150), nullable=False)
    author_role: Mapped[str] = mapped_column(String(150), nullable=False)
    read_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # One paragraph per array element, matching how the previously-static blog data
    # was shaped (lib/blog-data.ts's body: string[]) -- keeps the reading/rendering
    # code on the frontend unchanged, only the data source moves to the API.
    body: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ContentStatus.DRAFT.value, index=True)
    # Distinct from created_at/updated_at (which track row mutation history):
    # published_at is the editorial date shown to readers, settable independently
    # so a post can be drafted days before its public date and backdated/scheduled.
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class JobPosting(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "job_postings"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    team: Mapped[str] = mapped_column(String(150), nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
