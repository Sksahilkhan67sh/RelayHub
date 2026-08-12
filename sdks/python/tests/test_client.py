from __future__ import annotations

import json

import httpx
import pytest

from relayhub import (
    RelayHubClient,
    RelayHubNotFoundError,
    RelayHubRateLimitError,
    RelayHubValidationError,
)


def make_client(handler, **kwargs) -> RelayHubClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return RelayHubClient(api_key="test_key", http_client=http_client, max_retries=kwargs.pop("max_retries", 0), **kwargs)


def json_response(status: int, body, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers or {})


def test_successful_get_returns_parsed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(200, {"id": "ep_123", "name": "Test"})

    client = make_client(handler)
    endpoint = client.endpoints.get("ep_123")
    assert endpoint["name"] == "Test"


def test_404_maps_to_not_found_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(404, {"error": {"message": "Endpoint not found", "code": "not_found"}})

    client = make_client(handler)
    with pytest.raises(RelayHubNotFoundError) as exc_info:
        client.endpoints.get("missing")
    assert exc_info.value.message == "Endpoint not found"
    assert exc_info.value.status == 404


def test_422_maps_to_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(422, {"error": {"message": "Invalid event type"}})

    client = make_client(handler)
    with pytest.raises(RelayHubValidationError):
        client.events.publish(event="bad")


def test_429_is_retried_then_raises_rate_limit_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return json_response(429, {"error": {"message": "Too many requests"}}, headers={"retry-after": "0"})

    client = make_client(handler, max_retries=2)
    with pytest.raises(RelayHubRateLimitError):
        client.endpoints.list()
    assert calls["count"] == 3  # initial attempt + 2 retries


def test_500_then_success_does_not_raise():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return json_response(500, {"error": {"message": "boom"}})
        return json_response(200, [])

    client = make_client(handler, max_retries=2)
    result = client.endpoints.list()
    assert result == []
    assert calls["count"] == 2


def test_204_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = make_client(handler)
    assert client.auth.logout() is None


def test_idempotency_key_option_sets_body_field():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return json_response(
            201,
            {"id": "evt_1", "event": "payment.success", "environment": "test", "payload": {}, "request_id": "req_1", "created_at": "now", "delivery_jobs": []},
        )

    client = make_client(handler)
    from relayhub.http import RequestOptions

    client.events.publish(event="payment.success", options=RequestOptions(idempotency_key="order-42"))
    assert captured["body"]["idempotency_key"] == "order-42"


def test_builder_pattern_produces_a_working_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(200, {"user": {}, "organization": {}, "role": "member"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = RelayHubClient.builder().api_key("test_key").http_client(http_client).max_retries(0).build()
    me = client.auth.me()
    assert me["role"] == "member"


def test_builder_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        RelayHubClient.builder().build()


def test_context_manager_closes_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(200, [])

    with make_client(handler) as client:
        client.endpoints.list()
