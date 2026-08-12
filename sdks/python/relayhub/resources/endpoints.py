from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import EndpointOut, EndpointSecretOut


class EndpointsResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        url: str,
        description: str | None = None,
        environment: str | None = None,
        custom_headers: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
        subscribed_event_types: list[str] | None = None,
        ip_allowlist: list[str] | None = None,
        tls_verification_enabled: bool | None = None,
        max_retry_attempts: int | None = None,
        options: RequestOptions | None = None,
    ) -> EndpointOut:
        """POST /v1/endpoints"""
        body: dict[str, Any] = {
            "name": name,
            "url": url,
            "description": description,
            "environment": environment,
            "custom_headers": custom_headers,
            "timeout_seconds": timeout_seconds,
            "subscribed_event_types": subscribed_event_types,
            "ip_allowlist": ip_allowlist,
            "tls_verification_enabled": tls_verification_enabled,
            "max_retry_attempts": max_retry_attempts,
        }
        return self._transport.request("POST", "/v1/endpoints", body, options)

    def list(self, options: RequestOptions | None = None) -> list[EndpointOut]:
        """GET /v1/endpoints"""
        return self._transport.request("GET", "/v1/endpoints", None, options)

    def get(self, endpoint_id: str, options: RequestOptions | None = None) -> EndpointOut:
        """GET /v1/endpoints/{id}"""
        return self._transport.request("GET", f"/v1/endpoints/{endpoint_id}", None, options)

    def update(self, endpoint_id: str, *, options: RequestOptions | None = None, **fields: Any) -> EndpointOut:
        """PATCH /v1/endpoints/{id} -- pass any subset of create()'s fields, plus is_active."""
        return self._transport.request("PATCH", f"/v1/endpoints/{endpoint_id}", fields, options)

    def delete(self, endpoint_id: str, options: RequestOptions | None = None) -> None:
        """DELETE /v1/endpoints/{id} -- 204 No Content on success."""
        return self._transport.request("DELETE", f"/v1/endpoints/{endpoint_id}", None, options)

    def rotate_secret(self, endpoint_id: str, *, grace_period_hours: int | None = None, options: RequestOptions | None = None) -> EndpointSecretOut:
        """POST /v1/endpoints/{id}/rotate-secret -- the new secret is returned once, here. `grace_period_hours` keeps the old secret valid in parallel."""
        return self._transport.request("POST", f"/v1/endpoints/{endpoint_id}/rotate-secret", {"grace_period_hours": grace_period_hours}, options)
