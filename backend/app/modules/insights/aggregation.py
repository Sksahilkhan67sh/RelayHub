"""
Phase 3 -- aggregation layer. This is the ONLY module in insights/ that queries
DeliveryJob/DeliveryAttempt/WorkerHeartbeat directly. Everything downstream
(health_analysis, anomaly_detection, incident_engine, failure_classification, rca)
consumes a WindowMetrics object and never touches raw delivery tables -- keeps the
"which table has this field" knowledge in one place, and keeps this the one spot to
optimize if query performance ever becomes an issue (see section 19 of the brief).

Deliberately reuses the same query shapes as app/modules/analytics/service.py
(percentiles.py, time-range filtering) rather than reinventing them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.admin.models import WorkerHeartbeat
from app.modules.analytics.percentiles import compute_percentiles
from app.modules.delivery.models import DeliveryAttempt, DeliveryJob, DeliveryJobStatus, ErrorCategory


@dataclass
class WindowMetrics:
    """Deterministic, evidence-carrying rollup of one endpoint's delivery behaviour
    over [window_start, window_end). Every rate is None (not 0.0) when sample_size
    is 0 or below INSIGHTS_MIN_SAMPLE_SIZE -- callers must not fabricate a rate from
    an empty or too-small sample (section 3: "never generate a score when there is
    insufficient data")."""

    organization_id: uuid.UUID
    endpoint_id: uuid.UUID | None
    window_start: datetime
    window_end: datetime

    sample_size: int = 0
    success_count: int = 0
    failure_count: int = 0
    http_4xx_count: int = 0
    http_5xx_count: int = 0
    timeout_count: int = 0
    connection_error_count: int = 0
    auth_failure_count: int = 0  # 401/403 subset of http_4xx_count
    rate_limited_count: int = 0  # 429 subset of http_4xx_count
    retry_count: int = 0  # attempts with attempt_number > 1
    dlq_count: int = 0  # distinct delivery jobs that hit dead_letter in-window
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None

    workers_total: int = 0
    workers_healthy: int = 0

    # Raw {http_status_or_bucket: count} -- feeds failure classification and RCA
    # evidence without a second query.
    status_breakdown: dict = field(default_factory=dict)

    def has_sufficient_data(self) -> bool:
        return self.sample_size >= settings.INSIGHTS_MIN_SAMPLE_SIZE

    @property
    def success_rate(self) -> float | None:
        return (self.success_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def failure_rate(self) -> float | None:
        return (self.failure_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def http_4xx_rate(self) -> float | None:
        return (self.http_4xx_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def http_5xx_rate(self) -> float | None:
        return (self.http_5xx_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def timeout_rate(self) -> float | None:
        return (self.timeout_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def retry_rate(self) -> float | None:
        return (self.retry_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def dlq_rate(self) -> float | None:
        return (self.dlq_count / self.sample_size) if self.has_sufficient_data() else None

    @property
    def worker_health_ratio(self) -> float | None:
        return (self.workers_healthy / self.workers_total) if self.workers_total else None


_AUTH_STATUSES = {401, 403}
_RATE_LIMIT_STATUS = 429


async def compute_endpoint_window_metrics(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    endpoint_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> WindowMetrics:
    """Aggregate DeliveryAttempt rows for one endpoint in [window_start, window_end).
    Uses attempt.started_at (not job.queued_at) since that's what actually happened
    inside the window, matching how anomaly baselines need to line up."""

    metrics = WindowMetrics(
        organization_id=organization_id, endpoint_id=endpoint_id, window_start=window_start, window_end=window_end
    )

    attempts_query = (
        select(
            DeliveryAttempt.http_status,
            DeliveryAttempt.error_category,
            DeliveryAttempt.attempt_number,
            DeliveryAttempt.duration_ms,
        )
        .select_from(DeliveryAttempt)
        .join(DeliveryJob, DeliveryJob.id == DeliveryAttempt.delivery_job_id)
        .where(
            DeliveryAttempt.organization_id == organization_id,
            DeliveryJob.endpoint_id == endpoint_id,
            DeliveryAttempt.started_at >= window_start,
            DeliveryAttempt.started_at < window_end,
        )
    )
    rows = (await db.execute(attempts_query)).all()

    durations: list[int] = []
    status_breakdown: dict[str, int] = {}

    for http_status, error_category, attempt_number, duration_ms in rows:
        metrics.sample_size += 1
        durations.append(duration_ms)

        if error_category == ErrorCategory.NONE.value:
            metrics.success_count += 1
        else:
            metrics.failure_count += 1

        if error_category == ErrorCategory.TIMEOUT.value:
            metrics.timeout_count += 1
        elif error_category == ErrorCategory.CONNECTION_ERROR.value:
            metrics.connection_error_count += 1

        if http_status is not None:
            status_breakdown[str(http_status)] = status_breakdown.get(str(http_status), 0) + 1
            if 400 <= http_status < 500:
                metrics.http_4xx_count += 1
                if http_status in _AUTH_STATUSES:
                    metrics.auth_failure_count += 1
                if http_status == _RATE_LIMIT_STATUS:
                    metrics.rate_limited_count += 1
            elif 500 <= http_status < 600:
                metrics.http_5xx_count += 1

        if attempt_number > 1:
            metrics.retry_count += 1

    metrics.status_breakdown = status_breakdown

    if durations:
        percentiles = compute_percentiles(durations, [50, 95])
        metrics.latency_p50_ms = percentiles[50]
        metrics.latency_p95_ms = percentiles[95]

    # DLQ: distinct jobs for this endpoint that transitioned to dead_letter with
    # completed_at inside the window. Counted separately from attempts because a
    # job can accumulate several failed attempts before finally dead-lettering --
    # DLQ rate should reflect jobs, not attempts.
    dlq_query = select(func.count(func.distinct(DeliveryJob.id))).where(
        DeliveryJob.organization_id == organization_id,
        DeliveryJob.endpoint_id == endpoint_id,
        DeliveryJob.status == DeliveryJobStatus.DEAD_LETTER.value,
        DeliveryJob.completed_at >= window_start,
        DeliveryJob.completed_at < window_end,
    )
    metrics.dlq_count = (await db.execute(dlq_query)).scalar_one() or 0

    # Worker health as a supporting signal (section 3: "worker/queue health where
    # relevant"). Not endpoint-specific -- shared across all endpoints in the window.
    heartbeat_query = select(WorkerHeartbeat.last_heartbeat_at)
    heartbeat_rows = (await db.execute(heartbeat_query)).all()
    metrics.workers_total = len(heartbeat_rows)
    if heartbeat_rows:
        # A worker is "healthy" for this snapshot if it heartbeat at any point up to
        # window_end -- staleness thresholds are Phase 2's reconciliation concern
        # (reconcile_stuck_jobs), this is just a coarse corroborating signal for RCA.
        metrics.workers_healthy = sum(1 for (hb,) in heartbeat_rows if hb <= window_end)

    return metrics
