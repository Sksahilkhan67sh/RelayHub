package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class DlqResource {
    private final Transport transport;

    DlqResource(Transport transport) { this.transport = transport; }

    /** GET /v1/dlq -- deliveries that exhausted their retry budget. */
    public List<Models.DeadLetterJob> list(String endpointId, Integer limit, Integer offset) { return list(endpointId, limit, offset, null); }
    public List<Models.DeadLetterJob> list(String endpointId, Integer limit, Integer offset, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (endpointId != null) b.query("endpoint_id", endpointId);
        if (limit != null) b.query("limit", String.valueOf(limit));
        if (offset != null) b.query("offset", String.valueOf(offset));
        return transport.requestList("GET", "/v1/dlq", null, Models.DeadLetterJob.class, b.build());
    }

    /** GET /v1/dlq/{jobId} */
    public Models.DeadLetterJob get(String jobId) { return get(jobId, null); }
    public Models.DeadLetterJob get(String jobId, RequestOptions options) {
        return transport.request("GET", "/v1/dlq/" + jobId, null, Models.DeadLetterJob.class, options);
    }

    /**
     * POST /v1/dlq/{jobId}/retry -- replays a single dead-lettered delivery as a
     * fresh attempt (same signed payload, doesn't re-trigger the source event).
     * This is what "replay" means in the RelayHub API today: it's a DLQ
     * operation, not a separate top-level /replay endpoint.
     */
    public Models.RetryDeadLetterResponse retry(String jobId) { return retry(jobId, null); }
    public Models.RetryDeadLetterResponse retry(String jobId, RequestOptions options) {
        return transport.request("POST", "/v1/dlq/" + jobId + "/retry", null, Models.RetryDeadLetterResponse.class, options);
    }

    /** POST /v1/dlq/bulk-retry -- replays up to 500 dead-lettered deliveries in one call. */
    public Models.BulkRetryResponse bulkRetry(List<String> jobIds) { return bulkRetry(jobIds, null); }
    public Models.BulkRetryResponse bulkRetry(List<String> jobIds, RequestOptions options) {
        return transport.request("POST", "/v1/dlq/bulk-retry", Map.of("job_ids", jobIds), Models.BulkRetryResponse.class, options);
    }

    /** DELETE /v1/dlq/{jobId} -- permanently discards a dead-lettered delivery without replaying it. 204 No Content on success. */
    public void discard(String jobId) { discard(jobId, null); }
    public void discard(String jobId, RequestOptions options) {
        transport.request("DELETE", "/v1/dlq/" + jobId, null, Void.class, options);
    }

    /** GET /v1/dlq/export -- CSV export; returns the raw text body. */
    public String export(String endpointId) { return export(endpointId, null); }
    public String export(String endpointId, RequestOptions options) {
        Map<String, String> query = endpointId != null ? Map.of("endpoint_id", endpointId) : Map.of();
        return transport.requestText("GET", "/v1/dlq/export", query, options);
    }
}
