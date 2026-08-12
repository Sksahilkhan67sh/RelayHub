# relayhub-go

Official Go SDK for the [RelayHub](https://relayhub.dev) webhook and event
delivery API. Thin, typed wrapper over `/v1/*` -- every method maps 1:1 to a real
REST endpoint (see the [API reference](../../docs/api)); the SDK adds no business
logic of its own. Standard library only (`net/http`) -- no external dependencies.

## Install

```bash
go get github.com/relayhub/relayhub-go
```

Requires Go 1.21+ (uses generics for `Paginate`/`CollectAll`).

## Quick start

```go
package main

import (
	"context"
	"log"
	"os"

	"github.com/relayhub/relayhub-go/relayhub"
)

func main() {
	client := relayhub.New(os.Getenv("RELAYHUB_API_KEY"))
	ctx := context.Background()

	endpoint, err := client.Endpoints.Create(ctx, relayhub.CreateEndpointRequest{
		Name:                 "Production webhook",
		URL:                  "https://api.example.com/webhooks/relayhub",
		Environment:          "live",
		SubscribedEventTypes: []string{"payment.success", "payment.failed"},
	})
	if err != nil {
		log.Fatal(err)
	}

	_, err = client.Events.Publish(ctx, relayhub.PublishEventRequest{
		Event:   "payment.success",
		Payload: map[string]any{"order_id": "ord_123", "amount": 4200},
	}, relayhub.WithIdempotencyKey("ord_123-payment-success")) // safe to retry Publish with the same key
	if err != nil {
		log.Fatal(err)
	}
}
```

Or with the fluent builder:

```go
client := relayhub.NewBuilder().
	APIKey(os.Getenv("RELAYHUB_API_KEY")).
	Timeout(10 * time.Second).
	MaxRetries(3).
	Header("X-Client-Name", "checkout-service").
	Build()
```

## Services

Every service below is a thin wrapper over the matching route in
[`docs/api`](../../docs/api) -- `client.<Service>.<Method>(ctx, ...)`:

| Service | Covers |
|---|---|
| `Auth` | Register, Login, Refresh, Logout, Me, ForgotPassword/ResetPassword |
| `APIKeys` | Create, List, Revoke, Rotate |
| `Organizations` | Update, members, and `Organizations.Invitations.*` (email invites) |
| `Endpoints` | Create, List, Get, Update, Delete, RotateSecret |
| `Events` | Publish, Get, List |
| `Deliveries` | Get a delivery job, ListByEvent, `SearchLogs` (the filterable delivery log) |
| `DLQ` | List, Get, `Retry`/`BulkRetry` (this is where "replay" lives), Discard, Export |
| `Analytics` | Summary, DeliveriesOverTime, EventsByType, TopEndpoints, EndpointHealth, Export |
| `Billing` | ListPlans, GetSubscription, GetUsage, ListInvoices, CreateCheckoutSession, CreatePortalSession |
| `Notifications` | Alert rules and history -- see note below |
| `Audit` | List |

**Not included:** an organization-scoped concept called "Projects" doesn't exist
in the RelayHub API today -- endpoints and events live directly under an
organization. **`Notifications`** maps to RelayHub's alert-rule endpoints
(`/v1/alerts/*`): Slack/Discord/webhook/email notifications fired on a
failure-rate threshold. There's no separate `/notifications` route in the
backend; this is that feature under the name developers actually look for.

## Pagination

List endpoints return a plain array with `limit`/`offset` query params:

```go
err := relayhub.Paginate(50, func(job relayhub.DeadLetterJob) error {
	fmt.Println(job.ID)
	return nil
}, func(limit, offset int) ([]relayhub.DeadLetterJob, error) {
	return client.DLQ.List(ctx, "", limit, offset)
})
```

## Error handling

```go
_, err := client.Endpoints.Get(ctx, id)
if relayhub.IsNotFound(err) {
	// ...
} else if relayhub.IsRateLimited(err) {
	rhErr := err.(*relayhub.Error)
	seconds, _ := rhErr.RetryAfter()
	log.Printf("retry after %.0fs", seconds)
}
```

`IsConnectionError` reports a request that never got a response (network failure
or client-side timeout).

## Retries and timeouts

429s and 5xx responses are retried automatically with exponential backoff
(honoring `Retry-After` when the server sends one):

```go
client := relayhub.New(apiKey,
	relayhub.WithClientTimeout(10*time.Second),
	relayhub.WithClientMaxRetries(3),
)

client.Endpoints.List(ctx, relayhub.WithTimeout(2*time.Second), relayhub.WithMaxRetries(0)) // override for this call
```

## Idempotency

RelayHub's publish-event endpoint accepts an `idempotency_key` field on the
request body (not a header). `relayhub.WithIdempotencyKey(...)` sets it.

## Development

```bash
go build ./...
go vet ./...
go test ./...
```

> This SDK was authored and reviewed without a local Go toolchain available in
> the environment it was written in -- see `PHASE_D_REPORT.md` for details. Run
> the commands above before relying on it in production.

## License

MIT
