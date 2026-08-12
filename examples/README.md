# RelayHub Developer Examples

Real, runnable examples exercising only endpoints that actually exist in the
backend (see [`docs/api`](../docs/api)).

| Example | Language | What it does |
|---|---|---|
| [`node/publish.mjs`](./node/publish.mjs) | Node.js | Create an endpoint, publish an event, with an idempotency key |
| [`node/replay.mjs`](./node/replay.mjs) | Node.js | List the DLQ and replay a dead-lettered delivery |
| [`python/publish.py`](./python/publish.py) | Python | Same as the Node example, using the Python SDK |
| [`go` publish example](../sdks/go/examples/publish/main.go) | Go | Create an endpoint and publish an event (lives under the Go SDK -- see note below) |
| [`java` publish example](../sdks/java/examples/PublishExample.java) | Java | Same, using the Java SDK (lives under the Java SDK -- see note below) |
| [`webhook-receiver/server.mjs`](./webhook-receiver/server.mjs) | Node.js | A minimal HTTP server that receives a RelayHub delivery and verifies its signature |
| [`signature-verification/verify.mjs`](./signature-verification/verify.mjs) / [`verify.py`](./signature-verification/verify.py) | Node.js, Python | Standalone signature verification, no server needed |

**Why the Go and Java examples live under `sdks/go/examples` and
`sdks/java/examples` instead of here:** they were written alongside those SDKs
(Phase D, first pass) and depend on the SDK's local module path; moving them
would mean re-wiring `go.mod`/Maven paths for no benefit. They cover the same
"event publishing" scenario as the Node/Python examples in this directory.

## Prerequisites

All examples read `RELAYHUB_API_KEY` (and, for management operations like
creating an endpoint, a session token) from the environment. None of them are
mocked -- they make real HTTP calls to whatever `RELAYHUB_BASE_URL` points to
(default: `https://api.relayhub.dev/v1`; point it at
`http://localhost:8000/v1` for a local Docker Compose backend, see
[`docs/self-hosting`](../docs/self-hosting/README.md)).
