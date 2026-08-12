# @relayhub/sdk

Official Node.js / TypeScript SDK for the [RelayHub](https://relayhub.dev) webhook
and event delivery API. Thin, typed wrapper over `/v1/*` -- every method maps 1:1
to a real REST endpoint (see the [API reference](../../docs/api)); the SDK adds no
business logic of its own.

## Install

```bash
npm install @relayhub/sdk
```

Requires Node 18+ (uses the global `fetch`).

## Quick start

```ts
import { RelayHubClient } from "@relayhub/sdk";

const client = new RelayHubClient({ apiKey: process.env.RELAYHUB_API_KEY! });

const endpoint = await client.endpoints.create({
  name: "Production webhook",
  url: "https://api.example.com/webhooks/relayhub",
  environment: "live",
  subscribed_event_types: ["payment.success", "payment.failed"],
});

await client.events.publish(
  { event: "payment.success", payload: { orderId: "ord_123", amount: 4200 } },
  { idempotencyKey: "ord_123-payment-success" } // safe to retry publish() with the same key
);
```

Or with the builder, if you prefer assembling config conditionally:

```ts
const client = RelayHubClient.builder()
  .apiKey(process.env.RELAYHUB_API_KEY!)
  .timeout(10_000)
  .maxRetries(3)
  .header("X-Client-Name", "checkout-service")
  .build();
```

## Resources

Every resource below is a thin wrapper over the matching route in
[`docs/api`](../../docs/api) -- `client.<resource>.<method>()`:

| Resource | Covers |
|---|---|
| `auth` | register, login, refresh, logout, me, forgot/reset password |
| `apiKeys` | create, list, revoke, rotate |
| `organizations` | update org, members, and `organizations.invitations.*` (email invites) |
| `endpoints` | create, list, get, update, delete, rotate signing secret |
| `events` | publish, get, list |
| `deliveries` | get a delivery job, list by event, `searchLogs()` (the filterable delivery log) |
| `dlq` | list, get, `retry()` / `bulkRetry()` (this is where "replay" lives), discard, export |
| `analytics` | summary, time series, event-type volume, top endpoints, health, export |
| `billing` | plans, subscription, usage, invoices, checkout, portal |
| `notifications` | alert rules and history -- see note below |
| `audit` | audit log |

**Not included:** an `organizations`-scoped concept called "Projects" doesn't exist
in the RelayHub API today -- endpoints and events live directly under an
organization. **`notifications`** maps to RelayHub's alert-rule endpoints
(`/v1/alerts/*`): Slack/Discord/webhook/email notifications fired on a failure-rate
threshold. There's no separate `/notifications` route in the backend; this is
that feature under the name developers actually look for.

## Pagination

List endpoints return a plain array with `limit`/`offset` query params, not a
cursor envelope. Use `paginate`/`collectAll` to walk a full result set:

```ts
import { paginate } from "@relayhub/sdk";

for await (const job of paginate((page) => client.dlq.list({ ...page }))) {
  console.log(job.id, job.last_error_message);
}
```

## Error handling

Every non-2xx response raises a typed subclass of `RelayHubError`:

```ts
import { RelayHubNotFoundError, RelayHubRateLimitError } from "@relayhub/sdk";

try {
  await client.endpoints.get(id);
} catch (err) {
  if (err instanceof RelayHubNotFoundError) {
    // ...
  } else if (err instanceof RelayHubRateLimitError) {
    console.log(`retry after ${err.retryAfterSeconds}s`);
  } else {
    throw err;
  }
}
```

`RelayHubConnectionError` is raised for network failures and client-side timeouts
(nothing ever reached the server).

## Retries and timeouts

429s and 5xx responses are retried automatically with exponential backoff (honoring
`Retry-After` when the server sends one). Configure globally via the client, or
per-call:

```ts
const client = new RelayHubClient({ apiKey, timeoutMs: 10_000, maxRetries: 3 });

await client.endpoints.list({ timeoutMs: 2_000, maxRetries: 0 }); // override for this call
```

## Custom headers

```ts
await client.events.publish(
  { event: "user.invited" },
  { headers: { "X-Request-Source": "signup-flow" } }
);
```

## Idempotency

RelayHub's publish-event endpoint accepts an `idempotency_key` field on the request
body (not a header). The SDK exposes it as `options.idempotencyKey` on
`events.publish()` so retried publishes on your side don't create duplicate events.

## Development

```bash
npm install
npm run build       # emit dist/
npm run typecheck
npm test             # compiles tests, then runs them with node --test
```

## License

MIT
