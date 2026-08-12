from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import MeResponse, TokenResponse


class AuthResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def register(self, *, email: str, password: str, full_name: str, organization_name: str, options: RequestOptions | None = None) -> TokenResponse:
        """POST /v1/auth/register"""
        body = {"email": email, "password": password, "full_name": full_name, "organization_name": organization_name}
        return self._transport.request("POST", "/v1/auth/register", body, options)

    def login(self, *, email: str, password: str, options: RequestOptions | None = None) -> TokenResponse:
        """POST /v1/auth/login"""
        return self._transport.request("POST", "/v1/auth/login", {"email": email, "password": password}, options)

    def refresh(self, *, refresh_token: str, options: RequestOptions | None = None) -> TokenResponse:
        """POST /v1/auth/refresh"""
        return self._transport.request("POST", "/v1/auth/refresh", {"refresh_token": refresh_token}, options)

    def logout(self, options: RequestOptions | None = None) -> None:
        """POST /v1/auth/logout -- 204 No Content on success."""
        return self._transport.request("POST", "/v1/auth/logout", None, options)

    def me(self, options: RequestOptions | None = None) -> MeResponse:
        """GET /v1/auth/me"""
        return self._transport.request("GET", "/v1/auth/me", None, options)

    def forgot_password(self, *, email: str, options: RequestOptions | None = None) -> dict[str, Any]:
        """POST /v1/auth/forgot-password -- always returns the same generic message whether or not the email is registered, by design."""
        return self._transport.request("POST", "/v1/auth/forgot-password", {"email": email}, options)

    def reset_password(self, *, token: str, new_password: str, options: RequestOptions | None = None) -> None:
        """POST /v1/auth/reset-password -- 204 No Content on success."""
        return self._transport.request("POST", "/v1/auth/reset-password", {"token": token, "new_password": new_password}, options)
