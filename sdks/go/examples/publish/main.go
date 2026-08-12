// Example: create an endpoint and publish an event to it.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/relayhub/relayhub-go/relayhub"
)

func main() {
	apiKey := os.Getenv("RELAYHUB_API_KEY")
	if apiKey == "" {
		log.Fatal("set RELAYHUB_API_KEY")
	}

	client := relayhub.New(apiKey)
	ctx := context.Background()

	endpoint, err := client.Endpoints.Create(ctx, relayhub.CreateEndpointRequest{
		Name:                 "Local dev webhook",
		URL:                  "https://example.com/webhooks/relayhub",
		Environment:          "test",
		SubscribedEventTypes: []string{"payment.success"},
	})
	if err != nil {
		log.Fatalf("create endpoint: %v", err)
	}
	fmt.Printf("created endpoint %s (%s)\n", endpoint.ID, endpoint.Name)

	event, err := client.Events.Publish(ctx, relayhub.PublishEventRequest{
		Event:       "payment.success",
		Environment: "test",
		Payload:     map[string]any{"order_id": "ord_123", "amount": 4200},
	}, relayhub.WithIdempotencyKey("ord_123-payment-success"))
	if err != nil {
		log.Fatalf("publish event: %v", err)
	}
	fmt.Printf("published event %s -- %d delivery job(s) queued\n", event.ID, len(event.DeliveryJobs))
}
