package dev.relayhub.sdk;

import java.util.List;

public final class ApiKeysResource {
    private final Transport transport;

    ApiKeysResource(Transport transport) { this.transport = transport; }

    public static final class CreateApiKeyRequest {
        public String name;
        public String environment;
        public List<String> scopes;
        public Integer expiresInDays;

        public CreateApiKeyRequest(String name) { this.name = name; }
    }

    /** POST /v1/api-keys -- the full key is only ever present on this response. Store it now; it can't be retrieved again. */
    public Models.ApiKeyCreated create(CreateApiKeyRequest req) { return create(req, null); }
    public Models.ApiKeyCreated create(CreateApiKeyRequest req, RequestOptions options) {
        return transport.request("POST", "/v1/api-keys", req, Models.ApiKeyCreated.class, options);
    }

    /** GET /v1/api-keys */
    public List<Models.ApiKey> list() { return list(null); }
    public List<Models.ApiKey> list(RequestOptions options) {
        return transport.requestList("GET", "/v1/api-keys", null, Models.ApiKey.class, options);
    }

    /** POST /v1/api-keys/{id}/revoke */
    public Models.ApiKey revoke(String keyId, String reason) { return revoke(keyId, reason, null); }
    public Models.ApiKey revoke(String keyId, String reason, RequestOptions options) {
        return transport.request("POST", "/v1/api-keys/" + keyId + "/revoke", java.util.Map.of("reason", reason == null ? "" : reason), Models.ApiKey.class, options);
    }

    /** POST /v1/api-keys/{id}/rotate -- revokes the old key and issues a new one; key is shown once, same as create(). */
    public Models.ApiKeyCreated rotate(String keyId) { return rotate(keyId, null); }
    public Models.ApiKeyCreated rotate(String keyId, RequestOptions options) {
        return transport.request("POST", "/v1/api-keys/" + keyId + "/rotate", null, Models.ApiKeyCreated.class, options);
    }
}
