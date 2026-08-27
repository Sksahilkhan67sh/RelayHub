package dev.relayhub.sdk;

import java.util.List;

/**
 * Phase 3 AI Intelligence layer -- mounted at /v1/insights/intelligence/...,
 * not bare /v1/insights/..., because that path is already owned by
 * AnalyticsResource's alias (see backend/app/modules/insights/routes.py's
 * module docstring). Analytics is raw metrics/reporting; this resource is
 * derived health/anomaly/incident/RCA state built on top of it -- keep the
 * FACT (deterministic) vs INFERENCE (ai) distinction visible in anything built
 * on top of these methods ({@code Models.RootCauseAnalysis.source}).
 */
public final class InsightsResource {
    private final Transport transport;

    InsightsResource(Transport transport) { this.transport = transport; }

    /** GET /v1/insights/intelligence/health */
    public List<Models.EndpointHealthSnapshot> health(String endpointId) { return health(endpointId, null); }
    public List<Models.EndpointHealthSnapshot> health(String endpointId, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (endpointId != null) b.query("endpoint_id", endpointId);
        return transport.requestList("GET", "/v1/insights/intelligence/health", null, Models.EndpointHealthSnapshot.class, b.build());
    }

    /** GET /v1/insights/intelligence/health/{endpointId}/history */
    public List<Models.EndpointHealthSnapshot> healthHistory(String endpointId, Integer limit, Integer offset) {
        return healthHistory(endpointId, limit, offset, null);
    }
    public List<Models.EndpointHealthSnapshot> healthHistory(String endpointId, Integer limit, Integer offset, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (limit != null) b.query("limit", String.valueOf(limit));
        if (offset != null) b.query("offset", String.valueOf(offset));
        return transport.requestList(
            "GET", "/v1/insights/intelligence/health/" + endpointId + "/history", null, Models.EndpointHealthSnapshot.class, b.build());
    }

    public static final class AnomaliesParams {
        public String endpointId, metric, since;
        public Integer limit, offset;
    }

    /** GET /v1/insights/intelligence/anomalies */
    public List<Models.InsightAnomaly> anomalies(AnomaliesParams params) { return anomalies(params, null); }
    public List<Models.InsightAnomaly> anomalies(AnomaliesParams params, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (params != null) {
            if (params.endpointId != null) b.query("endpoint_id", params.endpointId);
            if (params.metric != null) b.query("metric", params.metric);
            if (params.since != null) b.query("since", params.since);
            if (params.limit != null) b.query("limit", String.valueOf(params.limit));
            if (params.offset != null) b.query("offset", String.valueOf(params.offset));
        }
        return transport.requestList("GET", "/v1/insights/intelligence/anomalies", null, Models.InsightAnomaly.class, b.build());
    }

    public static final class IncidentsParams {
        public String status, endpointId;
        public Integer limit, offset;
    }

    /** GET /v1/insights/intelligence/incidents */
    public List<Models.Incident> incidents(IncidentsParams params) { return incidents(params, null); }
    public List<Models.Incident> incidents(IncidentsParams params, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (params != null) {
            if (params.status != null) b.query("status", params.status);
            if (params.endpointId != null) b.query("endpoint_id", params.endpointId);
            if (params.limit != null) b.query("limit", String.valueOf(params.limit));
            if (params.offset != null) b.query("offset", String.valueOf(params.offset));
        }
        return transport.requestList("GET", "/v1/insights/intelligence/incidents", null, Models.Incident.class, b.build());
    }

    /** GET /v1/insights/intelligence/incidents/{incidentId} */
    public Models.IncidentDetail getIncident(String incidentId) { return getIncident(incidentId, null); }
    public Models.IncidentDetail getIncident(String incidentId, RequestOptions options) {
        return transport.request("GET", "/v1/insights/intelligence/incidents/" + incidentId, null, Models.IncidentDetail.class, options);
    }

    /** GET /v1/insights/intelligence/incidents/{incidentId}/rca */
    public List<Models.RootCauseAnalysis> incidentRca(String incidentId) { return incidentRca(incidentId, null); }
    public List<Models.RootCauseAnalysis> incidentRca(String incidentId, RequestOptions options) {
        return transport.requestList(
            "GET", "/v1/insights/intelligence/incidents/" + incidentId + "/rca", null, Models.RootCauseAnalysis.class, options);
    }

    /** GET /v1/insights/intelligence/incidents/{incidentId}/recommendations */
    public Models.Recommendations incidentRecommendations(String incidentId) { return incidentRecommendations(incidentId, null); }
    public Models.Recommendations incidentRecommendations(String incidentId, RequestOptions options) {
        return transport.request(
            "GET", "/v1/insights/intelligence/incidents/" + incidentId + "/recommendations", null, Models.Recommendations.class, options);
    }

    /** GET /v1/insights/intelligence/incidents/{incidentId}/timeline */
    public Models.IncidentTimeline incidentTimeline(String incidentId) { return incidentTimeline(incidentId, null); }
    public Models.IncidentTimeline incidentTimeline(String incidentId, RequestOptions options) {
        return transport.request(
            "GET", "/v1/insights/intelligence/incidents/" + incidentId + "/timeline", null, Models.IncidentTimeline.class, options);
    }
}
