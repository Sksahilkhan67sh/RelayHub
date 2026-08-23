import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.modules.insights.ai.provider import AIProviderTimeoutError, FakeAIProvider
from tests.conftest import create_endpoint, register_and_get_token

pytestmark = pytest.mark.asyncio

WINDOW_MIN = settings.INSIGHTS_HEALTH_WINDOW_MINUTES
MIN_SAMPLES = settings.INSIGHTS_MIN_SAMPLE_SIZE


async def _seed_event_and_attempts(
    db_session, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID, window_end: datetime, count: int, failure_ratio: float,
    http_status_on_failure: int = 503,
):
    """Seeds `count` DeliveryAttempt rows (via a DeliveryJob + Event, matching the
    real schema) ending just before window_end, with the given failure ratio, so
    aggregation.py's real query has real rows to aggregate over."""
    from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus, DeliveryAttempt, ErrorCategory
    from app.modules.events.models import Event

    event = Event(
        organization_id=organization_id, event_type="order.created", environment="test",
        payload={}, request_id=str(uuid.uuid4()),
    )
    db_session.add(event)
    await db_session.flush()

    job = DeliveryJob(
        organization_id=organization_id, event_id=event.id, endpoint_id=endpoint_id,
        status=DeliveryJobStatus.SUCCESS.value, attempt_number=count, queued_at=window_end - timedelta(minutes=WINDOW_MIN),
    )
    db_session.add(job)
    await db_session.flush()

    failures = int(count * failure_ratio)
    for i in range(count):
        started_at = window_end - timedelta(seconds=(count - i) * 2)
        is_failure = i < failures
        db_session.add(
            DeliveryAttempt(
                delivery_job_id=job.id,
                organization_id=organization_id,
                attempt_number=1,
                queued_at=started_at,
                started_at=started_at,
                completed_at=started_at,
                duration_ms=150,
                http_status=http_status_on_failure if is_failure else 200,
                error_category=(ErrorCategory.TRANSIENT_HTTP_ERROR.value if is_failure else ErrorCategory.NONE.value),
                worker_id="test-worker",
            )
        )
    await db_session.commit()


async def _setup_org_and_endpoint(client, email: str):
    token = await register_and_get_token(client, email)
    endpoint_id = await create_endpoint(client, token)
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(resp.json()["organization"]["id"])
    return org_id, uuid.UUID(endpoint_id)


def _window_end(now: datetime) -> datetime:
    from app.workers.insight_tasks import _truncate_to_window

    return _truncate_to_window(now, WINDOW_MIN)


# ---------------------------------------------------------------------------
# Idempotency (section 13, 17.duplicate-analysis-jobs)
# ---------------------------------------------------------------------------


async def test_analyze_endpoint_is_idempotent_for_same_window(client, db_session):
    from app.modules.insights.models import EndpointHealthSnapshot
    from app.workers.insight_tasks import analyze_endpoint
    from sqlalchemy import select

    org_id, endpoint_id = await _setup_org_and_endpoint(client, "idempotency@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=MIN_SAMPLES, failure_ratio=0.0
    )

    result_1 = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=now)
    result_2 = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=now + timedelta(seconds=5))

    assert result_1 == "analyzed"
    assert result_2 == "skipped_duplicate"

    snapshots = (await db_session.execute(select(EndpointHealthSnapshot).where(EndpointHealthSnapshot.endpoint_id == endpoint_id))).scalars().all()
    assert len(snapshots) == 1
    # Regression check for a real bug caught during review: the snapshot's rate/
    # sample_size columns must reflect the real aggregated data, not silently
    # persist as their column defaults (0/None).
    assert snapshots[0].sample_size == MIN_SAMPLES
    assert snapshots[0].failure_rate == 0.0
    assert snapshots[0].success_rate == 1.0


async def test_analyze_endpoint_reports_insufficient_data_below_min_sample(client, db_session):
    from app.workers.insight_tasks import analyze_endpoint

    org_id, endpoint_id = await _setup_org_and_endpoint(client, "insufficient@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    await _seed_event_and_attempts(db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=3, failure_ratio=1.0)

    result = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=now)
    assert result == "insufficient_data"


# ---------------------------------------------------------------------------
# Full pipeline: healthy baseline -> failure spike -> incident -> deterministic RCA
# ---------------------------------------------------------------------------


async def test_full_pipeline_detects_incident_and_generates_deterministic_rca(client, db_session):
    from app.workers.insight_tasks import analyze_endpoint

    org_id, endpoint_id = await _setup_org_and_endpoint(client, "pipeline@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    baseline_window_end = window_end - timedelta(minutes=WINDOW_MIN)

    # Baseline windows: healthy (low failure rate), spread across the lookback period.
    for i in range(1, settings.INSIGHTS_BASELINE_LOOKBACK_WINDOWS + 1):
        await _seed_event_and_attempts(
            db_session, organization_id=org_id, endpoint_id=endpoint_id,
            window_end=baseline_window_end - timedelta(minutes=WINDOW_MIN * (i - 1)),
            count=MIN_SAMPLES * 2, failure_ratio=0.02,
        )
    # Current window: sharp 503 spike.
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=MIN_SAMPLES * 2, failure_ratio=0.9,
    )

    result = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=now)
    assert result == "analyzed"

    from app.modules.insights import query_service

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id)
    assert len(incidents) == 1
    assert incidents[0].status == "open"
    assert incidents[0].failure_category == "destination_5xx"

    rca_entries = await query_service.list_rca_for_incident(db_session, organization_id=org_id, incident_id=incidents[0].id)
    assert len(rca_entries) == 1
    assert rca_entries[0].source == "deterministic"


