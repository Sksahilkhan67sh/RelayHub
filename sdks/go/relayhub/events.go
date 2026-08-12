package relayhub

import "context"

type EventsService struct{ t *transport }

type PublishEventRequest struct {
	Event       string         `json:"event"`
	Payload     map[string]any `json:"payload,omitempty"`
	Environment string         `json:"environment,omitempty"`
}

// Publish calls POST /v1/events -- publishes an event, fanning it out to every
// endpoint subscribed to Event in the given environment. Use WithIdempotencyKey
// to make republishing the same logical event safe to retry on your side.
func (s *EventsService) Publish(ctx context.Context, req PublishEventRequest, opts ...RequestOption) (Event, error) {
	return decode[Event](s.t.do(ctx, "POST", "/v1/events", req, opts...))
}

// Get calls GET /v1/events/{id}.
func (s *EventsService) Get(ctx context.Context, eventID string, opts ...RequestOption) (Event, error) {
	return decode[Event](s.t.do(ctx, "GET", "/v1/events/"+eventID, nil, opts...))
}

// List calls GET /v1/events.
func (s *EventsService) List(ctx context.Context, opts ...RequestOption) ([]Event, error) {
	return decode[[]Event](s.t.do(ctx, "GET", "/v1/events", nil, opts...))
}
