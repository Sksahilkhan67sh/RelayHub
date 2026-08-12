package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class AnalyticsResource {
    private final Transport transport;

    AnalyticsResource(Transport transport) { this.transport = transport; }

    public static final class RangeParams {
        public String environment, startDate, endDate;
    }

    private RequestOptions.Builder withRange(RangeParams params, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (params != null) {
            if (params.environment != null) b.query("environment", params.environment);
            if (params.startDate != null) b.query("start_date", params.startDate);
            if (params.endDate != null) b.query("end_date", params.endDate);
        }
        return b;
    }

    /** GET /v1/analytics/summary -- totals and latency percentiles for the range. */
    public Models.Summary summary(RangeParams params) { return summary(params, null); }
    public Models.Summary summary(RangeParams params, RequestOptions options) {
        return transport.request("GET", "/v1/analytics/summary", null, Models.Summary.class, withRange(params, options).build());
    }

    /** GET /v1/analytics/deliveries-over-time */
    public List<Models.TimeSeriesBucket> deliveriesOverTime(RangeParams params, String granularity) { return deliveriesOverTime(params, granularity, null); }
    public List<Models.TimeSeriesBucket> deliveriesOverTime(RangeParams params, String granularity, RequestOptions options) {
        RequestOptions.Builder b = withRange(params, options);
        if (granularity != null) b.query("granularity", granularity);
        return transport.requestList("GET", "/v1/analytics/deliveries-over-time", null, Models.TimeSeriesBucket.class, b.build());
    }

    /** GET /v1/analytics/events-by-type */
    public List<Models.EventTypeVolume> eventsByType(RangeParams params) { return eventsByType(params, null); }
    public List<Models.EventTypeVolume> eventsByType(RangeParams params, RequestOptions options) {
        return transport.requestList("GET", "/v1/analytics/events-by-type", null, Models.EventTypeVolume.class, withRange(params, options).build());
    }

    /** GET /v1/analytics/top-endpoints */
    public List<Models.TopEndpoint> topEndpoints(RangeParams params) { return topEndpoints(params, null); }
    public List<Models.TopEndpoint> topEndpoints(RangeParams params, RequestOptions options) {
        return transport.requestList("GET", "/v1/analytics/top-endpoints", null, Models.TopEndpoint.class, withRange(params, options).build());
    }

    /** GET /v1/analytics/endpoint-health */
    public List<Models.EndpointHealth> endpointHealth() { return endpointHealth(null); }
    public List<Models.EndpointHealth> endpointHealth(RequestOptions options) {
        return transport.requestList("GET", "/v1/analytics/endpoint-health", null, Models.EndpointHealth.class, options);
    }

    /** GET /v1/analytics/export -- CSV export; returns the raw text body. report is required: "deliveries-over-time" or "top-endpoints". */
    public String export(String report, RangeParams params) { return export(report, params, null); }
    public String export(String report, RangeParams params, RequestOptions options) {
        Map<String, String> query = new java.util.LinkedHashMap<>();
        query.put("report", report);
        if (params != null) {
            if (params.environment != null) query.put("environment", params.environment);
            if (params.startDate != null) query.put("start_date", params.startDate);
            if (params.endDate != null) query.put("end_date", params.endDate);
        }
        return transport.requestText("GET", "/v1/analytics/export", query, options);
    }
}
