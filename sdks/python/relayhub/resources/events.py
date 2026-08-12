from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import EventOut


class EventsResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def publish(
        self,
        *,
        event: str,
        payload: dict[str, Any] | None = None,
        environment: str | None = None,
        options: RequestOptions | None = None,
    ) -> EventOut:
        """
        POST /v1/events -- publishes an event, fanning it out to every endpoint
        subscribed to `event` in the given environment. Pass `options.idempotency_key`
        to make republishing the same logical event safe to retry on your side.
        """
        body = {"event": event, "payload": payload, "environment": environment}
        return self._transport.request("POST", "/v1/events", body, options)

    def get(self, event_id: str, options: RequestOptions | None = None) -> EventOut:
        """GET /v1/events/{id}"""
        return self._transport.request("GET", f"/v1/events/{event_id}", None, options)

    def list(self, options: RequestOptions | None = None) -> list[EventOut]:
        """GET /v1/events"""
        return self._transport.request("GET", "/v1/events", None, options)
