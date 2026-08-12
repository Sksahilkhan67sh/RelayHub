package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class EndpointsResource {
    private final Transport transport;

    EndpointsResource(Transport transport) { this.transport = transport; }

    public static final class CreateEndpointRequest {
        public String name;
        public String url;
        public String description;
        public String environment;
        public Map<String, String> customHeaders;
        public Integer timeoutSeconds;
        public List<String> subscribedEventTypes;
        public List<String> ipAllowlist;
        public Boolean tlsVerificationEnabled;
        public Integer maxRetryAttempts;

        public CreateEndpointRequest(String name, String url) { this.name = name; this.url = url; }
    }

    public static final class UpdateEndpointRequest {
        public String name;
        public String url;
        public String description;
        public Map<String, String> customHeaders;
        public Integer timeoutSeconds;
        public List<String> subscribedEventTypes;
        public List<String> ipAllowlist;
        public Boolean tlsVerificationEnabled;
        public Integer maxRetryAttempts;
        public Boolean isActive;
    }

    /** POST /v1/endpoints */
    public Models.Endpoint create(CreateEndpointRequest req) { return create(req, null); }
    public Models.Endpoint create(CreateEndpointRequest req, RequestOptions options) {
        return transport.request("POST", "/v1/endpoints", req, Models.Endpoint.class, options);
    }

    /** GET /v1/endpoints */
    public List<Models.Endpoint> list() { return list(null); }
    public List<Models.Endpoint> list(RequestOptions options) {
        return transport.requestList("GET", "/v1/endpoints", null, Models.Endpoint.class, options);
    }

    /** GET /v1/endpoints/{id} */
    public Models.Endpoint get(String endpointId) { return get(endpointId, null); }
    public Models.Endpoint get(String endpointId, RequestOptions options) {
        return transport.request("GET", "/v1/endpoints/" + endpointId, null, Models.Endpoint.class, options);
    }

    /** PATCH /v1/endpoints/{id} */
    public Models.Endpoint update(String endpointId, UpdateEndpointRequest req) { return update(endpointId, req, null); }
    public Models.Endpoint update(String endpointId, UpdateEndpointRequest req, RequestOptions options) {
        return transport.request("PATCH", "/v1/endpoints/" + endpointId, req, Models.Endpoint.class, options);
    }

    /** DELETE /v1/endpoints/{id} -- 204 No Content on success. */
    public void delete(String endpointId) { delete(endpointId, null); }
    public void delete(String endpointId, RequestOptions options) {
        transport.request("DELETE", "/v1/endpoints/" + endpointId, null, Void.class, options);
    }

    /** POST /v1/endpoints/{id}/rotate-secret -- the new secret is returned once, here. gracePeriodHours keeps the old secret valid in parallel. */
    public Models.EndpointSecret rotateSecret(String endpointId, Integer gracePeriodHours) { return rotateSecret(endpointId, gracePeriodHours, null); }
    public Models.EndpointSecret rotateSecret(String endpointId, Integer gracePeriodHours, RequestOptions options) {
        return transport.request("POST", "/v1/endpoints/" + endpointId + "/rotate-secret", Map.of("grace_period_hours", gracePeriodHours == null ? 0 : gracePeriodHours), Models.EndpointSecret.class, options);
    }
}
