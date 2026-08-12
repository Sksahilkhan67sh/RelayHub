package relayhub

import "context"

type AnalyticsService struct{ t *transport }

// RangeParams filters every analytics query. All fields optional.
type RangeParams struct {
	Environment string
	StartDate   string
	EndDate     string
}

func (p RangeParams) toOptions() []RequestOption {
	var opts []RequestOption
	if p.Environment != "" {
		opts = append(opts, WithQuery("environment", p.Environment))
	}
	if p.StartDate != "" {
		opts = append(opts, WithQuery("start_date", p.StartDate))
	}
	if p.EndDate != "" {
		opts = append(opts, WithQuery("end_date", p.EndDate))
	}
	return opts
}

// Summary calls GET /v1/analytics/summary -- totals and latency percentiles for the range.
func (s *AnalyticsService) Summary(ctx context.Context, params RangeParams, opts ...RequestOption) (Summary, error) {
	return decode[Summary](s.t.do(ctx, "GET", "/v1/analytics/summary", nil, append(params.toOptions(), opts...)...))
}

// DeliveriesOverTime calls GET /v1/analytics/deliveries-over-time.
func (s *AnalyticsService) DeliveriesOverTime(ctx context.Context, params RangeParams, granularity string, opts ...RequestOption) ([]TimeSeriesBucket, error) {
	allOpts := params.toOptions()
	if granularity != "" {
		allOpts = append(allOpts, WithQuery("granularity", granularity))
	}
	return decode[[]TimeSeriesBucket](s.t.do(ctx, "GET", "/v1/analytics/deliveries-over-time", nil, append(allOpts, opts...)...))
}

// EventsByType calls GET /v1/analytics/events-by-type.
func (s *AnalyticsService) EventsByType(ctx context.Context, params RangeParams, opts ...RequestOption) ([]EventTypeVolume, error) {
	return decode[[]EventTypeVolume](s.t.do(ctx, "GET", "/v1/analytics/events-by-type", nil, append(params.toOptions(), opts...)...))
}

// TopEndpoints calls GET /v1/analytics/top-endpoints.
func (s *AnalyticsService) TopEndpoints(ctx context.Context, params RangeParams, opts ...RequestOption) ([]TopEndpoint, error) {
	return decode[[]TopEndpoint](s.t.do(ctx, "GET", "/v1/analytics/top-endpoints", nil, append(params.toOptions(), opts...)...))
}

// EndpointHealth calls GET /v1/analytics/endpoint-health.
func (s *AnalyticsService) EndpointHealth(ctx context.Context, opts ...RequestOption) ([]EndpointHealth, error) {
	return decode[[]EndpointHealth](s.t.do(ctx, "GET", "/v1/analytics/endpoint-health", nil, opts...))
}

// Export calls GET /v1/analytics/export -- CSV export; returns the raw text
// body. report is required: "deliveries-over-time" or "top-endpoints".
func (s *AnalyticsService) Export(ctx context.Context, report string, params RangeParams, opts ...RequestOption) (string, error) {
	allOpts := append(params.toOptions(), WithQuery("report", report))
	raw, err := s.t.do(ctx, "GET", "/v1/analytics/export", nil, append(allOpts, opts...)...)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}
