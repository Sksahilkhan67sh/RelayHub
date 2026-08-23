"""
Phase 3 -- background processing (section 13). Wires together every layer built in
steps 1-4 on a schedule: aggregation -> health -> anomaly -> incident -> RCA
(always deterministic) -> RCA (AI, only if enabled and eligible) -> recovery
evaluation. Runs on the dedicated "insights" Celery queue (see celery_app.py's
task_routes) so it can never compete with deliver_webhook for worker capacity.

Same async-bridge pattern as app/workers/tasks.py: a fresh engine per task
invocation (asyncpg connections are bound to the event loop that created them).

Idempotency (section 13 / 17.duplicate-analysis-jobs): each run is keyed by
(endpoint_id, window_end) where window_end is truncated to an
INSIGHTS_HEALTH_WINDOW_MINUTES boundary. If a snapshot for that exact window
already exists, the task is a no-op -- so a Celery retry, a beat misfire, or an
operator manually re-triggering the periodic task can never produce duplicate
snapshots/anomalies for the same window.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.tracing import get_tracer
from app.modules.endpoints.models import Endpoint
from app.modules.insights.aggregation import WindowMetrics, compute_endpoint_window_metrics
from app.modules.insights.ai.provider import AIProvider, get_ai_provider
from app.modules.insights.ai.service import AIAnalysisOutcome, ai_result_to_rca_fields, analyze_incident
from app.modules.insights.anomaly_detection import detect_anomalies
from app.modules.insights.health_analysis import compute_health
from app.modules.insights.incident_engine import correlate_anomalies, evaluate_incident_recovery
from app.modules.insights.models import EndpointHealthSnapshot, Incident, RootCauseAnalysis
from app.modules.insights.rca import build_rca
from app.workers.celery_app import celery_app

logger = logging.getLogger("relayhub.insights.tasks")


def _truncate_to_window(now: datetime, window_minutes: int) -> datetime:
    """Rounds down to the nearest window boundary so repeated runs within the same
    window compute the same window_end -- the basis for the idempotency check."""
    epoch_minutes = int(now.timestamp() // 60)
    truncated_minutes = (epoch_minutes // window_minutes) * window_minutes
    return datetime.fromtimestamp(truncated_minutes * 60, tz=timezone.utc)


async def _get_existing_snapshot(db: AsyncSession, *, endpoint_id: uuid.UUID, window_end: datetime) -> EndpointHealthSnapshot | None:
    query = select(EndpointHealthSnapshot).where(
        EndpointHealthSnapshot.endpoint_id == endpoint_id, EndpointHealthSnapshot.window_end == window_end
    )
    return (await db.execute(query)).scalars().first()


async def _upsert_rca(db: AsyncSession, *, incident: Incident, organization_id: uuid.UUID, source: str, fields: dict) -> None:
    """One RCA row per (incident, source) -- updated in place on subsequent runs
    rather than accumulating a new row every window. Keeps the table from growing
    unboundedly for a long-lived incident while still keeping history at the
    incident level (RCA reflects current understanding; the incident's own
    opened_at/anomalies give the historical trail -- see the timeline endpoint)."""
    query = select(RootCauseAnalysis).where(RootCauseAnalysis.incident_id == incident.id, RootCauseAnalysis.source == source)
    existing = (await db.execute(query)).scalars().first()
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        db.add(RootCauseAnalysis(organization_id=organization_id, incident_id=incident.id, source=source, **fields))


async def analyze_endpoint(
    db: AsyncSession, *, endpoint_id: uuid.UUID, organization_id: uuid.UUID, ai_provider: AIProvider | None, now: datetime | None = None
) -> str:
    """Runs one full pipeline pass for one endpoint. Returns a short status string
    for logging ("skipped_duplicate", "insufficient_data", "analyzed"). Exposed as
    a plain async function (not just the Celery task) so it's directly unit- and
    integration-testable without going through Celery's task-calling machinery."""

    now = now or datetime.now(timezone.utc)
    window_minutes = settings.INSIGHTS_HEALTH_WINDOW_MINUTES
    window_end = _truncate_to_window(now, window_minutes)
    window_start = window_end - timedelta(minutes=window_minutes)

    if await _get_existing_snapshot(db, endpoint_id=endpoint_id, window_end=window_end) is not None:
        return "skipped_duplicate"

    current = await compute_endpoint_window_metrics(
        db, organization_id=organization_id, endpoint_id=endpoint_id, window_start=window_start, window_end=window_end
    )
    health = compute_health(current)

    # NOTE: compute_health() intentionally returns only status/health_score/
    # confidence/supporting_signals (see health_analysis.py -- it's a pure
    # scoring function, unit-tested against exactly those keys). The snapshot row
    # has additional rate/sample-size columns that must come from `current`
    # (WindowMetrics) directly -- spreading **health alone would silently persist
    # every rate as its column default (0/None) regardless of the real data.
    snapshot = EndpointHealthSnapshot(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        window_start=window_start,
        window_end=window_end,
        sample_size=current.sample_size,
        success_rate=current.success_rate,
        failure_rate=current.failure_rate,
        http_4xx_rate=current.http_4xx_rate,
        http_5xx_rate=current.http_5xx_rate,
        timeout_rate=current.timeout_rate,
        retry_rate=current.retry_rate,
        dlq_rate=current.dlq_rate,
        latency_p50_ms=current.latency_p50_ms,
        latency_p95_ms=current.latency_p95_ms,
        **health,
    )
    db.add(snapshot)

    if not current.has_sufficient_data():
        await _evaluate_recovery_for_endpoint(db, endpoint_id=endpoint_id, metrics=current, health_status=health["status"], observed_at=now)
        await db.commit()
        return "insufficient_data"

    baseline_start = window_start - timedelta(minutes=window_minutes * settings.INSIGHTS_BASELINE_LOOKBACK_WINDOWS)
    baseline = await compute_endpoint_window_metrics(
        db, organization_id=organization_id, endpoint_id=endpoint_id, window_start=baseline_start, window_end=window_start
    )

    anomaly_dicts = detect_anomalies(
        endpoint_id=endpoint_id, organization_id=organization_id, current=current, baseline=baseline, observed_at=now
    )
    incident, _anomaly_rows = await correlate_anomalies(
        db, organization_id=organization_id, endpoint_id=endpoint_id, anomaly_dicts=anomaly_dicts, metrics=current, observed_at=now
    )

    if incident is not None:
        deterministic = build_rca(metrics=current, min_sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE)
        await _upsert_rca(db, incident=incident, organization_id=organization_id, source="deterministic", fields={k: v for k, v in deterministic.items() if k != "source"})

        if ai_provider is not None:
            outcome: AIAnalysisOutcome = await analyze_incident(
                ai_provider,
                incident=incident,
                metrics=current,
                deterministic_likely_cause=deterministic["likely_cause"],
                deterministic_evidence=deterministic["evidence"],
            )
            if outcome.succeeded:
                await _upsert_rca(db, incident=incident, organization_id=organization_id, source="ai", fields={k: v for k, v in ai_result_to_rca_fields(outcome).items() if k != "source"})

    await _evaluate_recovery_for_endpoint(db, endpoint_id=endpoint_id, metrics=current, health_status=health["status"], observed_at=now)

    await db.commit()
    return "analyzed"


