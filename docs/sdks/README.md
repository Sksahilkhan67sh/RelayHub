# RelayHub SDKs

Four official SDKs, all thin typed wrappers over the same REST API documented in
[`docs/api`](../api) -- no SDK contains business logic the API doesn't already
implement. Full per-SDK docs live in each package's own README; this page is the
cross-SDK summary plus the honest verification-status disclosure requested for
Phase D.

| SDK | Package | README | Verification status |
|---|---|---|---|
| Node.js / TypeScript | [`sdks/node`](../../sdks/node) | [README](../../sdks/node/README.md) | ✅ Built, typechecked, 12/12 tests passing |
| Python | [`sdks/python`](../../sdks/python) | [README](../../sdks/python/README.md) | ✅ ruff clean, mypy clean, 13/13 tests passing |
| Go | [`sdks/go`](../../sdks/go) | [README](../../sdks/go/README.md) | ⚠️ **No Go toolchain in this environment** -- written and manually reviewed, never compiled or run here |
| Java | [`sdks/java`](../../sdks/java) | [README](../../sdks/java/README.md) | ⚠️ **No JDK compiler in this environment** (JRE only) and Maven Central is unreachable from this sandbox's network allowlist -- written and manually reviewed, never compiled or run here |

## Installation

| SDK | Command |
|---|---|
| Node.js | `npm install relayhub-sdk` |
| Python | `pip install relayhub` |
| Go | `go get github.com/relayhub/relayhub-go` |
| Java | Maven dependency `dev.relayhub:relayhub-sdk:1.0.0` |

## Authentication / client creation

All four take an API key and construct a client either directly or via a
builder:

```ts
// Node
const client = new RelayHubClient({ apiKey });
// or: RelayHubClient.builder().apiKey(apiKey).timeout(10_000).build();
```
```python
# Python
client = RelayHubClient(api_key=api_key)
# or: RelayHubClient.builder().api_key(api_key).timeout(10.0).build()
```
```go
// Go
client := relayhub.New(apiKey)
// or: relayhub.NewBuilder().APIKey(apiKey).Timeout(10*time.Second).Build()
```
```java
// Java
RelayHubClient client = new RelayHubClient(apiKey);
// or: RelayHubClient.builder().apiKey(apiKey).timeout(Duration.ofSeconds(10)).build();
```

Session bearer tokens (from `POST /auth/login`) work the same way as API keys
for every route except `POST /events`, which requires an actual API key with
the `events:write` scope -- see [`docs/api/README.md`](../api/README.md#authentication).

## Resources (identical across all four)

`auth`, `apiKeys`/`api_keys`/`APIKeys`, `organizations` (+ nested
`invitations`), `endpoints`, `events`, `deliveries`, `dlq`, `analytics`,
`billing`, `notifications`, `audit`. See [`docs/api/README.md`](../api/README.md)
for what each maps to.

**Not included, in every SDK, deliberately:** a "Projects" resource -- no such
entity exists in the backend.

**`notifications` in every SDK** maps to the real `/alerts/*` endpoints; see
[`docs/api/notifications.md`](../api/notifications.md).

## Retries

All four retry 429 and 5xx responses (and, for Node/Python/Go, network errors)
with exponential backoff, honoring a `Retry-After` header when the server sends
one. Configurable globally (client construction) and per-call.

## Timeouts

All four support a client-level default timeout and a per-call override
(`options.timeoutMs` / `RequestOptions(timeout=...)` / `WithTimeout(...)` /
`RequestOptions.builder().timeout(...)`).

## Pagination

RelayHub's list endpoints return a plain array with `limit`/`offset` query
params -- no cursor, no envelope. Every SDK ships a small pagination helper
(`paginate`/`collectAll` in Node and Python, `Paginate`/`CollectAll` in Go,
`Pagination.paginate`/`collectAll` in Java) that walks pages until one comes
back shorter than requested.

## Idempotency

`POST /events` accepts an `idempotency_key` field in its request body (not a
header -- see [`docs/api/events.md`](../api/events.md)). Every SDK exposes this
as a first-class option on the publish call rather than requiring you to set it
in the payload object yourself.

## Error handling

Every SDK maps non-2xx responses to typed exceptions/errors with the same
shape: message, HTTP status, optional machine code, optional request id, and
(for 429s) a parsed `Retry-After` value. See each SDK's README for the exact
class/type names.

## Limitations

- **Go and Java are unverified in this development environment** (see the table
  above) -- both were written and manually reviewed with extra care, but neither
  has been mechanically compiled here. Run `go build ./... && go test ./...`
  (Go) or `mvn compile test` (Java) in an environment with the respective
  toolchain before depending on them in production.
- No SDK supports the `sms` alert channel end-to-end, because the backend
  itself doesn't -- `sms` exists only as a named constant (architecture hook),
  not a working send path. See `REMAINING_WORK.md`.
- No SDK wraps `POST /billing/webhook` -- it's Stripe's inbound receiver, never
  called by an API consumer.
