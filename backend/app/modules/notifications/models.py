import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin, org_fk


class Notification(Base, UUIDPKMixin, TimestampMixin):
    """
    In-app notification for a single (user, organization) pair -- mirrors
    AuthContext's (user_id, organization_id) tenant boundary exactly, since a
    user can belong to multiple orgs (see Membership) and a notification is
    always about something that happened in one specific org.

    `type` is a short dotted event key (e.g. "member.joined",
    "abuse_report.created") so the frontend can route/icon by type without
    parsing `title`. `resource_type`/`resource_id` optionally point at the
    thing the notification is about, for "go to X" navigation -- both are
    nullable since not every notification links to a concrete resource.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_org_created", "user_id", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
