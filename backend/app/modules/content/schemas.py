from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.content.models import ContentStatus

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CreateBlogPostRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=200)
    title: str = Field(min_length=3, max_length=300)
    excerpt: str = Field(min_length=3, max_length=500)
    category: str = Field(min_length=1, max_length=50)
    author_name: str = Field(min_length=1, max_length=150)
    author_role: str = Field(min_length=1, max_length=150)
    read_minutes: int = Field(default=5, ge=1, le=120)
    body: list[str] = Field(default_factory=list, description="One paragraph per array element.")
    status: ContentStatus = ContentStatus.DRAFT
    published_at: str | None = Field(default=None, max_length=40, description='Editorial display date, e.g. "August 14, 2026". Independent of created_at/updated_at.')

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase letters, numbers, and single hyphens only (e.g. 'my-post-title')")
        return v


class UpdateBlogPostRequest(BaseModel):
    slug: str | None = Field(default=None, min_length=3, max_length=200)
    title: str | None = Field(default=None, min_length=3, max_length=300)
    excerpt: str | None = Field(default=None, min_length=3, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    author_name: str | None = Field(default=None, min_length=1, max_length=150)
    author_role: str | None = Field(default=None, min_length=1, max_length=150)
    read_minutes: int | None = Field(default=None, ge=1, le=120)
    body: list[str] | None = None
    status: ContentStatus | None = None
    published_at: str | None = Field(default=None, max_length=40)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase letters, numbers, and single hyphens only (e.g. 'my-post-title')")
        return v


class BlogPostOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    excerpt: str
    category: str
    author_name: str
    author_role: str
    read_minutes: int
    body: list[str]
    status: ContentStatus
    published_at: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateJobPostingRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    team: str = Field(min_length=1, max_length=150)
    location: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=20_000)
    is_active: bool = True


class UpdateJobPostingRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    team: str | None = Field(default=None, min_length=1, max_length=150)
    location: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=20_000)
    is_active: bool | None = None


class JobPostingOut(BaseModel):
    id: uuid.UUID
    title: str
    team: str
    location: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
