"""Internal HTTP transport shared by every resource client.

Not part of the public API -- resource classes (``client.endpoints``,
``client.events``, ...) are. Handles auth headers, timeouts, exponential-backoff
retries on 429/5xx and connection errors, and mapping non-2xx responses to typed
``RelayHubError`` subclasses.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .errors import RelayHubConnectionError, RelayHubError, error_for_status

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class RequestOptions:
    query: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    timeout: float | None = None
    max_retries: int | None = None
    idempotency_key: str | None = None


@dataclass
class TransportConfig:
    base_url: str
    api_key: str
    timeout: float = 30.0
    max_retries: int = 2
    default_headers: dict[str, str] = field(default_factory=dict)
    http_client: httpx.Client | None = None


class Transport:
    def __init__(self, config: TransportConfig) -> None:
        self._config = config
        self._client = config.http_client or httpx.Client()

    def request(self, method: str, path: str, body: dict[str, Any] | None = None, options: RequestOptions | None = None) -> Any:
        options = options or RequestOptions()
        url = f"{self._config.base_url}{path}"
        max_retries = options.max_retries if options.max_retries is not None else self._config.max_retries
        timeout = options.timeout if options.timeout is not None else self._config.timeout

        request_body = dict(body) if body is not None else None
        if options.idempotency_key and request_body is not None:
            request_body["idempotency_key"] = options.idempotency_key

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "relayhub-python/1.0.0",
            **self._config.default_headers,
            **(options.headers or {}),
        }
        params = {k: v for k, v in (options.query or {}).items() if v is not None}

        attempt = 0
        while True:
            try:
                response = self._client.request(method, url, json=request_body, headers=headers, params=params, timeout=timeout)
            except httpx.TimeoutException as exc:
                if attempt < max_retries:
                    attempt += 1
                    time.sleep(_backoff_seconds(attempt))
                    continue
                raise RelayHubConnectionError(f"Request to {path} timed out after {timeout}s", cause=exc) from exc
            except httpx.RequestError as exc:
                if attempt < max_retries:
                    attempt += 1
                    time.sleep(_backoff_seconds(attempt))
                    continue
                raise RelayHubConnectionError(f"Request to {path} failed: {exc}", cause=exc) from exc

            if response.status_code == 204:
                return None

            content_type = response.headers.get("content-type", "")
            data: Any = response.json() if "application/json" in content_type else response.text

            if response.is_success:
                return data

            retry_after_header = response.headers.get("retry-after")
            retry_after_seconds = float(retry_after_header) if retry_after_header else None

            if response.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                attempt += 1
                time.sleep(retry_after_seconds if retry_after_seconds is not None else _backoff_seconds(attempt))
                continue

            raise _error_from_response(response.status_code, data, retry_after_seconds)

    def close(self) -> None:
        self._client.close()


def _backoff_seconds(attempt: int) -> float:
    base = min(1.0 * (2 ** (attempt - 1)), 8.0)
    return base + random.uniform(0, 0.25)


def _error_from_response(status: int, data: Any, retry_after_seconds: float | None) -> RelayHubError:
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        err = data["error"]
        return error_for_status(
            status,
            err.get("message", "Request failed"),
            code=err.get("code"),
            request_id=err.get("request_id"),
            details=data,
            retry_after_seconds=retry_after_seconds,
        )
    if isinstance(data, str) and data:
        return error_for_status(status, data, retry_after_seconds=retry_after_seconds)
    return error_for_status(status, f"Request failed with status {status}", details=data, retry_after_seconds=retry_after_seconds)