async def _evaluate_recovery_for_endpoint(db: AsyncSession, *, endpoint_id: uuid.UUID, metrics: WindowMetrics, health_status: str, observed_at: datetime) -> None:
    """Runs recovery evaluation for every non-terminal incident on this endpoint,
    independent of whether new anomalies fired this pass -- a quiet, healthy
    window is itself the signal recovery detection needs (section 5)."""
    query = select(Incident).where(
        Incident.endpoint_id == endpoint_id, Incident.status.in_(("open", "investigating", "recovering"))
    )
    incidents = (await db.execute(query)).scalars().all()
    for incident in incidents:
        await evaluate_incident_recovery(
            db, incident=incident, current_window_metrics=metrics, current_health_status=health_status, observed_at=observed_at
        )


async def _run_analyze_endpoint(endpoint_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    ai_provider = None
    if settings.AI_PROVIDER_ENABLED:
        try:
            ai_provider = get_ai_provider()
        except Exception:  # noqa: BLE001 -- a misconfigured AI provider must not block the deterministic pipeline
            logger.exception("failed to construct AI provider, continuing without AI enrichment")

    async with session_maker() as db:
        try:
            result = await analyze_endpoint(db, endpoint_id=endpoint_id, organization_id=organization_id, ai_provider=ai_provider)
            logger.info("insight analysis endpoint=%s result=%s", endpoint_id, result)
        except Exception:
            await db.rollback()
            raise
    await engine.dispose()


async def _run_analyze_all_endpoints() -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_maker() as db:
        query = select(Endpoint.id, Endpoint.organization_id).where(Endpoint.is_active.is_(True), Endpoint.deleted_at.is_(None))
        rows = (await db.execute(query)).all()
    await engine.dispose()

    logger.info("dispatching insight analysis for %d active endpoint(s)", len(rows))
    for endpoint_id, organization_id in rows:
        analyze_endpoint_health.delay(str(endpoint_id), str(organization_id))


@celery_app.task(name="analyze_endpoint_health", bind=True, max_retries=3, default_retry_delay=30)
def analyze_endpoint_health(self, endpoint_id: str, organization_id: str) -> None:
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("analyze_endpoint_health") as span:
        span.set_attribute("relayhub.endpoint_id", endpoint_id)
        try:
            asyncio.run(_run_analyze_endpoint(uuid.UUID(endpoint_id), uuid.UUID(organization_id)))
        except Exception as exc:
            # Retryable: a transient DB hiccup or AI provider blip shouldn't
            # silently drop this window's analysis. Deliberately NOT
            # infinite -- max_retries=3 -- an insights job that can never
            # succeed must not retry forever and pile up on the insights queue.
            raise self.retry(exc=exc)


@celery_app.task(name="analyze_all_endpoints")
def analyze_all_endpoints() -> None:
    asyncio.run(_run_analyze_all_endpoints())
