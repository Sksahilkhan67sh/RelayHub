import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class AbuseReportStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FeatureFlag(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    is_enabled_globally: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FeatureFlagOverride(Base, UUIDPKMixin, TimestampMixin):
    """Per-org override -- lets platform admins enable/disable a flag for one org independent of the global default."""

    __tablename__ = "feature_flag_overrides"
    __table_args__ = (UniqueConstraint("flag_id", "organization_id", name="uq_flag_org_override"),)

    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)


class AbuseReport(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "abuse_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AbuseReportStatus.OPEN.value)
    resolution_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
