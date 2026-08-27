package relayhub

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"testing"
)

func TestInsightsHealthHitsIntelligencePathNotBareInsights(t *testing.T) {
	var capturedPath, capturedQuery string
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		capturedQuery = r.URL.Query().Get("endpoint_id")
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]EndpointHealthSnapshot{})
	})
	defer server.Close()

	result, err := client.Insights.Health(context.Background(), "ep_1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Regression guard: /v1/insights/... (bare) is already owned by the
	// analytics alias -- this service must hit /v1/insights/intelligence/...
	// or it would silently collide with analytics summary/export routes.
	if capturedPath != "/v1/insights/intelligence/health" {
		t.Errorf("expected /v1/insights/intelligence/health, got %q", capturedPath)
	}
	if capturedQuery != "ep_1" {
		t.Errorf("expected endpoint_id=ep_1, got %q", capturedQuery)
	}
	if len(result) != 0 {
		t.Errorf("expected empty result, got %v", result)
	}
}

func TestInsightsHealthHistoryBuildsPathWithEndpointID(t *testing.T) {
	var capturedPath string
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]EndpointHealthSnapshot{})
	})
	defer server.Close()

	_, err := client.Insights.HealthHistory(context.Background(), "ep_42", 10, 5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if capturedPath != "/v1/insights/intelligence/health/ep_42/history" {
		t.Errorf("expected /v1/insights/intelligence/health/ep_42/history, got %q", capturedPath)
	}
}

func TestInsightsAnomaliesPassesAllFiltersAsQueryParams(t *testing.T) {
	var capturedQuery url.Values
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedQuery = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]InsightAnomaly{})
	})
	defer server.Close()

	_, err := client.Insights.Anomalies(context.Background(), AnomaliesParams{
		EndpointID: "ep_1", Metric: "latency_p95", Since: "2026-01-01T00:00:00Z", Limit: 25,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if capturedQuery.Get("endpoint_id") != "ep_1" || capturedQuery.Get("metric") != "latency_p95" ||
		capturedQuery.Get("since") != "2026-01-01T00:00:00Z" || capturedQuery.Get("limit") != "25" {
		t.Errorf("unexpected query params: %v", capturedQuery)
	}
}

func TestInsightsGetIncidentHitsDetailPath(t *testing.T) {
	var capturedPath string
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(IncidentDetail{
			Incident:   Incident{ID: "inc_1", Status: "resolved"},
			Anomalies:  []InsightAnomaly{},
			RCAEntries: []RootCauseAnalysis{},
		})
	})
	defer server.Close()

	incident, err := client.Insights.GetIncident(context.Background(), "inc_1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if capturedPath != "/v1/insights/intelligence/incidents/inc_1" {
		t.Errorf("expected detail path, got %q", capturedPath)
	}
	if incident.ID != "inc_1" {
		t.Errorf("expected incident ID inc_1, got %q", incident.ID)
	}
}

func TestInsightsIncidentRCAKeepsDeterministicAndAISourcesDistinguishable(t *testing.T) {
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]RootCauseAnalysis{
			{ID: "rca_1", Source: "deterministic", LikelyCause: "Endpoint returning 503s"},
			{ID: "rca_2", Source: "ai", LikelyCause: "Possible downstream dependency outage"},
		})
	})
	defer server.Close()

	entries, err := client.Insights.IncidentRCA(context.Background(), "inc_1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(entries) != 2 || entries[0].Source != "deterministic" || entries[1].Source != "ai" {
		t.Errorf("expected one deterministic and one ai entry, got %+v", entries)
	}
}

func TestInsightsIncidentRecommendationsPathAndShape(t *testing.T) {
	var capturedPath string
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(Recommendations{IncidentID: "inc_1", Recommendations: []string{"Increase timeout"}})
	})
	defer server.Close()

	recs, err := client.Insights.IncidentRecommendations(context.Background(), "inc_1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if capturedPath != "/v1/insights/intelligence/incidents/inc_1/recommendations" {
		t.Errorf("expected recommendations path, got %q", capturedPath)
	}
	if len(recs.Recommendations) != 1 || recs.Recommendations[0] != "Increase timeout" {
		t.Errorf("unexpected recommendations: %v", recs.Recommendations)
	}
}

func TestInsightsIncidentTimelinePathAndShape(t *testing.T) {
	var capturedPath string
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(IncidentTimeline{
			IncidentID: "inc_1",
			Status:     "open",
			Events:     []IncidentTimelineEvent{{Type: "anomaly_detected", At: "2026-01-01T00:00:00Z", Detail: "d"}},
		})
	})
	defer server.Close()

	timeline, err := client.Insights.IncidentTimeline(context.Background(), "inc_1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if capturedPath != "/v1/insights/intelligence/incidents/inc_1/timeline" {
		t.Errorf("expected timeline path, got %q", capturedPath)
	}
	if len(timeline.Events) != 1 || timeline.Events[0].Type != "anomaly_detected" {
		t.Errorf("unexpected events: %v", timeline.Events)
	}
}
