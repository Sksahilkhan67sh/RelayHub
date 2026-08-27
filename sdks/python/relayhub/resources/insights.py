from __future__ import annotations

import builtins

from ..http import RequestOptions, Transport
from ..types import (
    EndpointHealthSnapshotOut,
    IncidentDetailOut,
    IncidentOut,
    IncidentTimelineOut,
    InsightAnomalyOut,
    RecommendationsOut,
    RootCauseAnalysisOut,
)


class InsightsResource:
    """
    Phase 3 AI Intelligence layer -- deliberately mounted at
    /v1/insights/intelligence/... rather than bare /v1/insights/... because that
    path is already owned by AnalyticsResource's alias (see
    backend/app/modules/insights/routes.py's module docstring). Analytics is raw
    metrics/reporting; this resource is derived health/anomaly/incident/RCA state
    built on top of it -- keep that distinction visible in anything you build on
    top of these methods (RootCauseAnalysisOut.source is "deterministic" or "ai").
    """

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def health(self, *, endpoint_id: str | None = None, options: RequestOptions | None = None) -> builtins.list[EndpointHealthSnapshotOut]:
        """GET /v1/insights/intelligence/health"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "endpoint_id": endpoint_id}
        return self._transport.request("GET", "/v1/insights/intelligence/health", None, opts)

    def health_history(
        self, endpoint_id: str, *, limit: int = 100, offset: int = 0, options: RequestOptions | None = None
    ) -> builtins.list[EndpointHealthSnapshotOut]:
        """GET /v1/insights/intelligence/health/{endpoint_id}/history"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "limit": limit, "offset": offset}
        return self._transport.request("GET", f"/v1/insights/intelligence/health/{endpoint_id}/history", None, opts)

    def anomalies(
        self,
        *,
        endpoint_id: str | None = None,
        metric: str | None = None,
        since: str | None = None,
        limit: int = 100,
        offset: int = 0,
        options: RequestOptions | None = None,
    ) -> builtins.list[InsightAnomalyOut]:
        """GET /v1/insights/intelligence/anomalies"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "endpoint_id": endpoint_id, "metric": metric, "since": since, "limit": limit, "offset": offset}
        return self._transport.request("GET", "/v1/insights/intelligence/anomalies", None, opts)

    def incidents(
        self,
        *,
        status: str | None = None,
        endpoint_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        options: RequestOptions | None = None,
    ) -> builtins.list[IncidentOut]:
        """GET /v1/insights/intelligence/incidents"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "status": status, "endpoint_id": endpoint_id, "limit": limit, "offset": offset}
        return self._transport.request("GET", "/v1/insights/intelligence/incidents", None, opts)

    def get_incident(self, incident_id: str, options: RequestOptions | None = None) -> IncidentDetailOut:
        """GET /v1/insights/intelligence/incidents/{incident_id}"""
        return self._transport.request("GET", f"/v1/insights/intelligence/incidents/{incident_id}", None, options)

    def incident_rca(self, incident_id: str, options: RequestOptions | None = None) -> builtins.list[RootCauseAnalysisOut]:
        """GET /v1/insights/intelligence/incidents/{incident_id}/rca"""
        return self._transport.request("GET", f"/v1/insights/intelligence/incidents/{incident_id}/rca", None, options)

    def incident_recommendations(self, incident_id: str, options: RequestOptions | None = None) -> RecommendationsOut:
        """GET /v1/insights/intelligence/incidents/{incident_id}/recommendations"""
        return self._transport.request(
            "GET", f"/v1/insights/intelligence/incidents/{incident_id}/recommendations", None, options
        )

    def incident_timeline(self, incident_id: str, options: RequestOptions | None = None) -> IncidentTimelineOut:
        """GET /v1/insights/intelligence/incidents/{incident_id}/timeline"""
        return self._transport.request("GET", f"/v1/insights/intelligence/incidents/{incident_id}/timeline", None, options)
