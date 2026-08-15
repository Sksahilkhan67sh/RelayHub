from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_platform_admin
from app.modules.content import service
from app.modules.content.schemas import (
    BlogPostOut,
    CreateBlogPostRequest,
    CreateJobPostingRequest,
    JobPostingOut,
    UpdateBlogPostRequest,
    UpdateJobPostingRequest,
)

# Two routers: admin (full CRUD, every status/inactive posting included, platform-admin
# only) and public (published/active only, no auth -- these back the marketing site's
# /blog and /careers pages, replacing what used to be static data in the frontend).
admin_router = APIRouter(prefix="/admin/content", tags=["admin", "content"])
public_router = APIRouter(prefix="/content", tags=["content"])


# ---------------------------------------------------------------------------
# Admin: blog posts
# ---------------------------------------------------------------------------


@admin_router.post("/blog-posts", response_model=BlogPostOut, status_code=status.HTTP_201_CREATED)
async def admin_create_blog_post(
    payload: CreateBlogPostRequest,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_blog_post(db, data=payload)


@admin_router.get("/blog-posts", response_model=list[BlogPostOut])
async def admin_list_blog_posts(
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_blog_posts_admin(db)


@admin_router.patch("/blog-posts/{post_id}", response_model=BlogPostOut)
async def admin_update_blog_post(
    post_id: uuid.UUID,
    payload: UpdateBlogPostRequest,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_blog_post(db, post_id=post_id, data=payload)


@admin_router.delete("/blog-posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_blog_post(
    post_id: uuid.UUID,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_blog_post(db, post_id=post_id)


# ---------------------------------------------------------------------------
# Admin: job postings
# ---------------------------------------------------------------------------


@admin_router.post("/job-postings", response_model=JobPostingOut, status_code=status.HTTP_201_CREATED)
async def admin_create_job_posting(
    payload: CreateJobPostingRequest,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_job_posting(db, data=payload)


@admin_router.get("/job-postings", response_model=list[JobPostingOut])
async def admin_list_job_postings(
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_job_postings_admin(db)


@admin_router.patch("/job-postings/{posting_id}", response_model=JobPostingOut)
async def admin_update_job_posting(
    posting_id: uuid.UUID,
    payload: UpdateJobPostingRequest,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_job_posting(db, posting_id=posting_id, data=payload)


@admin_router.delete("/job-postings/{posting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_job_posting(
    posting_id: uuid.UUID,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_job_posting(db, posting_id=posting_id)


# ---------------------------------------------------------------------------
# Public: read-only, no auth -- backs the marketing site
# ---------------------------------------------------------------------------


@public_router.get("/blog-posts", response_model=list[BlogPostOut])
async def public_list_blog_posts(db: AsyncSession = Depends(get_db)):
    return await service.list_blog_posts_public(db)


@public_router.get("/blog-posts/{slug}", response_model=BlogPostOut)
async def public_get_blog_post(slug: str, db: AsyncSession = Depends(get_db)):
    return await service.get_blog_post_by_slug_public(db, slug)


@public_router.get("/job-postings", response_model=list[JobPostingOut])
async def public_list_job_postings(db: AsyncSession = Depends(get_db)):
    return await service.list_job_postings_public(db)
