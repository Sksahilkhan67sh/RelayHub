from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.newsletter.models import NewsletterSubscriber

ALREADY_SUBSCRIBED_MESSAGE = "You're already subscribed."
SUBSCRIBED_MESSAGE = "Thanks -- you're subscribed."
RESUBSCRIBED_MESSAGE = "Welcome back -- you're subscribed again."


async def subscribe(db: AsyncSession, *, email: str) -> tuple[str, str]:
    """
    Idempotent by design: submitting the same email twice is a normal, expected
    user action (double-clicking submit, signing up on two different posts), not
    an error -- so this never raises a conflict, it just reports back which of
    the three real outcomes happened.
    """
    normalized_email = email.strip().lower()
    # tenant-scope: safe - NewsletterSubscriber is not tenant-scoped (no organization_id
    # column); these are marketing-site visitors, not RelayHub customer accounts.
    existing = (
        await db.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == normalized_email))
    ).scalar_one_or_none()

    if existing is None:
        db.add(NewsletterSubscriber(email=normalized_email))
        await db.commit()
        return "subscribed", SUBSCRIBED_MESSAGE

    if existing.unsubscribed_at is not None:
        existing.unsubscribed_at = None
        await db.commit()
        return "resubscribed", RESUBSCRIBED_MESSAGE

    return "already_subscribed", ALREADY_SUBSCRIBED_MESSAGE


async def unsubscribe(db: AsyncSession, *, email: str) -> bool:
    normalized_email = email.strip().lower()
    existing = (
        await db.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == normalized_email))
    ).scalar_one_or_none()
    if existing is None or existing.unsubscribed_at is not None:
        return False
    existing.unsubscribed_at = datetime.now(timezone.utc)
    await db.commit()
    return True
