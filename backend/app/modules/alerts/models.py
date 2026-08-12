import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class AlertConditionType(str, Enum):
    ENDPOINT_DOWN = "endpoint_down"
    QUEUE_FULL = "queue_full"
    DLQ_SPIKE = "dlq_spike"
    API_KEY_LEAK_SUSPICION = "api_key_leak_suspicion"
    HIGH_LATENCY = "high_latency"
    REPEATED_FAILURES = "repeated_failures"
    BILLING_THRESHOLD = "billing_threshold"
    RATE_LIMIT_ABUSE = "rate_limit_abuse"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    SMS = "sms"  # architecture hook -- see common/notification_client.py


class AlertDeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"  # deduplicated/throttled -- no send attempted


DEFAULT_THROTTLE_WINDOW_MINUTES = 15


class AlertRule(Base, UUIDPKMixin, TimestampMixin):
    """Per-org alert preference: which condition, which channel, how sensitive, how noisy."""

    __tablename__ = "alert_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default=AlertSeverity.WARNING.value)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    threshold_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    throttle_window_minutes: Mapped[int] = mapped_column(default=DEFAULT_THROTTLE_WINDOW_MINUTES, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AlertEvent(Base, UUIDPKMixin, TimestampMixin):
    """Alert history -- one row per triggered (and possibly delivered) alert."""

    __tablename__ = "alert_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    alert_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True
    )
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default=AlertDeliveryStatus.PENDING.value)
    delivery_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
