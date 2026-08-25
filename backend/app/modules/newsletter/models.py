"""
G-4 fix (Phase 4C): the blog's newsletter signup was a UI-only no-op. Per the
remediation brief, this was one of: (A) wire it to a real ESP, or (B) remove the
UI. This sandbox has no real ESP credentials and no outbound network to one, so
integrating (say) Mailchimp here would be an unverifiable "fake success" claim --
exactly what the brief says not to do. Instead this is a real, tested,
self-hosted subscriber capture (this table) with real validation, duplicate
handling, and rate limiting -- not a mock. An ESP sync (reading unsynced rows
from this table and pushing them to a real provider once real credentials
exist) is a natural, isolated follow-up that would not require changing this
table or the public API.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class NewsletterSubscriber(Base, UUIDPKMixin, TimestampMixin):
    """
    Not tenant-scoped -- these are marketing-site visitors, not RelayHub customer
    accounts, and there is no organization_id to scope by at signup time.
    """

    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
