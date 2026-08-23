import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import create_endpoint, register_and_get_token

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


async def _seed_incident(db_session, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID):
    from app.modules.insights.models import Anomaly, EndpointHealthSnapshot, Incident, RootCauseAnalysis

    snapshot = EndpointHealthSnapshot(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        status="critical",
        health_score=12.5,
        confidence=0.9,
        sample_size=200,
        success_rate=0.1,
        failure_rate=0.9,
        http_5xx_rate=0.85,
        supporting_signals={"status_breakdown": {"503": 170}},
    )
    db_session.add(snapshot)

    incident = Incident(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        status="open",
        failure_category="destination_5xx",
        severity="critical",
        title="Destination 5xx spike",
        summary="90% failure rate observed",
        opened_at=NOW - timedelta(minutes=30),
        last_signal_at=NOW,
    )
    db_session.add(incident)
    await db_session.flush()

    anomaly = Anomaly(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        metric="failure_rate",
        direction="spike",
        observed_value=0.9,
        baseline_value=0.05,
        delta=0.85,
        observed_at=NOW - timedelta(minutes=25),
        confidence=0.9,
        sample_size=200,
        evidence=[{"label": "current failure rate", "value": "90.0%"}],
        incident_id=incident.id,
    )
    db_session.add(anomaly)

    rca = RootCauseAnalysis(
        organization_id=organization_id,
        incident_id=incident.id,
        source="deterministic",
        likely_cause="Destination service is returning server errors (5xx).",
        confidence_level="highly_likely",
        confidence_score=0.85,
        evidence=[{"label": "5xx rate", "value": "85%"}],
        recommendations=["Check the destination service's health and recent deployments."],
    )
    db_session.add(rca)

    await db_session.commit()
    return incident.id


async def test_insights_endpoints_require_auth(client):
    # Matches the codebase's established convention for "no credentials at all"
    # (see test_analytics.py::test_analytics_requires_auth) -- FastAPI's
    # HTTPBearer dependency returns 403 for a missing Authorization header and
    # reserves 401 for a present-but-invalid/expired token, so a request with no
    # header at all can legitimately come back as either depending on the auth
    # dependency's exact implementation.
    resp = await client.get("/v1/insights/intelligence/health")
    assert resp.status_code in (401, 403)


async def test_health_endpoint_returns_seeded_snapshot(client, db_session):
    token = await register_and_get_token(client, "insights-health@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    resp = await client.get("/v1/insights/intelligence/health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "critical"
    assert body[0]["health_score"] == 12.5


async def test_incidents_list_and_detail(client, db_session):
    token = await register_and_get_token(client, "insights-incidents@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    incident_id = await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    list_resp = await client.get("/v1/insights/intelligence/incidents", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == str(incident_id)

    detail_resp = await client.get(f"/v1/insights/intelligence/incidents/{incident_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "open"
    assert len(detail["anomalies"]) == 1
    assert len(detail["rca_entries"]) == 1
    assert detail["rca_entries"][0]["source"] == "deterministic"  # FACT vs AI INFERENCE distinguishable


async def test_incident_rca_and_recommendations(client, db_session):
    token = await register_and_get_token(client, "insights-rca@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    incident_id = await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    rca_resp = await client.get(f"/v1/insights/intelligence/incidents/{incident_id}/rca", headers={"Authorization": f"Bearer {token}"})
    assert rca_resp.status_code == 200
    assert rca_resp.json()[0]["confidence_level"] == "highly_likely"

    recs_resp = await client.get(
        f"/v1/insights/intelligence/incidents/{incident_id}/recommendations", headers={"Authorization": f"Bearer {token}"}
    )
    assert recs_resp.status_code == 200
    assert "destination service" in recs_resp.json()["recommendations"][0].lower()


async def test_incident_timeline_ordered(client, db_session):
    token = await register_and_get_token(client, "insights-timeline@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    incident_id = await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    resp = await client.get(f"/v1/insights/intelligence/incidents/{incident_id}/timeline", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert events[0]["type"] == "incident_opened"
    assert any(e["type"] == "anomaly" for e in events)
    # chronological order
    timestamps = [e["at"] for e in events]
    assert timestamps == sorted(timestamps)


async def test_anomalies_filterable_by_endpoint(client, db_session):
    token = await register_and_get_token(client, "insights-anomalies@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    resp = await client.get(
        "/v1/insights/intelligence/anomalies", params={"endpoint_id": endpoint_id}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["metric"] == "failure_rate"


# ---------------------------------------------------------------------------
# Tenant isolation (section 10, section 18.I) -- the most important test class here
# ---------------------------------------------------------------------------


async def test_cross_tenant_incident_detail_returns_404_not_403(client, db_session):
    """Org A's incident must be invisible to Org B -- and specifically a 404, not a
    403, so Org B can't even infer that the incident ID exists."""
    token_a = await register_and_get_token(client, "tenant-a@example.com")
    endpoint_id_a = await create_endpoint(client, token_a)
    org_a_id = await _org_id(client, token_a)
    incident_id = await _seed_incident(db_session, organization_id=org_a_id, endpoint_id=uuid.UUID(endpoint_id_a))

    token_b = await register_and_get_token(client, "tenant-b@example.com")

    resp = await client.get(f"/v1/insights/intelligence/incidents/{incident_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404

    rca_resp = await client.get(f"/v1/insights/intelligence/incidents/{incident_id}/rca", headers={"Authorization": f"Bearer {token_b}"})
    assert rca_resp.status_code == 404


async def test_cross_tenant_incident_list_does_not_leak(client, db_session):
    token_a = await register_and_get_token(client, "tenant-list-a@example.com")
    endpoint_id_a = await create_endpoint(client, token_a)
    org_a_id = await _org_id(client, token_a)
    await _seed_incident(db_session, organization_id=org_a_id, endpoint_id=uuid.UUID(endpoint_id_a))

    token_b = await register_and_get_token(client, "tenant-list-b@example.com")
    resp = await client.get("/v1/insights/intelligence/incidents", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_cross_tenant_health_does_not_leak(client, db_session):
    token_a = await register_and_get_token(client, "tenant-health-a@example.com")
    endpoint_id_a = await create_endpoint(client, token_a)
    org_a_id = await _org_id(client, token_a)
    await _seed_incident(db_session, organization_id=org_a_id, endpoint_id=uuid.UUID(endpoint_id_a))

    token_b = await register_and_get_token(client, "tenant-health-b@example.com")
    resp = await client.get("/v1/insights/intelligence/health", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _org_id(client, token: str) -> uuid.UUID:
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return uuid.UUID(resp.json()["organization"]["id"])
