"""
Metrics export: closes the "no metrics/tracing export" gap noted throughout the
Phase 2 reliability work (see PHASE_2_REPORT.md's Observability section and
Remaining Risks item 4). Until this file, `prometheus-fastapi-instrumentator`,
`opentelemetry-sdk`, and `opentelemetry-instrumentation-fastapi` were all present in
requirements.txt but completely unwired -- dead dependencies from an earlier phase,
with only an unused `OTEL_EXPORTER_OTLP_ENDPOINT` config placeholder. This wires the
Prometheus half of that (OTel tracing remains out of scope -- see the module
docstring note at the bottom).

Design: two kinds of metrics, both exposed on the same `/metrics` endpoint and the
same default `prometheus_client` registry, deliberately for different reasons.

1. HTTP-level metrics (request count, latency, in-progress) come from
   `prometheus_fastapi_instrumentator`'s middleware, which accumulates them
   in-process as the FastAPI app serves real traffic -- true Prometheus Counters/
   Histograms, correct because the API process being scraped is the same process
   that's handling the requests being measured.

2. Reliability metrics (queue depth, worker health, delivery latency/retry-rate/
   DLQ-rate, stuck-job count) are Gauges refreshed from a live DB query
   immediately before every scrape (`refresh_reliability_gauges`, called from the
   `/metrics` route in main.py), NOT accumulated as in-process counters. This is a
   deliberate choice, not an oversight: reconciliation and delivery execution run in
   Celery worker processes, not in the FastAPI process that serves `/metrics`. A
   plain in-memory `Counter` incremented inside `reconcile_stuck_jobs` or the
   executor would only be visible to a scrape of that specific worker process, not
   the API -- and Celery worker processes don't serve HTTP at all, so nothing
   would ever scrape them without introducing a separate exporter/push-gateway,
   which is out of scope for this pass (avoid unnecessary new infrastructure,
   consistent with the rest of this phase). Re-deriving these as gauges from the
   database on every scrape sidesteps the cross-process problem entirely: whichever
   process serves the scrape, the numbers reflect real, current, durable state --
   the same approach `admin/service.py`'s `get_queue_depth`/`get_worker_health`/
   `get_delivery_metrics` already use for their JSON equivalents. This module adds
   no new querying logic; it reuses those functions and copies their output onto
   Gauges.
"""

from __future__ import annotations

from prometheus_client import Gauge
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import service as admin_service
from app.modules.delivery.models import DeliveryJobStatus

# --- Queue depth by status (mirrors admin/service.py's get_queue_depth) ---
QUEUE_DEPTH = Gauge(
    "relayhub_queue_depth",
    "Number of delivery jobs currently in each status",
    labelnames=["status"],
)
DELIVERIES_LAST_HOUR = Gauge(
    "relayhub_deliveries_last_hour",
    "Delivery jobs that reached a terminal outcome in the last hour",
    labelnames=["outcome"],  # success | failed
)

# --- Worker fleet health (mirrors get_worker_health) ---
WORKER_HEALTHY_COUNT = Gauge("relayhub_workers_healthy", "Worker processes with a recent heartbeat")
WORKER_UNHEALTHY_COUNT = Gauge("relayhub_workers_unhealthy", "Worker processes whose heartbeat has gone stale")

# --- Delivery reliability metrics (mirrors get_delivery_metrics) ---
DELIVERY_LATENCY_AVG_MS = Gauge(
    "relayhub_delivery_latency_avg_ms", "Average successful-delivery latency over the metrics window"
)
DELIVERY_LATENCY_P95_MS = Gauge(
    "relayhub_delivery_latency_p95_ms", "P95 successful-delivery latency over the metrics window"
)
RETRY_RATE = Gauge("relayhub_retry_rate", "Fraction of completed deliveries in the window that required a retry")
DLQ_RATE = Gauge("relayhub_dlq_rate", "Fraction of completed deliveries in the window that were dead-lettered")
STUCK_JOBS_COUNT = Gauge(
    "relayhub_stuck_jobs_count",
    "Jobs currently in `processing` past the stuck-job threshold, per admin/service.py's "
    "METRICS_STUCK_PROCESSING_AFTER (the same threshold reconcile_stuck_jobs' time-heuristic "
    "fallback uses) -- a nonzero, non-transient value here is worth alerting on",
)

