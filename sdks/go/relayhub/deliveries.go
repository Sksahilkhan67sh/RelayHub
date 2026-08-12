package relayhub

import (
	"context"
	"strconv"
)

type DeliveriesService struct{ t *transport }

// SearchLogsParams filters GET /v1/logs, the searchable delivery log explorer.
// Every field is optional; zero values are omitted from the query.
type SearchLogsParams struct {
	EndpointID   string
	Status       []string
	EventType    string
	Environment  string
	RequestID    string
	WorkerID     string
	QueuedAfter  string
	QueuedBefore string
	MinLatencyMs *int
	MaxLatencyMs *int
	Limit        int
	Offset       int
}

func (p SearchLogsParams) toOptions() []RequestOption {
	var opts []RequestOption
	add := func(k, v string) {
		if v != "" {
			opts = append(opts, WithQuery(k, v))
		}
	}
	add("endpoint_id", p.EndpointID)
	for _, st := range p.Status {
		opts = append(opts, WithQuery("status", st))
	}
	add("event_type", p.EventType)
	add("environment", p.Environment)
	add("request_id", p.RequestID)
	add("worker_id", p.WorkerID)
	add("queued_after", p.QueuedAfter)
	add("queued_before", p.QueuedBefore)
	if p.MinLatencyMs != nil {
		opts = append(opts, WithQuery("min_latency_ms", strconv.Itoa(*p.MinLatencyMs)))
	}
	if p.MaxLatencyMs != nil {
		opts = append(opts, WithQuery("max_latency_ms", strconv.Itoa(*p.MaxLatencyMs)))
	}
	if p.Limit > 0 {
		opts = append(opts, WithQuery("limit", strconv.Itoa(p.Limit)))
	}
	if p.Offset > 0 {
		opts = append(opts, WithQuery("offset", strconv.Itoa(p.Offset)))
	}
	return opts
}

// Get calls GET /v1/deliveries/{jobId}.
func (s *DeliveriesService) Get(ctx context.Context, jobID string, opts ...RequestOption) (DeliveryJob, error) {
	return decode[DeliveryJob](s.t.do(ctx, "GET", "/v1/deliveries/"+jobID, nil, opts...))
}

// ListByEvent calls GET /v1/deliveries/by-event/{eventId} -- every delivery job
// (one per subscribed endpoint) produced by a single event.
func (s *DeliveriesService) ListByEvent(ctx context.Context, eventID string, opts ...RequestOption) ([]DeliveryJob, error) {
	return decode[[]DeliveryJob](s.t.do(ctx, "GET", "/v1/deliveries/by-event/"+eventID, nil, opts...))
}

// SearchLogs calls GET /v1/logs -- the searchable delivery log explorer backing
// the dashboard's Logs page: every attempt, filterable by endpoint, status, event
// type, environment, request ID, worker, queued-date range, and latency range.
func (s *DeliveriesService) SearchLogs(ctx context.Context, params SearchLogsParams, opts ...RequestOption) ([]DeliveryLogEntry, error) {
	allOpts := append(params.toOptions(), opts...)
	return decode[[]DeliveryLogEntry](s.t.do(ctx, "GET", "/v1/logs", nil, allOpts...))
}
