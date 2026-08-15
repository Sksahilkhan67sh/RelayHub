from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import BlogPost, ContentStatus, JobPosting
from app.modules.content.schemas import (
    CreateBlogPostRequest,
    CreateJobPostingRequest,
    UpdateBlogPostRequest,
    UpdateJobPostingRequest,
)

# ---------------------------------------------------------------------------
# Blog posts
# ---------------------------------------------------------------------------


async def create_blog_post(db: AsyncSession, *, data: CreateBlogPostRequest) -> BlogPost:
    post = BlogPost(**data.model_dump(exclude={"status"}), status=data.status.value)
    db.add(post)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A blog post with this slug already exists") from e
    await db.refresh(post)
    return post


async def _get_blog_post_or_404(db: AsyncSession, post_id: uuid.UUID) -> BlogPost:
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id, BlogPost.deleted_at.is_(None)))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    return post


async def update_blog_post(db: AsyncSession, *, post_id: uuid.UUID, data: UpdateBlogPostRequest) -> BlogPost:
    post = await _get_blog_post_or_404(db, post_id)
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None:
        updates["status"] = updates["status"].value
    for field, value in updates.items():
        setattr(post, field, value)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A blog post with this slug already exists") from e
    await db.refresh(post)
    return post


async def delete_blog_post(db: AsyncSession, *, post_id: uuid.UUID) -> None:
    post = await _get_blog_post_or_404(db, post_id)
    post.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def list_blog_posts_admin(db: AsyncSession) -> list[BlogPost]:
    """Every non-deleted post regardless of status -- for the admin list view."""
    result = await db.execute(select(BlogPost).where(BlogPost.deleted_at.is_(None)).order_by(BlogPost.created_at.desc()))
    return list(result.scalars().all())


async def list_blog_posts_public(db: AsyncSession) -> list[BlogPost]:
    """Published only -- for the public marketing site."""
    result = await db.execute(
        select(BlogPost)
        .where(BlogPost.deleted_at.is_(None), BlogPost.status == ContentStatus.PUBLISHED.value)
        .order_by(BlogPost.created_at.desc())
    )
    return list(result.scalars().all())


async def get_blog_post_by_slug_public(db: AsyncSession, slug: str) -> BlogPost:
    result = await db.execute(
        select(BlogPost).where(
            BlogPost.slug == slug, BlogPost.deleted_at.is_(None), BlogPost.status == ContentStatus.PUBLISHED.value
        )
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    return post


# ---------------------------------------------------------------------------
# Job postings
# ---------------------------------------------------------------------------


async def create_job_posting(db: AsyncSession, *, data: CreateJobPostingRequest) -> JobPosting:
    posting = JobPosting(**data.model_dump())
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def _get_job_posting_or_404(db: AsyncSession, posting_id: uuid.UUID) -> JobPosting:
    result = await db.execute(select(JobPosting).where(JobPosting.id == posting_id, JobPosting.deleted_at.is_(None)))
    posting = result.scalar_one_or_none()
    if posting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job posting not found")
    return posting


async def update_job_posting(db: AsyncSession, *, posting_id: uuid.UUID, data: UpdateJobPostingRequest) -> JobPosting:
    posting = await _get_job_posting_or_404(db, posting_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(posting, field, value)
    await db.commit()
    await db.refresh(posting)
    return posting


async def delete_job_posting(db: AsyncSession, *, posting_id: uuid.UUID) -> None:
    posting = await _get_job_posting_or_404(db, posting_id)
    posting.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def list_job_postings_admin(db: AsyncSession) -> list[JobPosting]:
    result = await db.execute(select(JobPosting).where(JobPosting.deleted_at.is_(None)).order_by(JobPosting.created_at.desc()))
    return list(result.scalars().all())


async def list_job_postings_public(db: AsyncSession) -> list[JobPosting]:
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.deleted_at.is_(None), JobPosting.is_active.is_(True))
        .order_by(JobPosting.created_at.desc())
    )
    return list(result.scalars().all())
