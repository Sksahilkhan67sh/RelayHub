package dev.relayhub.sdk;

import java.util.List;

public final class DeliveriesResource {
    private final Transport transport;

    DeliveriesResource(Transport transport) { this.transport = transport; }

    /** GET /v1/deliveries/{jobId} */
    public Models.DeliveryJob get(String jobId) { return get(jobId, null); }
    public Models.DeliveryJob get(String jobId, RequestOptions options) {
        return transport.request("GET", "/v1/deliveries/" + jobId, null, Models.DeliveryJob.class, options);
    }

    /** GET /v1/deliveries/by-event/{eventId} -- every delivery job (one per subscribed endpoint) produced by a single event. */
    public List<Models.DeliveryJob> listByEvent(String eventId) { return listByEvent(eventId, null); }
    public List<Models.DeliveryJob> listByEvent(String eventId, RequestOptions options) {
        return transport.requestList("GET", "/v1/deliveries/by-event/" + eventId, null, Models.DeliveryJob.class, options);
    }

    public static final class SearchLogsParams {
        public String endpointId, eventType, environment, requestId, workerId, queuedAfter, queuedBefore;
        public List<String> status;
        public Integer minLatencyMs, maxLatencyMs, limit, offset;
    }

    /**
     * GET /v1/logs -- the searchable delivery log explorer: every attempt,
     * filterable by endpoint, status, event type, environment, request ID,
     * worker, queued-date range, and latency range. This is the read model
     * backing the dashboard's Logs page.
     */
    public List<Models.DeliveryLogEntry> searchLogs(SearchLogsParams params) { return searchLogs(params, null); }
    public List<Models.DeliveryLogEntry> searchLogs(SearchLogsParams params, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) {
            options.headers.forEach(b::header);
            options.query.forEach(b::query);
        }
        if (params != null) {
            if (params.endpointId != null) b.query("endpoint_id", params.endpointId);
            if (params.status != null) for (String s : params.status) b.query("status", s);
            if (params.eventType != null) b.query("event_type", params.eventType);
            if (params.environment != null) b.query("environment", params.environment);
            if (params.requestId != null) b.query("request_id", params.requestId);
            if (params.workerId != null) b.query("worker_id", params.workerId);
            if (params.queuedAfter != null) b.query("queued_after", params.queuedAfter);
            if (params.queuedBefore != null) b.query("queued_before", params.queuedBefore);
            if (params.minLatencyMs != null) b.query("min_latency_ms", String.valueOf(params.minLatencyMs));
            if (params.maxLatencyMs != null) b.query("max_latency_ms", String.valueOf(params.maxLatencyMs));
            if (params.limit != null) b.query("limit", String.valueOf(params.limit));
            if (params.offset != null) b.query("offset", String.valueOf(params.offset));
        }
        return transport.requestList("GET", "/v1/logs", null, Models.DeliveryLogEntry.class, b.build());
    }
}
