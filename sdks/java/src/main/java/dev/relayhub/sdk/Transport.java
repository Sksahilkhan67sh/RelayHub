package dev.relayhub.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import java.util.stream.Collectors;

/**
 * Internal HTTP transport shared by every resource client. Not part of the
 * public API -- resource classes ({@code client.getEndpoints()}, etc.) are.
 * Handles auth headers, timeouts, exponential-backoff retries on 429/5xx and
 * connection errors, and mapping non-2xx responses to typed {@link RelayHubException} subclasses.
 */
final class Transport {
    private static final Set<Integer> RETRYABLE_STATUS = Set.of(429, 500, 502, 503, 504);

    private final String baseUrl;
    private final String apiKey;
    private final Duration timeout;
    private final int maxRetries;
    private final Map<String, String> defaultHeaders;
    private final HttpClient httpClient;
    private final ObjectMapper mapper;

    Transport(String baseUrl, String apiKey, Duration timeout, int maxRetries, Map<String, String> defaultHeaders, HttpClient httpClient, ObjectMapper mapper) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.timeout = timeout;
        this.maxRetries = maxRetries;
        this.defaultHeaders = defaultHeaders;
        this.httpClient = httpClient;
        this.mapper = mapper;
    }

    <T> T request(String method, String path, Object body, Class<T> responseType, RequestOptions options) {
        JsonNode raw = requestRaw(method, path, body, options);
        if (raw == null) return null;
        try {
            return mapper.treeToValue(raw, responseType);
        } catch (IOException e) {
            throw new RelayHubException.ConnectionException("Failed to decode response from " + path, e);
        }
    }

    <T> T request(String method, String path, Object body, com.fasterxml.jackson.databind.JavaType responseType, RequestOptions options) {
        JsonNode raw = requestRaw(method, path, body, options);
        if (raw == null) return null;
        try {
            return mapper.convertValue(raw, responseType);
        } catch (IllegalArgumentException e) {
            throw new RelayHubException.ConnectionException("Failed to decode response from " + path, e);
        }
    }

    <T> java.util.List<T> requestList(String method, String path, Object body, Class<T> elementType, RequestOptions options) {
        com.fasterxml.jackson.databind.JavaType listType = mapper.getTypeFactory().constructCollectionType(java.util.List.class, elementType);
        java.util.List<T> result = request(method, path, body, listType, options);
        return result != null ? result : java.util.List.of();
    }

    String requestText(String method, String path, Map<String, String> query, RequestOptions options) {
        RequestOptions merged = mergeQuery(options, query);
        return requestRawText(method, path, null, merged);
    }

    private JsonNode requestRaw(String method, String path, Object body, RequestOptions options) {
        String text = requestRawText(method, path, body, options);
        if (text == null || text.isEmpty()) return null;
        try {
            return mapper.readTree(text);
        } catch (IOException e) {
            throw new RelayHubException.ConnectionException("Failed to parse response from " + path, e);
        }
    }

    private RequestOptions mergeQuery(RequestOptions options, Map<String, String> query) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) {
            if (options.timeout != null) b.timeout(options.timeout);
            if (options.maxRetries != null) b.maxRetries(options.maxRetries);
            if (options.idempotencyKey != null) b.idempotencyKey(options.idempotencyKey);
            options.headers.forEach(b::header);
            options.query.forEach(b::query);
        }
        if (query != null) query.forEach((k, v) -> { if (v != null) b.query(k, v); });
        return b.build();
    }

    private String requestRawText(String method, String path, Object body, RequestOptions options) {
        String url = baseUrl + path + buildQueryString(options);
        int retries = (options != null && options.maxRetries != null) ? options.maxRetries : maxRetries;
        Duration effectiveTimeout = (options != null && options.timeout != null) ? options.timeout : timeout;

        String requestBody = null;
        if (body != null) {
            Object payload = body;
            if (options != null && options.idempotencyKey != null) {
                payload = mergeIdempotencyKey(body, options.idempotencyKey);
            }
            try {
                requestBody = mapper.writeValueAsString(payload);
            } catch (IOException e) {
                throw new RelayHubException.ConnectionException("Failed to encode request body for " + path, e);
            }
        }

        RelayHubException lastError = null;
        for (int attempt = 0; attempt <= retries; attempt++) {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(url))
                    .timeout(effectiveTimeout)
                    // See the matching comment in the Node SDK's transport.ts -- the backend's
                    // API-key auth dependency (app/modules/api_keys/dependencies.py) reads ONLY
                    // this header. Authorization: Bearer is reserved for dashboard user JWT
                    // sessions, a separate auth path this client never uses.
                    .header("X-RelayHub-Api-Key", apiKey)
                    .header("Content-Type", "application/json")
                    .header("User-Agent", "relayhub-java/1.0.1");
            defaultHeaders.forEach(builder::header);
            if (options != null) options.headers.forEach(builder::header);

            HttpRequest.BodyPublisher publisher = requestBody != null
                    ? HttpRequest.BodyPublishers.ofString(requestBody)
                    : HttpRequest.BodyPublishers.noBody();
            builder.method(method, publisher);

            HttpResponse<String> response;
            try {
                response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            } catch (IOException | InterruptedException e) {
                lastError = new RelayHubException.ConnectionException("Request to " + path + " failed: " + e.getMessage(), e);
                if (attempt < retries) { sleep(backoffMillis(attempt + 1)); continue; }
                throw lastError;
            }

            int status = response.statusCode();
            if (status == 204) return null;

            if (status >= 200 && status < 300) return response.body();

            String retryAfterHeader = response.headers().firstValue("Retry-After").orElse(null);
            Double retryAfterSeconds = null;
            if (retryAfterHeader != null) {
                try { retryAfterSeconds = Double.parseDouble(retryAfterHeader); } catch (NumberFormatException ignored) {}
            }

            if (RETRYABLE_STATUS.contains(status) && attempt < retries) {
                // Retry-After, when the server sends it, REPLACES our own exponential
                // backoff for this wait -- it should never stack with it. Falling back
                // to backoff only when the server didn't tell us how long to wait.
                sleep(retryAfterSeconds != null ? (long) (retryAfterSeconds * 1000) : backoffMillis(attempt + 1));
                continue;
            }

            throw errorFromResponse(status, response.body(), retryAfterSeconds);
        }
        throw lastError != null ? lastError : new RelayHubException.ConnectionException("Request to " + path + " failed with no response", null);
    }

    private Object mergeIdempotencyKey(Object body, String key) {
        Map<String, Object> map = mapper.convertValue(body, new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {});
        Map<String, Object> merged = new HashMap<>(map);
        merged.put("idempotency_key", key);
        return merged;
    }

    private String buildQueryString(RequestOptions options) {
        if (options == null || options.query.isEmpty()) return "";
        return "?" + options.query.entrySet().stream()
                .map(e -> java.net.URLEncoder.encode(e.getKey(), java.nio.charset.StandardCharsets.UTF_8) + "="
                        + java.net.URLEncoder.encode(e.getValue(), java.nio.charset.StandardCharsets.UTF_8))
                .collect(Collectors.joining("&"));
    }

    private RelayHubException errorFromResponse(int status, String body, Double retryAfterSeconds) {
        String message = "Request failed with status " + status;
        String code = null;
        String requestId = null;
        try {
            JsonNode node = mapper.readTree(body);
            if (node.has("error")) {
                JsonNode err = node.get("error");
                if (err.has("message")) message = err.get("message").asText();
                if (err.has("code")) code = err.get("code").asText();
                if (err.has("request_id")) requestId = err.get("request_id").asText();
            }
        } catch (Exception ignored) {
            if (body != null && !body.isBlank()) message = body;
        }
        return RelayHubException.forStatus(status, message, code, requestId, body, retryAfterSeconds);
    }

    private static long backoffMillis(int attempt) {
        long base = Math.min(1000L * (1L << (attempt - 1)), 8000L);
        long jitter = ThreadLocalRandom.current().nextLong(250);
        return base + jitter;
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
