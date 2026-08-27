package relayhub

import (
	"context"
	"strconv"
)

// InsightsService covers the Phase 3 AI Intelligence layer -- mounted at
// /v1/insights/intelligence/..., not bare /v1/insights/..., because that path
// is already owned by AnalyticsService's alias (see
// backend/app/modules/insights/routes.py's module docstring). Analytics is
// raw metrics/reporting; this service is derived health/anomaly/incident/RCA
// state built on top of it -- keep the FACT (deterministic) vs INFERENCE (ai)
// distinction visible in anything built on top of these methods
// (RootCauseAnalysis.Source).
type InsightsService struct{ t *transport }

// Health calls GET /v1/insights/intelligence/health.
func (s *InsightsService) Health(ctx context.Context, endpointID string, opts ...RequestOption) ([]EndpointHealthSnapshot, error) {
	allOpts := opts
	if endpointID != "" {
		allOpts = append(allOpts, WithQuery("endpoint_id", endpointID))
	}
	return decode[[]EndpointHealthSnapshot](s.t.do(ctx, "GET", "/v1/insights/intelligence/health", nil, allOpts...))
}

// HealthHistory calls GET /v1/insights/intelligence/health/{endpointId}/history.
func (s *InsightsService) HealthHistory(ctx context.Context, endpointID string, limit, offset int, opts ...RequestOption) ([]EndpointHealthSnapshot, error) {
	allOpts := opts
	if limit > 0 {
		allOpts = append(allOpts, WithQuery("limit", strconv.Itoa(limit)))
	}
	if offset > 0 {
		allOpts = append(allOpts, WithQuery("offset", strconv.Itoa(offset)))
	}
	return decode[[]EndpointHealthSnapshot](s.t.do(ctx, "GET", "/v1/insights/intelligence/health/"+endpointID+"/history", nil, allOpts...))
}

// AnomaliesParams filters an Anomalies query. All fields optional.
type AnomaliesParams struct {
	EndpointID string
	Metric     string
	Since      string
	Limit      int
	Offset     int
}

func (p AnomaliesParams) toOptions() []RequestOption {
	var opts []RequestOption
	if p.EndpointID != "" {
		opts = append(opts, WithQuery("endpoint_id", p.EndpointID))
	}
	if p.Metric != "" {
		opts = append(opts, WithQuery("metric", p.Metric))
	}
	if p.Since != "" {
		opts = append(opts, WithQuery("since", p.Since))
	}
	if p.Limit > 0 {
		opts = append(opts, WithQuery("limit", strconv.Itoa(p.Limit)))
	}
	if p.Offset > 0 {
		opts = append(opts, WithQuery("offset", strconv.Itoa(p.Offset)))
	}
	return opts
}

// Anomalies calls GET /v1/insights/intelligence/anomalies.
func (s *InsightsService) Anomalies(ctx context.Context, params AnomaliesParams, opts ...RequestOption) ([]InsightAnomaly, error) {
	return decode[[]InsightAnomaly](s.t.do(ctx, "GET", "/v1/insights/intelligence/anomalies", nil, append(params.toOptions(), opts...)...))
}

// IncidentsParams filters an Incidents query. All fields optional.
type IncidentsParams struct {
	Status     string
	EndpointID string
	Limit      int
	Offset     int
}

func (p IncidentsParams) toOptions() []RequestOption {
	var opts []RequestOption
	if p.Status != "" {
		opts = append(opts, WithQuery("status", p.Status))
	}
	if p.EndpointID != "" {
		opts = append(opts, WithQuery("endpoint_id", p.EndpointID))
	}
	if p.Limit > 0 {
		opts = append(opts, WithQuery("limit", strconv.Itoa(p.Limit)))
	}
	if p.Offset > 0 {
		opts = append(opts, WithQuery("offset", strconv.Itoa(p.Offset)))
	}
	return opts
}

// Incidents calls GET /v1/insights/intelligence/incidents.
func (s *InsightsService) Incidents(ctx context.Context, params IncidentsParams, opts ...RequestOption) ([]Incident, error) {
	return decode[[]Incident](s.t.do(ctx, "GET", "/v1/insights/intelligence/incidents", nil, append(params.toOptions(), opts...)...))
}

// GetIncident calls GET /v1/insights/intelligence/incidents/{incidentId}.
func (s *InsightsService) GetIncident(ctx context.Context, incidentID string, opts ...RequestOption) (IncidentDetail, error) {
	return decode[IncidentDetail](s.t.do(ctx, "GET", "/v1/insights/intelligence/incidents/"+incidentID, nil, opts...))
}

// IncidentRCA calls GET /v1/insights/intelligence/incidents/{incidentId}/rca.
func (s *InsightsService) IncidentRCA(ctx context.Context, incidentID string, opts ...RequestOption) ([]RootCauseAnalysis, error) {
	return decode[[]RootCauseAnalysis](s.t.do(ctx, "GET", "/v1/insights/intelligence/incidents/"+incidentID+"/rca", nil, opts...))
}

// IncidentRecommendations calls GET /v1/insights/intelligence/incidents/{incidentId}/recommendations.
func (s *InsightsService) IncidentRecommendations(ctx context.Context, incidentID string, opts ...RequestOption) (Recommendations, error) {
	return decode[Recommendations](s.t.do(ctx, "GET", "/v1/insights/intelligence/incidents/"+incidentID+"/recommendations", nil, opts...))
}

// IncidentTimeline calls GET /v1/insights/intelligence/incidents/{incidentId}/timeline.
func (s *InsightsService) IncidentTimeline(ctx context.Context, incidentID string, opts ...RequestOption) (IncidentTimeline, error) {
	return decode[IncidentTimeline](s.t.do(ctx, "GET", "/v1/insights/intelligence/incidents/"+incidentID+"/timeline", nil, opts...))
}
