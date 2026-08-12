import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    # Import-time-only: avoids the real circular import between events/models.py and
    # delivery/models.py (Event <-> DeliveryJob reference each other) while still letting
    # mypy resolve the "DeliveryJob" string forward-ref below.
    from app.modules.delivery.models import DeliveryJob  # noqa: F401

BUILT_IN_EVENT_TYPES = [
    "order.created",
    "order.updated",
    "payment.success",
    "payment.failed",
    "invoice.created",
    "invoice.paid",
    "subscription.created",
    "subscription.cancelled",
    "refund.created",
    "shipment.created",
    "shipment.delivered",
]


class EventType(Base, UUIDPKMixin, TimestampMixin):
    """
    Catalog of event types an org has published, built-in or custom. Auto-registered
    the first time an org publishes a given type (see events/service.py). This is a
    discoverability/versioning catalog, not the enforcement mechanism -- endpoint
    subscription matching (events/service.py `_matching_endpoints`) compares against
    the raw event type string directly.
    """

    __tablename__ = "event_types"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_event_type_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[str] = mapped_column(String(10), nullable=False, default="v1")
    is_custom: Mapped[bool] = mapped_column(default=True, nullable=False)


class Event(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_org_idempotency_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="test")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    delivery_jobs: Mapped[list["DeliveryJob"]] = relationship(back_populates="event")  # noqa: F821
