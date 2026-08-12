from __future__ import annotations

import builtins

from ..http import RequestOptions, Transport
from ..types import BulkRetryResponse, DeadLetterJobOut, RetryDeadLetterResponse


class DlqResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(
        self, *, endpoint_id: str | None = None, limit: int = 50, offset: int = 0, options: RequestOptions | None = None
    ) -> list[DeadLetterJobOut]:
        """GET /v1/dlq -- deliveries that exhausted their retry budget."""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "endpoint_id": endpoint_id, "limit": limit, "offset": offset}
        return self._transport.request("GET", "/v1/dlq", None, opts)

    def get(self, job_id: str, options: RequestOptions | None = None) -> DeadLetterJobOut:
        """GET /v1/dlq/{jobId}"""
        return self._transport.request("GET", f"/v1/dlq/{job_id}", None, options)

    def retry(self, job_id: str, options: RequestOptions | None = None) -> RetryDeadLetterResponse:
        """
        POST /v1/dlq/{jobId}/retry -- replays a single dead-lettered delivery as a
        fresh attempt (same signed payload, doesn't re-trigger the source event).
        This is what "replay" means in the RelayHub API today: it's a DLQ operation,
        not a separate top-level /replay endpoint.
        """
        return self._transport.request("POST", f"/v1/dlq/{job_id}/retry", None, options)

    def bulk_retry(self, job_ids: builtins.list[str], options: RequestOptions | None = None) -> BulkRetryResponse:
        """POST /v1/dlq/bulk-retry -- replays up to 500 dead-lettered deliveries in one call."""
        return self._transport.request("POST", "/v1/dlq/bulk-retry", {"job_ids": job_ids}, options)

    def discard(self, job_id: str, options: RequestOptions | None = None) -> None:
        """DELETE /v1/dlq/{jobId} -- permanently discards a dead-lettered delivery without replaying it. 204 No Content."""
        return self._transport.request("DELETE", f"/v1/dlq/{job_id}", None, options)

    def export(self, *, endpoint_id: str | None = None, options: RequestOptions | None = None) -> str:
        """GET /v1/dlq/export -- CSV export; returns the raw text body."""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "endpoint_id": endpoint_id}
        return self._transport.request("GET", "/v1/dlq/export", None, opts)
