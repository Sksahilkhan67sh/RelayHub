"""
Phase E additions: health/security-headers behavior added during production
hardening. /health/live stays a pure liveness check (no dependency calls, so it
can't be dragged down by a slow/unavailable Postgres or Redis). /health/ready now
actually calls out to both dependencies instead of being a static stub.
"""


async def test_health_live_is_always_ok(client):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_ready_reports_dependency_status(client):
    resp = await client.get("/health/ready")
    # This environment has no live Redis, so `ready` can't be asserted unconditionally
    # -- what Phase E's change guarantees is that the endpoint actually *checked* both
    # dependencies (rather than always claiming "ready") and reported per-dependency
    # detail, and that a down dependency degrades the endpoint (503) instead of lying.
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert set(body["dependencies"].keys()) == {"database", "redis"}
    for dep in body["dependencies"].values():
        assert "ok" in dep
    if resp.status_code == 503:
        assert body["status"] == "not_ready"
        assert any(not dep["ok"] for dep in body["dependencies"].values())


async def test_responses_carry_baseline_security_headers(client):
    resp = await client.get("/health/live")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in resp.headers
    # HSTS is production-only (see SecurityHeadersMiddleware) -- tests run with
    # ENV=development (the conftest default), so it must be absent here.
    assert "Strict-Transport-Security" not in resp.headers


async def test_oversized_request_body_is_rejected(client):
    from app.middleware.body_size_limit import MAX_BODY_BYTES

    oversized = b"x" * (MAX_BODY_BYTES + 1)
    resp = await client.post(
        "/v1/auth/forgot-password",
        content=oversized,
        headers={"Content-Type": "application/json", "Content-Length": str(len(oversized))},
    )
    assert resp.status_code == 413


async def test_metrics_endpoint_exposes_prometheus_text_format(client):
    """
    Regression test for the metrics-export gap noted throughout Phase 2's report:
    /metrics must exist, be unauthenticated (standard scrape convention), return
    Prometheus text exposition format, and include both HTTP-level metrics (from
    the Instrumentator) and the reliability gauges from app/core/metrics.py.
    """
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    # HTTP-level metric from prometheus-fastapi-instrumentator's middleware
    assert "http_requests_total" in body
    # reliability gauges from app/core/metrics.py
    assert "relayhub_queue_depth" in body
    assert "relayhub_workers_healthy" in body
    assert "relayhub_workers_unhealthy" in body
    assert "relayhub_stuck_jobs_count" in body


async def test_metrics_reflect_real_queue_depth(client, unique_email, db_session):
    """
    Regression test: the queue-depth gauge must reflect a real DeliveryJob row, not
    a static/placeholder value -- proves refresh_reliability_gauges actually queries
    the database on every scrape rather than serving stale or fabricated numbers.
    """
    from tests.conftest import create_api_key, create_endpoint, register_and_get_token

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )

    resp = await client.get("/metrics")
    body = resp.text
    lines = [
        line for line in body.splitlines()
        if line.startswith('relayhub_queue_depth{status="queued"}')
    ]
    assert lines, "expected a relayhub_queue_depth line for status=queued"
    value = float(lines[0].split()[-1])
    assert value >= 1.0
