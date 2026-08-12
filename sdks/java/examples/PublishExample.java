package dev.relayhub.sdk.examples;

import dev.relayhub.sdk.*;

import java.util.List;
import java.util.Map;

/** Example: create an endpoint and publish an event to it. */
public class PublishExample {
    public static void main(String[] args) {
        String apiKey = System.getenv("RELAYHUB_API_KEY");
        if (apiKey == null || apiKey.isEmpty()) {
            System.err.println("set RELAYHUB_API_KEY");
            System.exit(1);
        }

        RelayHubClient client = new RelayHubClient(apiKey);

        EndpointsResource.CreateEndpointRequest createReq =
                new EndpointsResource.CreateEndpointRequest("Local dev webhook", "https://example.com/webhooks/relayhub");
        createReq.environment = "test";
        createReq.subscribedEventTypes = List.of("payment.success");

        Models.Endpoint endpoint = client.getEndpoints().create(createReq);
        System.out.printf("created endpoint %s (%s)%n", endpoint.id, endpoint.name);

        EventsResource.PublishEventRequest publishReq = new EventsResource.PublishEventRequest("payment.success");
        publishReq.environment = "test";
        publishReq.payload = Map.of("order_id", "ord_123", "amount", 4200);

        Models.Event event = client.getEvents().publish(
                publishReq,
                RequestOptions.builder().idempotencyKey("ord_123-payment-success").build());
        System.out.printf("published event %s -- %d delivery job(s) queued%n", event.id, event.deliveryJobs.size());
    }
}
