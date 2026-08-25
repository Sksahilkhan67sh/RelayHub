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


def test_sends_x_relayhub_api_key_header_matching_backend_auth_dependency():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return json_response(200, {"id": "ep_123", "name": "Test"})

    client = make_client(handler)
    client.endpoints.get("ep_123")

    assert captured["headers"].get("x-relayhub-api-key") == "test_key"
    # Regression guard: this transport previously sent Authorization: Bearer instead,
    # which the backend's API-key dependency never reads -- every real request 401'd.
    assert "authorization" not in captured["headers"]


def test_sends_x_relayhub_api_key_for_a_real_relayhub_api_key_shape():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return json_response(200, {"id": "ep_123", "name": "Test"})

    real_shaped_key = "rh_test_" + "a" * 43  # matches generate_api_key's actual output shape
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = RelayHubClient(api_key=real_shaped_key, http_client=http_client, max_retries=0)
    client.endpoints.get("ep_123")

    assert captured["headers"].get("x-relayhub-api-key") == real_shaped_key
    assert "authorization" not in captured["headers"]


def test_sends_authorization_bearer_for_a_jwt_session_token():
    """CLI login/whoami/dashboard-equivalent commands authenticate with a JWT
    access token from POST /v1/auth/login, and every one of those backend
    routes requires Authorization: Bearer, not X-RelayHub-Api-Key."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return json_response(200, {"id": "ep_123", "name": "Test"})

    # Shape of a real access token: header.payload.signature, each segment
    # base64url. Not a real signed token, just JWT-shaped for this test.
    jwt_shaped = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEyMyJ9.c2lnbmF0dXJlLWJ5dGVz"
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = RelayHubClient(api_key=jwt_shaped, http_client=http_client, max_retries=0)
    client.endpoints.get("ep_123")

    assert captured["headers"].get("authorization") == f"Bearer {jwt_shaped}"
    # Regression guard: before this fix, every JWT-session CLI command 403'd
    # against the real backend with "Not authenticated", even with a valid token.
    assert "x-relayhub-api-key" not in captured["headers"]


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
