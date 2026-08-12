import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class InvoiceStatus(str, Enum):
    PAID = "paid"
    OPEN = "open"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class Plan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "plans"

    tier: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # null for Free (no Stripe object)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    max_deliveries_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unlimited
    max_endpoints: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unlimited
    log_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    rate_limit_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)

    allow_overage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_advanced_analytics: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_priority_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_sso: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Subscription(Base, UUIDPKMixin, TimestampMixin):
    """One active subscription per org -- the source of truth for which Plan applies."""

    __tablename__ = "subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SubscriptionStatus.ACTIVE.value)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invoice(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    stripe_invoice_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageRecord(Base, UUIDPKMixin, TimestampMixin):
    """
    Periodic rollup of delivery usage for a billing period -- avoids re-scanning all
    of delivery_jobs on every plan-limit check. Refreshed on-demand (see
    billing/service.py get_current_usage) rather than only via a scheduled job, so
    limits are always checked against accurate current-period data; a cron refresh
    can be layered on top later purely as a caching optimization.
    """

    __tablename__ = "usage_records"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
