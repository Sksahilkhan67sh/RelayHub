package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class EventsResource {
    private final Transport transport;

    EventsResource(Transport transport) { this.transport = transport; }

    public static final class PublishEventRequest {
        public String event;
        public Map<String, Object> payload;
        public String environment;

        public PublishEventRequest(String event) { this.event = event; }
    }

    /**
     * POST /v1/events -- publishes an event, fanning it out to every endpoint
     * subscribed to {@code event} in the given environment. Use
     * {@link RequestOptions.Builder#idempotencyKey(String)} to make republishing
     * the same logical event safe to retry on your side.
     */
    public Models.Event publish(PublishEventRequest req) { return publish(req, null); }
    public Models.Event publish(PublishEventRequest req, RequestOptions options) {
        return transport.request("POST", "/v1/events", req, Models.Event.class, options);
    }

    /** GET /v1/events/{id} */
    public Models.Event get(String eventId) { return get(eventId, null); }
    public Models.Event get(String eventId, RequestOptions options) {
        return transport.request("GET", "/v1/events/" + eventId, null, Models.Event.class, options);
    }

    /** GET /v1/events */
    public List<Models.Event> list() { return list(null); }
    public List<Models.Event> list(RequestOptions options) {
        return transport.requestList("GET", "/v1/events", null, Models.Event.class, options);
    }
}
