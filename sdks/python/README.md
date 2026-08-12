# relayhub (Python)

Official Python SDK for the [RelayHub](https://relayhub.dev) webhook and event
delivery API. Thin, typed wrapper over `/v1/*` -- every method maps 1:1 to a real
REST endpoint (see the [API reference](../../docs/api)); the SDK adds no business
logic of its own. Built on [httpx](https://www.python-httpx.org/), its only
dependency.

## Install

```bash
pip install relayhub
```

Requires Python 3.10+.

## Quick start

```python
import os
from relayhub import RelayHubClient

client = RelayHubClient(api_key=os.environ["RELAYHUB_API_KEY"])

endpoint = client.endpoints.create(
    name="Production webhook",
    url="https://api.example.com/webhooks/relayhub",
    environment="live",
    subscribed_event_types=["payment.success", "payment.failed"],
)

from relayhub import RequestOptions

client.events.publish(
    event="payment.success",
    payload={"order_id": "ord_123", "amount": 4200},
    options=RequestOptions(idempotency_key="ord_123-payment-success"),  # safe to retry publish() with the same key
)
```

Or with the builder:

```python
client = (
    RelayHubClient.builder()
    .api_key(os.environ["RELAYHUB_API_KEY"])
    .timeout(10.0)
    .max_retries(3)
    .header("X-Client-Name", "checkout-service")
    .build()
)
```

Use it as a context manager to close the underlying HTTP connection pool:

```python
with RelayHubClient(api_key=api_key) as client:
    client.endpoints.list()
```

## Resources

Every resource below is a thin wrapper over the matching route in
[`docs/api`](../../docs/api) -- `client.<resource>.<method>()`:

| Resource | Covers |
|---|---|
| `auth` | register, login, refresh, logout, me, forgot/reset password |
| `api_keys` | create, list, revoke, rotate |
| `organizations` | update org, members, and `organizations.invitations.*` (email invites) |
| `endpoints` | create, list, get, update, delete, rotate signing secret |
| `events` | publish, get, list |
| `deliveries` | get a delivery job, list by event, `search_logs()` (the filterable delivery log) |
| `dlq` | list, get, `retry()` / `bulk_retry()` (this is where "replay" lives), discard, export |
| `analytics` | summary, time series, event-type volume, top endpoints, health, export |
| `billing` | plans, subscription, usage, invoices, checkout, portal |
| `notifications` | alert rules and history -- see note below |
| `audit` | audit log |

**Not included:** an organization-scoped concept called "Projects" doesn't exist in
the RelayHub API today -- endpoints and events live directly under an
organization. **`notifications`** maps to RelayHub's alert-rule endpoints
(`/v1/alerts/*`): Slack/Discord/webhook/email notifications fired on a
failure-rate threshold. There's no separate `/notifications` route in the backend;
this is that feature under the name developers actually look for.

## Pagination

List endpoints return a plain array with `limit`/`offset` query params, not a
cursor envelope:

```python
from relayhub import paginate

for job in paginate(lambda limit, offset: client.dlq.list(limit=limit, offset=offset)):
    print(job["id"], job["last_error_message"])
```

## Error handling

```python
from relayhub import RelayHubNotFoundError, RelayHubRateLimitError

try:
    client.endpoints.get(endpoint_id)
except RelayHubNotFoundError as err:
    ...
except RelayHubRateLimitError as err:
    print(f"retry after {err.retry_after_seconds}s")
```

`RelayHubConnectionError` is raised for network failures and client-side timeouts.

## Retries and timeouts

429s and 5xx responses are retried automatically with exponential backoff
(honoring `Retry-After` when the server sends one):

```python
client = RelayHubClient(api_key=api_key, timeout=10.0, max_retries=3)

client.endpoints.list(options=RequestOptions(timeout=2.0, max_retries=0))  # override for this call
```

## Idempotency

RelayHub's publish-event endpoint accepts an `idempotency_key` field on the
request body (not a header). `RequestOptions(idempotency_key=...)` sets it.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check relayhub tests
mypy relayhub
```

## License

MIT
