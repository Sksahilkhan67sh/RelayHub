package dev.relayhub.sdk;

import com.sun.net.httpserver.HttpExchange;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BiConsumer;

import com.sun.net.httpserver.HttpServer;

import static org.junit.jupiter.api.Assertions.*;

/**
 * NOTE (Phase 5A): this file was written to match RelayHubClientTest's
 * conventions but could not be compiled or run in the sandbox used to build
 * this change -- Maven Central (repo.maven.apache.org) is not reachable from
 * that environment, so `mvn test` fails before it can even fetch Jackson.
 * Please run `mvn test` in a normal dev environment with Central access
 * before merging.
 */
class InsightsResourceTest {
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) server.stop(0);
    }

    private RelayHubClient clientFor(BiConsumer<HttpExchange, AtomicInteger> handler) throws IOException {
        AtomicInteger callCount = new AtomicInteger(0);
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/", exchange -> handler.accept(exchange, callCount));
        server.start();
        return RelayHubClient.builder()
                .apiKey("test_key")
                .baseUrl("http://localhost:" + server.getAddress().getPort())
                .maxRetries(0)
                .build();
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    @Test
    void healthHitsIntelligencePathNotBareInsights() throws IOException {
        AtomicReference<String> capturedPath = new AtomicReference<>();
        AtomicReference<String> capturedQuery = new AtomicReference<>();
        RelayHubClient client = clientFor((exchange, count) -> {
            capturedPath.set(exchange.getRequestURI().getPath());
            capturedQuery.set(exchange.getRequestURI().getQuery());
            try { respond(exchange, 200, "[]"); } catch (IOException e) { throw new RuntimeException(e); }
        });

        List<Models.EndpointHealthSnapshot> result = client.getInsights().health("ep_1");

        // Regression guard: /v1/insights/... (bare) is already owned by the
        // analytics alias -- this resource must hit /v1/insights/intelligence/...
        // or it would silently collide with analytics summary/export routes.
        assertEquals("/v1/insights/intelligence/health", capturedPath.get());
        assertEquals("endpoint_id=ep_1", capturedQuery.get());
        assertTrue(result.isEmpty());
    }

    @Test
    void healthHistoryBuildsPathWithEndpointId() throws IOException {
        AtomicReference<String> capturedPath = new AtomicReference<>();
        RelayHubClient client = clientFor((exchange, count) -> {
            capturedPath.set(exchange.getRequestURI().getPath());
            try { respond(exchange, 200, "[]"); } catch (IOException e) { throw new RuntimeException(e); }
        });

        client.getInsights().healthHistory("ep_42", 10, 5);

        assertEquals("/v1/insights/intelligence/health/ep_42/history", capturedPath.get());
    }

    @Test
    void getIncidentHitsDetailPath() throws IOException {
        AtomicReference<String> capturedPath = new AtomicReference<>();
        RelayHubClient client = clientFor((exchange, count) -> {
            capturedPath.set(exchange.getRequestURI().getPath());
            try {
                respond(exchange, 200, "{\"id\":\"inc_1\",\"status\":\"resolved\",\"anomalies\":[],\"rca_entries\":[]}");
            } catch (IOException e) { throw new RuntimeException(e); }
        });

        Models.IncidentDetail incident = client.getInsights().getIncident("inc_1");

        assertEquals("/v1/insights/intelligence/incidents/inc_1", capturedPath.get());
        assertEquals("inc_1", incident.id);
    }

    @Test
    void incidentRcaKeepsDeterministicAndAiSourcesDistinguishable() throws IOException {
        RelayHubClient client = clientFor((exchange, count) -> {
            try {
                respond(exchange, 200,
                        "[{\"id\":\"rca_1\",\"source\":\"deterministic\"},{\"id\":\"rca_2\",\"source\":\"ai\"}]");
            } catch (IOException e) { throw new RuntimeException(e); }
        });

        List<Models.RootCauseAnalysis> entries = client.getInsights().incidentRca("inc_1");

        assertEquals(2, entries.size());
        assertEquals("deterministic", entries.get(0).source);
        assertEquals("ai", entries.get(1).source);
    }

    @Test
    void incidentRecommendationsPathAndShape() throws IOException {
        AtomicReference<String> capturedPath = new AtomicReference<>();
        RelayHubClient client = clientFor((exchange, count) -> {
            capturedPath.set(exchange.getRequestURI().getPath());
            try {
                respond(exchange, 200, "{\"incident_id\":\"inc_1\",\"recommendations\":[\"Increase timeout\"]}");
            } catch (IOException e) { throw new RuntimeException(e); }
        });

        Models.Recommendations recs = client.getInsights().incidentRecommendations("inc_1");

        assertEquals("/v1/insights/intelligence/incidents/inc_1/recommendations", capturedPath.get());
        assertEquals(1, recs.recommendations.size());
        assertEquals("Increase timeout", recs.recommendations.get(0));
    }

    @Test
    void incidentTimelinePathAndShape() throws IOException {
        AtomicReference<String> capturedPath = new AtomicReference<>();
        RelayHubClient client = clientFor((exchange, count) -> {
            capturedPath.set(exchange.getRequestURI().getPath());
            try {
                respond(exchange, 200,
                        "{\"incident_id\":\"inc_1\",\"status\":\"open\",\"events\":[{\"type\":\"anomaly_detected\",\"at\":\"2026-01-01T00:00:00Z\",\"detail\":\"d\"}]}");
            } catch (IOException e) { throw new RuntimeException(e); }
        });

        Models.IncidentTimeline timeline = client.getInsights().incidentTimeline("inc_1");

        assertEquals("/v1/insights/intelligence/incidents/inc_1/timeline", capturedPath.get());
        assertEquals(1, timeline.events.size());
        assertEquals("anomaly_detected", timeline.events.get(0).type);
    }
}
