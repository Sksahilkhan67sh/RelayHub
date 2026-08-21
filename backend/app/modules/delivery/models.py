import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    # See the matching TYPE_CHECKING import in events/models.py -- same circular-import
    # avoidance, mirrored here so mypy can resolve the "Event" string forward-ref below.
    from app.modules.endpoints.models import Endpoint  # noqa: F401
    from app.modules.events.models import Event  # noqa: F401


class DeliveryJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    RETRYING = "retrying"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ErrorCategory(str, Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    TRANSIENT_HTTP_ERROR = "transient_http_error"  # 408/429/5xx
    PERMANENT_HTTP_ERROR = "permanent_http_error"  # other 4xx
    SSRF_BLOCKED = "ssrf_blocked"
    SIGNING_ERROR = "signing_error"


class DeliveryJob(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """
    One row per (event, matching endpoint) pair. This table IS "the queue" in the
    architecture sense (API -> database -> queue -> worker): the Redis list just holds
    job IDs to wake workers efficiently, but this table is the durable source of truth
    -- a worker that crashes mid-delivery can always recover state from here.

    Attempt-level detail (request/response snapshots, timing, worker ID, etc.) lives
    in `delivery_attempts`, added in Phase 3e alongside the worker that creates them.
    """

    __tablename__ = "delivery_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DeliveryJobStatus.QUEUED.value, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Lease fields (Phase 2 follow-up): which worker process's CAS claim last moved
    # this job to `processing`, and when. Set in `_claim_job`, matched against
    # `worker_heartbeats.worker_id` by `reconcile_stuck_jobs` to distinguish "the
    # owning worker is still alive, this is just a slow request" from "the owning
    # worker is gone, this job is genuinely abandoned" -- a real lease rather than
    # pure elapsed time. Left populated after the job leaves `processing` (not
    # cleared) purely as forensic history of who last touched it; only meaningful
    # while status == processing.
    claimed_by_worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped["Event"] = relationship(back_populates="delivery_jobs")  # noqa: F821
    # One-directional (no back_populates -- Endpoint doesn't need a `delivery_jobs`
    # collection for anything today) relationship added specifically so the API layer
    # can read endpoint.max_retry_attempts to compute each job's effective max_attempts,
    # without a second query per job. Purely additive: no new column, no migration.
    endpoint: Mapped["Endpoint"] = relationship(viewonly=True)  # noqa: F821
    attempts: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="job", order_by="DeliveryAttempt.attempt_number")


class DeliveryAttempt(Base, UUIDPKMixin, TimestampMixin):
    """
    Full record of a single delivery attempt, per spec section 5's field list. This is
    what powers the Delivery Detail view and Delivery Logs search in later phases.
    """

    __tablename__ = "delivery_attempts"

    delivery_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_body_truncated: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    error_category: Mapped[str] = mapped_column(String(30), nullable=False, default=ErrorCategory.NONE.value)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    destination_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    job: Mapped["DeliveryJob"] = relationship(back_populates="attempts")
