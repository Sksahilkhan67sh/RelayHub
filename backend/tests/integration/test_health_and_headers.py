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