# --- Phase 3 AI intelligence layer (section 16) ---
# Same DB-refreshed-gauge pattern as everything above, for the same reason: the
# insight_tasks.py Celery task that generates these runs in a worker process, not
# the API process that serves /metrics, so an in-process Counter incremented there
# would only ever be visible to a scrape of that one worker. Re-deriving from the
# database (durable, already-persisted anomaly/incident/RCA rows) sidesteps that.
INSIGHTS_ANOMALIES_LAST_HOUR = Gauge("relayhub_insights_anomalies_last_hour", "Anomalies detected in the last hour")
INSIGHTS_INCIDENTS_OPEN = Gauge(
    "relayhub_insights_incidents_open", "Incidents currently in a non-terminal state", labelnames=["status"]
)
INSIGHTS_RCA_GENERATED_LAST_HOUR = Gauge(
    "relayhub_insights_rca_generated_last_hour", "Root cause analyses generated in the last hour", labelnames=["source"]
)
# AI-specific call metrics (analysis count/failures/latency/token usage) are
# in-process Counters/Histogram in app/modules/insights/ai/service.py instead of
# DB-refreshed gauges, because a failed AI call is deliberately NOT persisted to
# the database (nothing to show the user for a failed call) -- there is no durable
# row to re-derive a failure count from. This means, same as any in-process metric
# in a multi-worker-process deployment, per-process values rather than a
# cluster-wide total unless scraped per-worker or pushed through a gateway -- an
# accepted, documented tradeoff for this pass (see that module for the counters
# themselves), not an oversight.


_QUEUE_DEPTH_STATUSES = (
    DeliveryJobStatus.QUEUED.value,
    DeliveryJobStatus.PROCESSING.value,
    DeliveryJobStatus.RETRYING.value,
    DeliveryJobStatus.DEAD_LETTER.value,
)


async def refresh_reliability_gauges(db: AsyncSession) -> None:
    """
    Called once per `/metrics` scrape (see the route in main.py), immediately
    before rendering. Cheap: this is the same handful of indexed COUNT/aggregate
    queries `get_queue_depth`/`get_worker_health`/`get_delivery_metrics` already run
    for the equivalent JSON admin endpoints -- no new query patterns, no N+1s.
    """
    queue_depth = await admin_service.get_queue_depth(db)
    for status_value in _QUEUE_DEPTH_STATUSES:
        QUEUE_DEPTH.labels(status=status_value).set(queue_depth[status_value])
    DELIVERIES_LAST_HOUR.labels(outcome="success").set(queue_depth["success_last_hour"])
    DELIVERIES_LAST_HOUR.labels(outcome="failed").set(queue_depth["failed_last_hour"])

    worker_health = await admin_service.get_worker_health(db)
    WORKER_HEALTHY_COUNT.set(worker_health["healthy_count"])
    WORKER_UNHEALTHY_COUNT.set(worker_health["unhealthy_count"])

    delivery_metrics = await admin_service.get_delivery_metrics(db)
    # avg/p95 latency and the two rates are all `None` when there's no data yet in
    # the window (see get_delivery_metrics) -- Prometheus gauges can't represent
    # "no data" natively, so leave the gauge at its last-known value rather than
    # writing a misleading 0 (0% retry rate and "no data yet" are different facts).
    if delivery_metrics["avg_delivery_latency_ms"] is not None:
        DELIVERY_LATENCY_AVG_MS.set(delivery_metrics["avg_delivery_latency_ms"])
    if delivery_metrics["p95_delivery_latency_ms"] is not None:
        DELIVERY_LATENCY_P95_MS.set(delivery_metrics["p95_delivery_latency_ms"])
    if delivery_metrics["retry_rate"] is not None:
        RETRY_RATE.set(delivery_metrics["retry_rate"])
    if delivery_metrics["dlq_rate"] is not None:
        DLQ_RATE.set(delivery_metrics["dlq_rate"])
    STUCK_JOBS_COUNT.set(delivery_metrics["stuck_jobs_count"])

    await _refresh_insights_gauges(db)


async def _refresh_insights_gauges(db: AsyncSession) -> None:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from app.modules.insights.models import Anomaly, Incident, IncidentStatus, RootCauseAnalysis

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    anomaly_count = (
        await db.execute(select(func.count()).select_from(Anomaly).where(Anomaly.observed_at >= one_hour_ago))
    ).scalar_one()
    INSIGHTS_ANOMALIES_LAST_HOUR.set(anomaly_count or 0)

    for status_value in (IncidentStatus.OPEN.value, IncidentStatus.INVESTIGATING.value, IncidentStatus.RECOVERING.value):
        count = (
            await db.execute(select(func.count()).select_from(Incident).where(Incident.status == status_value))
        ).scalar_one()
        INSIGHTS_INCIDENTS_OPEN.labels(status=status_value).set(count or 0)

    for source_value in ("deterministic", "ai"):
        count = (
            await db.execute(
                select(func.count())
                .select_from(RootCauseAnalysis)
                .where(RootCauseAnalysis.source == source_value, RootCauseAnalysis.created_at >= one_hour_ago)
            )
        ).scalar_one()
        INSIGHTS_RCA_GENERATED_LAST_HOUR.labels(source=source_value).set(count or 0)
