"""
Phase 3 — AI Integration / Intelligence Layer: database models.

Deliberately does NOT duplicate anything analytics/ or delivery/ already own.
This module stores only the *derived* intelligence layer's own state:

  - point-in-time health snapshots (so health has history, not just "now")
  - detected anomalies (deterministic, evidence-attached)
  - incidents (correlated groups of anomalies) and their link table
  - root cause analyses (deterministic and/or AI-assisted, always evidence-attached)

All of it reads FROM DeliveryJob/DeliveryAttempt/Endpoint (see aggregation.py) but
never re-stores raw delivery data -- this is intelligence-on-top, not a second
source of truth.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"  # insufficient data -- never a guessed score


class AnomalyMetric(str, Enum):
    FAILURE_RATE = "failure_rate"
    LATENCY = "latency"
    RETRY_RATE = "retry_rate"
    DLQ_RATE = "dlq_rate"
    QUEUE_DEPTH = "queue_depth"
    TIMEOUT_RATE = "timeout_rate"
    STATUS_DISTRIBUTION = "status_distribution"


class AnomalyDirection(str, Enum):
    SPIKE = "spike"
    DROP = "drop"
    TREND = "trend"
    REGRESSION = "regression"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RECOVERING = "recovering"
    RESOLVED = "resolved"


class FailureCategory(str, Enum):
    DESTINATION_4XX = "destination_4xx"
    DESTINATION_5XX = "destination_5xx"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_FAILURE = "network_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    QUEUE_FAILURE = "queue_failure"
    WORKER_FAILURE = "worker_failure"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    CONFIRMED = "confirmed"
    HIGHLY_LIKELY = "highly_likely"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


class EndpointHealthSnapshot(Base, UUIDPKMixin, TimestampMixin):
    """
    One row per (endpoint, computed window). Written by the health-analysis job on a
    schedule (see workers/insight_tasks.py), not on every request -- dashboards read
    the latest snapshot(s) instead of recomputing across raw DeliveryAttempt rows.
    """

    __tablename__ = "endpoint_health_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False, index=True
    )

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=HealthStatus.UNKNOWN.value, index=True)
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # null when status == UNKNOWN
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    http_4xx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    http_5xx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    timeout_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    dlq_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p50_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p95_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Supporting signals that don't warrant their own columns (worker/queue health
    # summary, recent-change markers, etc.) -- kept structured so the API can pass
    # it straight through without a schema migration for every new signal.
    supporting_signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    endpoint: Mapped["object"] = relationship("Endpoint", viewonly=True)


class Anomaly(Base, UUIDPKMixin, TimestampMixin):
    """A single detected deviation from baseline. Cheap to create; not every
    anomaly becomes an incident -- see IncidentAnomaly / incident correlation."""

    __tablename__ = "insight_anomalies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=True, index=True
    )

    metric: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # List of {label, value} facts backing this anomaly -- e.g. raw counts used to
    # compute the rate, so the UI/API never has to re-derive "why" from scratch.
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Set once this anomaly has been folded into an incident (nullable: many
    # anomalies never escalate to incident status at all).
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Incident(Base, UUIDPKMixin, TimestampMixin):
    """Correlated group of anomalies for one endpoint (or org-wide signal) over a
    time window. This is the unit the RCA and recommendations attach to -- never
    create one of these per failed delivery; see incident_engine.py correlation."""

    __tablename__ = "incidents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=IncidentStatus.OPEN.value, index=True)
    failure_category: Mapped[str] = mapped_column(String(30), nullable=False, default=FailureCategory.UNKNOWN.value)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Stability-window recovery detection writes these; see incident_engine.py.
    recovering_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly", primaryjoin="Incident.id == Anomaly.incident_id", viewonly=True
    )
    rca_entries: Mapped[list["RootCauseAnalysis"]] = relationship(back_populates="incident")


class RootCauseAnalysis(Base, UUIDPKMixin, TimestampMixin):
    """Evidence-based RCA record. `source` distinguishes a deterministic
    (rule-based) RCA from one an AI provider helped produce -- the frontend must
    render these differently (FACT vs AI INFERENCE, see section 15 of the brief)."""

    __tablename__ = "insight_root_cause_analyses"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="deterministic")  # deterministic | ai
    likely_cause: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False, default=ConfidenceLevel.UNKNOWN.value)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Raw structured AI output (already validated) for audit/debugging -- never the
    # raw text response; see ai/schemas.py for the required shape.
    ai_raw_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="rca_entries")
