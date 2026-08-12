import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.db.types import StringList

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_FAILURE_STREAK_THRESHOLD = 10  # consecutive failures before auto-pausing an endpoint


class EndpointEnvironment(str, Enum):
    LIVE = "live"
    TEST = "test"


class EndpointHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # some recent failures, not yet paused
    UNHEALTHY = "unhealthy"  # circuit-broken / auto-paused after repeated failures
    UNKNOWN = "unknown"  # no deliveries attempted yet


class Endpoint(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "endpoints"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default=EndpointEnvironment.TEST.value)

    custom_headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_TIMEOUT_SECONDS)
    subscribed_event_types: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    ip_allowlist: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tls_verification_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Retry policy override (null fields fall back to org/plan default retry schedule)
    max_retry_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Health / circuit breaker tracking
    health_status: Mapped[str] = mapped_column(String(20), nullable=False, default=EndpointHealth.UNKNOWN.value)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    secrets: Mapped[list["EndpointSecret"]] = relationship(back_populates="endpoint", order_by="EndpointSecret.created_at.desc()")


class EndpointSecret(Base, UUIDPKMixin, TimestampMixin):
    """
    Signing secrets for HMAC verification. Supports rotation with a grace period:
    the old secret stays valid (signatures verified against it too) until
    `grace_period_ends_at`, after which only the new secret is accepted. Exactly one
    row per endpoint should have `is_primary=True` at a time -- that's the one used
    to SIGN outgoing requests; all non-expired rows are accepted when VERIFYING
    (relevant for customer-side verification docs, not RelayHub's own delivery, but
    kept here since the pattern is shared).
    """

    __tablename__ = "endpoint_secrets"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encrypted_secret: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    endpoint: Mapped["Endpoint"] = relationship(back_populates="secrets")
