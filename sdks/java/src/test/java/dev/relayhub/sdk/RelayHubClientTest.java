package dev.relayhub.sdk;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BiConsumer;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Uses the JDK's built-in {@link HttpServer} (com.sun.net.httpserver, bundled
 * with every JDK) as a real local HTTP server instead of a mocking framework --
 * keeps the test suite dependency-free beyond JUnit itself.
 */
class RelayHubClientTest {
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
    void getReturnsDecodedResponse() throws IOException {
        RelayHubClient client = clientFor((exchange, count) -> {
            try { respond(exchange, 200, "{\"id\":\"ep_123\",\"name\":\"Test\"}"); } catch (IOException e) { throw new RuntimeException(e); }
        });
        Models.Endpoint endpoint = client.getEndpoints().get("ep_123");
        assertEquals("Test", endpoint.name);
    }

    @Test
    void notFoundMapsToNotFoundException() throws IOException {
        RelayHubClient client = clientFor((exchange, count) -> {
            try { respond(exchange, 404, "{\"error\":{\"message\":\"Endpoint not found\",\"code\":\"not_found\"}}"); } catch (IOException e) { throw new RuntimeException(e); }
        });
        RelayHubException.NotFoundException ex = assertThrows(RelayHubException.NotFoundException.class, () -> client.getEndpoints().get("missing"));
        assertEquals("Endpoint not found", ex.getMessage());
        assertEquals(404, ex.getStatus());
    }

    @Test
    void validationErrorMapsCorrectly() throws IOException {
        RelayHubClient client = clientFor((exchange, count) -> {
            try { respond(exchange, 422, "{\"error\":{\"message\":\"Invalid event type\"}}"); } catch (IOException e) { throw new RuntimeException(e); }
        });
        assertThrows(RelayHubException.ValidationException.class,
                () -> client.getEvents().publish(new EventsResource.PublishEventRequest("bad")));
    }

    @Test
    void rateLimitIsRetriedThenThrows() throws IOException {
        AtomicInteger calls = new AtomicInteger(0);
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/", exchange -> {
            calls.incrementAndGet();
            try {
                exchange.getResponseHeaders().add("Retry-After", "0");
                respond(exchange, 429, "{\"error\":{\"message\":\"Too many requests\"}}");
            } catch (IOException e) { throw new RuntimeException(e); }
        });
        server.start();
        RelayHubClient client = RelayHubClient.builder()
                .apiKey("test_key")
                .baseUrl("http://localhost:" + server.getAddress().getPort())
                .maxRetries(2)
                .build();

        assertThrows(RelayHubException.RateLimitException.class, () -> client.getEndpoints().list());
        assertEquals(3, calls.get()); // initial attempt + 2 retries
    }

    @Test
    void noContentReturnsNull() throws IOException {
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/", exchange -> {
            try { exchange.sendResponseHeaders(204, -1); exchange.close(); } catch (IOException e) { throw new RuntimeException(e); }
        });
        server.start();
        RelayHubClient client = RelayHubClient.builder()
                .apiKey("test_key").baseUrl("http://localhost:" + server.getAddress().getPort()).maxRetries(0).build();
        assertDoesNotThrow(client.getAuth()::logout);
    }

    @Test
    void builderRequiresApiKey() {
        assertThrows(IllegalStateException.class, () -> RelayHubClient.builder().build());
    }

    @Test
    void emptyListEndpointReturnsEmptyListNotNull() throws IOException {
        RelayHubClient client = clientFor((exchange, count) -> {
            try { respond(exchange, 200, "[]"); } catch (IOException e) { throw new RuntimeException(e); }
        });
        List<Models.Endpoint> result = client.getEndpoints().list();
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }
}
