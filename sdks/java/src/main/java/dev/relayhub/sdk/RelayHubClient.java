package dev.relayhub.sdk;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.DeserializationFeature;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Official RelayHub API client. Every method on every resource maps 1:1 to a
 * real REST endpoint documented in {@code docs/api} -- the SDK adds no business
 * logic of its own.
 *
 * <pre>{@code
 * RelayHubClient client = new RelayHubClient("rh_live_...");
 * Models.Endpoint endpoint = client.getEndpoints().create(
 *     new EndpointsResource.CreateEndpointRequest("Prod", "https://example.com/hook"));
 * }</pre>
 *
 * Or with the builder:
 * <pre>{@code
 * RelayHubClient client = RelayHubClient.builder()
 *     .apiKey(System.getenv("RELAYHUB_API_KEY"))
 *     .timeout(Duration.ofSeconds(10))
 *     .maxRetries(3)
 *     .header("X-Client-Name", "checkout-service")
 *     .build();
 * }</pre>
 */
public final class RelayHubClient {
    private static final String DEFAULT_BASE_URL = "https://api.relayhub.dev/v1";
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);
    private static final int DEFAULT_MAX_RETRIES = 2;

    private final AuthResource auth;
    private final ApiKeysResource apiKeys;
    private final OrganizationsResource organizations;
    private final EndpointsResource endpoints;
    private final EventsResource events;
    private final DeliveriesResource deliveries;
    private final DlqResource dlq;
    private final AnalyticsResource analytics;
    private final BillingResource billing;
    private final NotificationsResource notifications;
    private final AuditResource audit;

    public RelayHubClient(String apiKey) {
        this(apiKey, DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_MAX_RETRIES, Map.of(), HttpClient.newHttpClient());
    }

    RelayHubClient(String apiKey, String baseUrl, Duration timeout, int maxRetries, Map<String, String> defaultHeaders, HttpClient httpClient) {
        if (apiKey == null || apiKey.isEmpty()) throw new IllegalArgumentException("RelayHubClient requires an apiKey");

        String normalizedBase = baseUrl.replaceAll("/v1/?$", "").replaceAll("/$", "");

        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        Transport transport = new Transport(normalizedBase, apiKey, timeout, maxRetries, defaultHeaders, httpClient, mapper);

        this.auth = new AuthResource(transport);
        this.apiKeys = new ApiKeysResource(transport);
        this.organizations = new OrganizationsResource(transport);
        this.endpoints = new EndpointsResource(transport);
        this.events = new EventsResource(transport);
        this.deliveries = new DeliveriesResource(transport);
        this.dlq = new DlqResource(transport);
        this.analytics = new AnalyticsResource(transport);
        this.billing = new BillingResource(transport);
        this.notifications = new NotificationsResource(transport);
        this.audit = new AuditResource(transport);
    }

    public AuthResource getAuth() { return auth; }
    public ApiKeysResource getApiKeys() { return apiKeys; }
    public OrganizationsResource getOrganizations() { return organizations; }
    public EndpointsResource getEndpoints() { return endpoints; }
    public EventsResource getEvents() { return events; }
    public DeliveriesResource getDeliveries() { return deliveries; }
    public DlqResource getDlq() { return dlq; }
    public AnalyticsResource getAnalytics() { return analytics; }
    public BillingResource getBilling() { return billing; }
    public NotificationsResource getNotifications() { return notifications; }
    public AuditResource getAudit() { return audit; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String apiKey;
        private String baseUrl = DEFAULT_BASE_URL;
        private Duration timeout = DEFAULT_TIMEOUT;
        private int maxRetries = DEFAULT_MAX_RETRIES;
        private final Map<String, String> headers = new LinkedHashMap<>();
        private HttpClient httpClient;

        public Builder apiKey(String apiKey) { this.apiKey = apiKey; return this; }
        public Builder baseUrl(String baseUrl) { this.baseUrl = baseUrl; return this; }
        public Builder timeout(Duration timeout) { this.timeout = timeout; return this; }
        public Builder maxRetries(int maxRetries) { this.maxRetries = maxRetries; return this; }
        public Builder header(String key, String value) { this.headers.put(key, value); return this; }
        public Builder httpClient(HttpClient httpClient) { this.httpClient = httpClient; return this; }

        public RelayHubClient build() {
            if (apiKey == null || apiKey.isEmpty()) {
                throw new IllegalStateException("RelayHubClient.Builder: apiKey(...) is required before build()");
            }
            HttpClient client = httpClient != null ? httpClient : HttpClient.newHttpClient();
            return new RelayHubClient(apiKey, baseUrl, timeout, maxRetries, headers, client);
        }
    }
}
