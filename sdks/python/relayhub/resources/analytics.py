from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import EndpointHealthOut, EventTypeVolume, SummaryOut, TimeSeriesBucket, TopEndpointOut


class AnalyticsResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def _range_query(self, environment: str | None, start_date: str | None, end_date: str | None) -> dict[str, Any]:
        return {"environment": environment, "start_date": start_date, "end_date": end_date}

    def summary(
        self, *, environment: str | None = None, start_date: str | None = None, end_date: str | None = None, options: RequestOptions | None = None
    ) -> SummaryOut:
        """GET /v1/analytics/summary -- totals and latency percentiles for the range."""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **self._range_query(environment, start_date, end_date)}
        return self._transport.request("GET", "/v1/analytics/summary", None, opts)

    def deliveries_over_time(
        self,
        *,
        environment: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: str | None = None,
        options: RequestOptions | None = None,
    ) -> list[TimeSeriesBucket]:
        """GET /v1/analytics/deliveries-over-time"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **self._range_query(environment, start_date, end_date), "granularity": granularity}
        return self._transport.request("GET", "/v1/analytics/deliveries-over-time", None, opts)

    def events_by_type(
        self, *, environment: str | None = None, start_date: str | None = None, end_date: str | None = None, options: RequestOptions | None = None
    ) -> list[EventTypeVolume]:
        """GET /v1/analytics/events-by-type"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **self._range_query(environment, start_date, end_date)}
        return self._transport.request("GET", "/v1/analytics/events-by-type", None, opts)

    def top_endpoints(
        self, *, environment: str | None = None, start_date: str | None = None, end_date: str | None = None, options: RequestOptions | None = None
    ) -> list[TopEndpointOut]:
        """GET /v1/analytics/top-endpoints"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **self._range_query(environment, start_date, end_date)}
        return self._transport.request("GET", "/v1/analytics/top-endpoints", None, opts)

    def endpoint_health(self, options: RequestOptions | None = None) -> list[EndpointHealthOut]:
        """GET /v1/analytics/endpoint-health"""
        return self._transport.request("GET", "/v1/analytics/endpoint-health", None, options)

    def export(
        self, *, report: str, granularity: str | None = None, environment: str | None = None, start_date: str | None = None, end_date: str | None = None, options: RequestOptions | None = None
    ) -> str:
        """GET /v1/analytics/export -- CSV export; returns the raw text body. `report` is required: "deliveries-over-time" or "top-endpoints"."""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), **self._range_query(environment, start_date, end_date), "report": report, "granularity": granularity}
        return self._transport.request("GET", "/v1/analytics/export", None, opts)
