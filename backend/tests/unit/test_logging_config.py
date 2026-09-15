"""
Phase 3 observability: structured logging + correlation-context regression
coverage.

Covers:
  - a malformed/oversized client-supplied X-Request-ID is replaced with a
    generated one rather than trusted verbatim (log-injection / unbounded-
    length hardening)
  - a well-formed client-supplied X-Request-ID is preserved
  - concurrent requests never see each other's request_id via the
    contextvar-based mechanism (the actual property that makes this safe to
    use from arbitrary logging call sites without threading a Request object
    through every function)
  - an unhandled exception is logged server-side (previously a silent gap --
    see app/core/error_handlers.py) with no traceback leaking into the
    client-facing response body
"""

import asyncio
import logging

import pytest

from app.core.logging_config import JsonFormatter, RequestContextFilter, request_id_var
from app.middleware.request_id import REQUEST_ID_HEADER


@pytest.mark.asyncio
async def test_malformed_request_id_is_replaced_not_trusted(client):
    malformed = "not a valid id\nX-Injected-Header: evil"
    resp = await client.get("/health/live", headers={REQUEST_ID_HEADER: malformed})
    returned = resp.headers[REQUEST_ID_HEADER]
    assert returned != malformed
    # A generated UUID4, not the attacker-controlled string.
    assert len(returned) == 36 and returned.count("-") == 4


@pytest.mark.asyncio
async def test_oversized_request_id_is_replaced(client):
    oversized = "a" * 5000
    resp = await client.get("/health/live", headers={REQUEST_ID_HEADER: oversized})
    assert resp.headers[REQUEST_ID_HEADER] != oversized
    assert len(resp.headers[REQUEST_ID_HEADER]) == 36


@pytest.mark.asyncio
async def test_well_formed_request_id_is_preserved(client):
    supplied = "client-correlation-id-123"
    resp = await client.get("/health/live", headers={REQUEST_ID_HEADER: supplied})
    assert resp.headers[REQUEST_ID_HEADER] == supplied


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_leak_request_id(client):
    """The actual property that makes the contextvar mechanism safe: two
    requests in flight at the same time must never see each other's ID, even
    though both are served by the same process and the same asyncio event
    loop."""
    seen: dict[str, str] = {}

    async def make_request(supplied_id: str):
        resp = await client.get("/health/live", headers={REQUEST_ID_HEADER: supplied_id})
        seen[supplied_id] = resp.headers[REQUEST_ID_HEADER]

    await asyncio.gather(
        make_request("request-a"),
        make_request("request-b"),
        make_request("request-c"),
    )

    assert seen == {"request-a": "request-a", "request-b": "request-b", "request-c": "request-c"}


def test_request_context_filter_attaches_active_request_id():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)
    token = request_id_var.set("abc-123")
    try:
        assert RequestContextFilter().filter(record) is True
        assert record.request_id == "abc-123"
    finally:
        request_id_var.reset(token)


def test_request_context_filter_omits_request_id_when_none_active():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)
    assert request_id_var.get() is None
    RequestContextFilter().filter(record)
    assert not hasattr(record, "request_id")


def test_json_formatter_includes_extra_fields_and_omits_internals():
    record = logging.LogRecord("app.test", logging.INFO, __file__, 42, "delivery finished", (), None)
    record.request_id = "req-1"
    record.delivery_job_id = "job-1"
    import json

    rendered = json.loads(JsonFormatter().format(record))
    assert rendered["message"] == "delivery finished"
    assert rendered["level"] == "INFO"
    assert rendered["logger"] == "app.test"
    assert rendered["request_id"] == "req-1"
    assert rendered["delivery_job_id"] == "job-1"
    # Internal LogRecord bookkeeping (pathname, lineno, etc.) must not leak in.
    assert "pathname" not in rendered
    assert "args" not in rendered


def test_json_formatter_includes_traceback_on_exception():
    import json

    logger = logging.getLogger("test_json_formatter_exc")
    try:
        raise ValueError("boom")
    except ValueError:
        record = logger.makeRecord("test", logging.ERROR, __file__, 1, "failed", (), __import__("sys").exc_info())
    rendered = json.loads(JsonFormatter().format(record))
    assert "boom" in rendered["traceback"]
    assert "ValueError" in rendered["traceback"]


@pytest.mark.asyncio
async def test_unhandled_exception_is_logged_and_response_has_no_traceback(db_session, caplog, monkeypatch):
    """Exercises the real registered exception handler end-to-end, not a
    reimplementation of it. Uses a dedicated client with
    raise_app_exceptions=False -- the shared `client` fixture deliberately
    re-raises unhandled exceptions (so a real test bug fails loudly rather
    than silently becoming a 500), which is correct for every other test but
    is exactly the behavior this one needs to disable to observe what a real
    API caller would actually receive."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _boom():
        raise RuntimeError("deliberate test failure")

    import app.main as main_module

    monkeypatch.setattr(main_module, "check_database", _boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as raising_client:
        with caplog.at_level(logging.ERROR, logger="app.core.error_handlers"):
            resp = await raising_client.get("/health/ready")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"
    assert "RuntimeError" not in resp.text
    assert "deliberate test failure" not in resp.text
    assert "Traceback" not in resp.text

    assert any("unhandled_exception" in r.message for r in caplog.records)
