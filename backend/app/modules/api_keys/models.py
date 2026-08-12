import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import StringList


class ApiKeyEnvironment(str, Enum):
    LIVE = "live"
    TEST = "test"


class ApiKeyScope(str, Enum):
    EVENTS_WRITE = "events:write"
    EVENTS_READ = "events:read"
    DELIVERIES_READ = "deliveries:read"
    ENDPOINTS_READ = "endpoints:read"
    ENDPOINTS_WRITE = "endpoints:write"
    FULL_ACCESS = "*"


DEFAULT_SCOPES = [ApiKeyScope.EVENTS_WRITE.value, ApiKeyScope.EVENTS_READ.value]


class ApiKey(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default=ApiKeyEnvironment.TEST.value)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # per-key rate limit override; null = use plan default
    rate_limit_per_minute: Mapped[int | None] = mapped_column(nullable=True)

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            from datetime import timezone as _tz

            expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=_tz.utc)
            from datetime import datetime as _dt

            if expires <= _dt.now(_tz.utc):
                return False
        return True

    def has_scope(self, required: str) -> bool:
        return ApiKeyScope.FULL_ACCESS.value in self.scopes or required in self.scopes
