from __future__ import annotations

from ..http import RequestOptions, Transport
from ..types import ApiKeyCreatedResponse, ApiKeyOut


class ApiKeysResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        environment: str | None = None,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
        options: RequestOptions | None = None,
    ) -> ApiKeyCreatedResponse:
        """POST /v1/api-keys -- the full `key` is only ever present on this response. Store it now; it can't be retrieved again."""
        body = {"name": name, "environment": environment, "scopes": scopes, "expires_in_days": expires_in_days}
        return self._transport.request("POST", "/v1/api-keys", body, options)

    def list(self, options: RequestOptions | None = None) -> list[ApiKeyOut]:
        """GET /v1/api-keys"""
        return self._transport.request("GET", "/v1/api-keys", None, options)

    def revoke(self, key_id: str, *, reason: str | None = None, options: RequestOptions | None = None) -> ApiKeyOut:
        """POST /v1/api-keys/{id}/revoke"""
        return self._transport.request("POST", f"/v1/api-keys/{key_id}/revoke", {"reason": reason}, options)

    def rotate(self, key_id: str, options: RequestOptions | None = None) -> ApiKeyCreatedResponse:
        """POST /v1/api-keys/{id}/rotate -- revokes the old key and issues a new one; `key` is shown once, same as create()."""
        return self._transport.request("POST", f"/v1/api-keys/{key_id}/rotate", None, options)
