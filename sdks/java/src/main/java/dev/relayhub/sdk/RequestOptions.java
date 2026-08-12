package dev.relayhub.sdk;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Per-call overrides, built fluently:
 *
 * <pre>{@code
 * client.getEndpoints().list(RequestOptions.builder().timeout(Duration.ofSeconds(2)).maxRetries(0).build());
 * }</pre>
 */
public final class RequestOptions {
    final Map<String, String> query;
    final Map<String, String> headers;
    final Duration timeout;
    final Integer maxRetries;
    final String idempotencyKey;

    private RequestOptions(Builder b) {
        this.query = b.query;
        this.headers = b.headers;
        this.timeout = b.timeout;
        this.maxRetries = b.maxRetries;
        this.idempotencyKey = b.idempotencyKey;
    }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private final Map<String, String> query = new LinkedHashMap<>();
        private final Map<String, String> headers = new LinkedHashMap<>();
        private Duration timeout;
        private Integer maxRetries;
        private String idempotencyKey;

        public Builder query(String key, String value) { this.query.put(key, value); return this; }
        public Builder header(String key, String value) { this.headers.put(key, value); return this; }
        public Builder timeout(Duration timeout) { this.timeout = timeout; return this; }
        public Builder maxRetries(int maxRetries) { this.maxRetries = maxRetries; return this; }

        /** Sets the {@code idempotency_key} field RelayHub's publish-event endpoint accepts in its body (see docs/api/events.md). */
        public Builder idempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; return this; }

        public RequestOptions build() { return new RequestOptions(this); }
    }
}
