package dev.relayhub.sdk;

import java.util.List;

public final class AuditResource {
    private final Transport transport;

    AuditResource(Transport transport) { this.transport = transport; }

    /** GET /v1/audit-logs */
    public List<Models.AuditLog> list(Integer limit, Integer offset) { return list(limit, offset, null); }
    public List<Models.AuditLog> list(Integer limit, Integer offset, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (limit != null) b.query("limit", String.valueOf(limit));
        if (offset != null) b.query("offset", String.valueOf(offset));
        return transport.requestList("GET", "/v1/audit-logs", null, Models.AuditLog.class, b.build());
    }
}
