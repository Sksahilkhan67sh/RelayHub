from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import DeliveryJobOut, DeliveryLogEntryOut


class DeliveriesResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def get(self, job_id: str, options: RequestOptions | None = None) -> DeliveryJobOut:
        """GET /v1/deliveries/{jobId}"""
        return self._transport.request("GET", f"/v1/deliveries/{job_id}", None, options)

    def list_by_event(self, event_id: str, options: RequestOptions | None = None) -> list[DeliveryJobOut]:
        """GET /v1/deliveries/by-event/{eventId} -- every delivery job (one per subscribed endpoint) produced by a single event."""
        return self._transport.request("GET", f"/v1/deliveries/by-event/{event_id}", None, options)

    def search_logs(
        self,
        *,
        endpoint_id: str | None = None,
        status: list[str] | None = None,
        event_type: str | None = None,
        environment: str | None = None,
        request_id: str | None = None,
        worker_id: str | None = None,
        queued_after: str | None = None,
        queued_before: str | None = None,
        min_latency_ms: int | None = None,
        max_latency_ms: int | None = None,
        limit: int = 50,
        offset: int = 0,
        options: RequestOptions | None = None,
    ) -> list[DeliveryLogEntryOut]:
        """
        GET /v1/logs -- the searchable delivery log explorer: every attempt, filterable
        by endpoint, status, event type, environment, request ID, worker, queued-date
        range, and latency range. This is the read model backing the dashboard's Logs page.
        """
        query: dict[str, Any] = {
            "endpoint_id": endpoint_id,
            "status": status,
            "event_type": event_type,
            "environment": environment,
            "request_id": request_id,
            "worker_id": worker_id,
            "queued_after": queued_after,
            "queued_before": queued_before,
            "min_latency_ms": min_latency_ms,
            "max_latency_ms": max_latency_ms,
            "limit": limit,
            "offset": offset,
        }
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **query}
        return self._transport.request("GET", "/v1/logs", None, opts)
