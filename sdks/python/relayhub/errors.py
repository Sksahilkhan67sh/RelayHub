"""Typed exceptions raised by the RelayHub SDK for non-2xx API responses."""

from __future__ import annotations

from typing import Any


class RelayHubError(Exception):
    """Base class for every error the SDK raises for a failed API call."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str | None = None,
        request_id: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id
        self.details = details

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{type(self).__name__}(status={self.status}, message={self.message!r})"


class RelayHubAuthenticationError(RelayHubError):
    """401 -- missing, invalid, or expired credentials."""


class RelayHubPermissionError(RelayHubError):
    """403 -- authenticated, but the caller's role/API key scope doesn't allow this."""


class RelayHubNotFoundError(RelayHubError):
    """404."""


class RelayHubConflictError(RelayHubError):
    """409 -- conflicting state (duplicate invitation, already-revoked resource, etc)."""


class RelayHubValidationError(RelayHubError):
    """422 / 400 -- request body or query params failed validation."""


class RelayHubRateLimitError(RelayHubError):
    """429 -- rate limited. `retry_after_seconds` is set when the server sent Retry-After."""

    def __init__(self, *args: Any, retry_after_seconds: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class RelayHubServerError(RelayHubError):
    """5xx from the API."""


class RelayHubConnectionError(RelayHubError):
    """The request never got a response: DNS failure, connection refused, or client-side timeout."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message, status=0)
        self.cause = cause


def error_for_status(
    status: int,
    message: str,
    *,
    code: str | None = None,
    request_id: str | None = None,
    details: Any = None,
    retry_after_seconds: float | None = None,
) -> RelayHubError:
    kwargs: dict[str, Any] = {"status": status, "code": code, "request_id": request_id, "details": details}
    if status == 401:
        return RelayHubAuthenticationError(message, **kwargs)
    if status == 403:
        return RelayHubPermissionError(message, **kwargs)
    if status == 404:
        return RelayHubNotFoundError(message, **kwargs)
    if status == 409:
        return RelayHubConflictError(message, **kwargs)
    if status in (400, 422):
        return RelayHubValidationError(message, **kwargs)
    if status == 429:
        return RelayHubRateLimitError(message, retry_after_seconds=retry_after_seconds, **kwargs)
    if status >= 500:
        return RelayHubServerError(message, **kwargs)
    return RelayHubError(message, **kwargs)