# ---------------------------------------------------------------------------
# Section 17's most important test: AI provider unavailable must not affect
# the deterministic pipeline or (by extension) delivery.
# ---------------------------------------------------------------------------


async def test_pipeline_completes_fully_when_ai_provider_unavailable(client, db_session, monkeypatch):
    from app.workers.insight_tasks import analyze_endpoint

    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", True)
    org_id, endpoint_id = await _setup_org_and_endpoint(client, "ai-down@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    baseline_window_end = window_end - timedelta(minutes=WINDOW_MIN)

    for i in range(1, settings.INSIGHTS_BASELINE_LOOKBACK_WINDOWS + 1):
        await _seed_event_and_attempts(
            db_session, organization_id=org_id, endpoint_id=endpoint_id,
            window_end=baseline_window_end - timedelta(minutes=WINDOW_MIN * (i - 1)),
            count=MIN_SAMPLES * 2, failure_ratio=0.02,
        )
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=MIN_SAMPLES * 2, failure_ratio=0.9,
    )

    failing_provider = FakeAIProvider()
    failing_provider.queue_failure(AIProviderTimeoutError("simulated total AI outage"))

    # Must not raise, even though the AI provider is completely down.
    result = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=failing_provider, now=now)
    assert result == "analyzed"

    from app.modules.insights import query_service

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id)
    assert len(incidents) == 1

    rca_entries = await query_service.list_rca_for_incident(db_session, organization_id=org_id, incident_id=incidents[0].id)
    # Deterministic RCA exists despite the AI outage; no "ai" source entry was created.
    sources = {r.source for r in rca_entries}
    assert sources == {"deterministic"}


async def test_pipeline_adds_ai_rca_alongside_deterministic_when_ai_succeeds(client, db_session, monkeypatch):
    import json

    from app.workers.insight_tasks import analyze_endpoint

    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", True)
    org_id, endpoint_id = await _setup_org_and_endpoint(client, "ai-up@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    baseline_window_end = window_end - timedelta(minutes=WINDOW_MIN)

    for i in range(1, settings.INSIGHTS_BASELINE_LOOKBACK_WINDOWS + 1):
        await _seed_event_and_attempts(
            db_session, organization_id=org_id, endpoint_id=endpoint_id,
            window_end=baseline_window_end - timedelta(minutes=WINDOW_MIN * (i - 1)),
            count=MIN_SAMPLES * 2, failure_ratio=0.02,
        )
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=MIN_SAMPLES * 2, failure_ratio=0.9,
    )

    provider = FakeAIProvider()
    provider.queue_response(json.dumps({
        "summary": "Destination returning 503s consistently.",
        "likely_causes": ["Destination outage"],
        "confidence_level": "highly_likely",
        "confidence_score": 0.87,
        "evidence": [{"label": "5xx rate", "value": "90%"}],
        "severity": "critical",
        "recommendations": ["Check destination service health."],
    }))

    result = await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=provider, now=now)
    assert result == "analyzed"

    from app.modules.insights import query_service

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id)
    rca_entries = await query_service.list_rca_for_incident(db_session, organization_id=org_id, incident_id=incidents[0].id)
    sources = {r.source for r in rca_entries}
    assert sources == {"deterministic", "ai"}


# ---------------------------------------------------------------------------
# Recovery (section 5) -- stability window
# ---------------------------------------------------------------------------


async def test_incident_moves_to_recovering_then_resolved_after_stability_windows(client, db_session):
    from app.workers.insight_tasks import analyze_endpoint
    from app.modules.insights import query_service

    org_id, endpoint_id = await _setup_org_and_endpoint(client, "recovery@example.com")
    now = datetime.now(timezone.utc)
    window_end = _window_end(now)
    baseline_window_end = window_end - timedelta(minutes=WINDOW_MIN)

    for i in range(1, settings.INSIGHTS_BASELINE_LOOKBACK_WINDOWS + 1):
        await _seed_event_and_attempts(
            db_session, organization_id=org_id, endpoint_id=endpoint_id,
            window_end=baseline_window_end - timedelta(minutes=WINDOW_MIN * (i - 1)),
            count=MIN_SAMPLES * 2, failure_ratio=0.02,
        )
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=window_end, count=MIN_SAMPLES * 2, failure_ratio=0.9,
    )
    await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=now)

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id)
    assert incidents[0].status == "open"

    # Next window: back to healthy.
    next_now = now + timedelta(minutes=WINDOW_MIN)
    next_window_end = _window_end(next_now)
    await _seed_event_and_attempts(
        db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=next_window_end, count=MIN_SAMPLES * 2, failure_ratio=0.02,
    )
    await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=next_now)

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id)
    assert incidents[0].status == "recovering"

    # Enough further healthy windows to clear the stability threshold.
    stability_windows_needed = settings.INSIGHTS_INCIDENT_STABILITY_WINDOWS + 1
    final_now = next_now
    for i in range(1, stability_windows_needed + 1):
        final_now = next_now + timedelta(minutes=WINDOW_MIN * i)
        final_window_end = _window_end(final_now)
        await _seed_event_and_attempts(
            db_session, organization_id=org_id, endpoint_id=endpoint_id, window_end=final_window_end, count=MIN_SAMPLES * 2, failure_ratio=0.02,
        )
        await analyze_endpoint(db_session, endpoint_id=endpoint_id, organization_id=org_id, ai_provider=None, now=final_now)

    incidents = await query_service.list_incidents(db_session, organization_id=org_id, endpoint_id=endpoint_id, status_filter="resolved")
    assert len(incidents) == 1
