# relayhub-sdk (Java)

Official Java SDK for the [RelayHub](https://relayhub.dev) webhook and event
delivery API. Thin, typed wrapper over `/v1/*` -- every method maps 1:1 to a real
REST endpoint (see the [API reference](../../docs/api)); the SDK adds no business
logic of its own. Built on `java.net.http.HttpClient` (JDK 11+, no HTTP library
dependency); Jackson is the SDK's only runtime dependency, for JSON.

## Install

Maven:

```xml
<dependency>
  <groupId>dev.relayhub</groupId>
  <artifactId>relayhub-sdk</artifactId>
  <version>1.0.0</version>
</dependency>
```

Requires Java 17+.

## Quick start

```java
import dev.relayhub.sdk.*;

RelayHubClient client = new RelayHubClient(System.getenv("RELAYHUB_API_KEY"));

var createReq = new EndpointsResource.CreateEndpointRequest(
        "Production webhook", "https://api.example.com/webhooks/relayhub");
createReq.environment = "live";
createReq.subscribedEventTypes = List.of("payment.success", "payment.failed");
Models.Endpoint endpoint = client.getEndpoints().create(createReq);

var publishReq = new EventsResource.PublishEventRequest("payment.success");
publishReq.payload = Map.of("order_id", "ord_123", "amount", 4200);
client.getEvents().publish(publishReq,
        RequestOptions.builder().idempotencyKey("ord_123-payment-success").build());
```

Or with the builder:

```java
RelayHubClient client = RelayHubClient.builder()
        .apiKey(System.getenv("RELAYHUB_API_KEY"))
        .timeout(Duration.ofSeconds(10))
        .maxRetries(3)
        .header("X-Client-Name", "checkout-service")
        .build();
```

## Resources

Every resource below is a thin wrapper over the matching route in
[`docs/api`](../../docs/api) -- `client.get<Resource>().<method>(...)`:

| Resource | Covers |
|---|---|
| `getAuth()` | register, login, refresh, logout, me, forgot/reset password |
| `getApiKeys()` | create, list, revoke, rotate |
| `getOrganizations()` | update org, members, and `.invitations()` (email invites) |
| `getEndpoints()` | create, list, get, update, delete, rotate signing secret |
| `getEvents()` | publish, get, list |
| `getDeliveries()` | get a delivery job, listByEvent, `searchLogs()` (the filterable delivery log) |
| `getDlq()` | list, get, `retry()`/`bulkRetry()` (this is where "replay" lives), discard, export |
| `getAnalytics()` | summary, time series, event-type volume, top endpoints, health, export |
| `getBilling()` | plans, subscription, usage, invoices, checkout, portal |
| `getNotifications()` | alert rules and history -- see note below |
| `getAudit()` | list |

**Not included:** an organization-scoped concept called "Projects" doesn't exist
in the RelayHub API today -- endpoints and events live directly under an
organization. **`Notifications`** maps to RelayHub's alert-rule endpoints
(`/v1/alerts/*`): Slack/Discord/webhook/email notifications fired on a
failure-rate threshold. There's no separate `/notifications` route in the
backend; this is that feature under the name developers actually look for.

## Pagination

```java
Pagination.paginate(50,
    job -> System.out.println(job.id),
    (limit, offset) -> client.getDlq().list(null, limit, offset));
```

## Error handling

Every non-2xx response throws a typed subclass of `RelayHubException`:

```java
try {
    client.getEndpoints().get(id);
} catch (RelayHubException.NotFoundException e) {
    // ...
} catch (RelayHubException.RateLimitException e) {
    System.out.println("retry after " + e.getRetryAfterSeconds() + "s");
}
```

`RelayHubException.ConnectionException` is thrown for network failures and
client-side timeouts.

## Retries and timeouts

429s and 5xx responses are retried automatically with exponential backoff
(honoring `Retry-After` when the server sends one):

```java
RelayHubClient client = RelayHubClient.builder()
        .apiKey(apiKey).timeout(Duration.ofSeconds(10)).maxRetries(3).build();

client.getEndpoints().list(RequestOptions.builder().timeout(Duration.ofSeconds(2)).maxRetries(0).build());
```

## Idempotency

RelayHub's publish-event endpoint accepts an `idempotency_key` field on the
request body (not a header). `RequestOptions.builder().idempotencyKey(...)` sets it.

## Development

```bash
mvn compile
mvn test
```

> **This SDK was authored without a JDK compiler available in the environment it
> was written in** (only a JRE was present -- no `javac`, and Maven Central isn't
> reachable from that sandbox either). Every file was written and manually
> reviewed for correctness, but unlike the Node.js and Python SDKs in this
> repository, this one has **not been mechanically compiled or run**. Run
> `mvn compile test` before relying on it in production, and see
> `PHASE_D_REPORT.md` for the full disclosure.

## License

MIT
