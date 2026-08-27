import type { Transport, RequestOptions } from "../transport.js";
import type {
  EndpointHealthSnapshotOut,
  IncidentDetailOut,
  IncidentOut,
  IncidentTimelineOut,
  InsightAnomalyOut,
  RecommendationsOut,
  RootCauseAnalysisOut,
} from "../types.js";

/**
 * Phase 3 AI Intelligence layer -- mounted at /v1/insights/intelligence/...,
 * not bare /v1/insights/..., because that path is already owned by
 * AnalyticsResource's alias (see backend/app/modules/insights/routes.py's
 * module docstring). Analytics is raw metrics/reporting; this resource is
 * derived health/anomaly/incident/RCA state built on top of it -- keep the
 * FACT (deterministic) vs INFERENCE (ai) distinction visible in anything you
 * build on top of these methods (RootCauseAnalysisOut.source).
 */
export class InsightsResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/insights/intelligence/health */
  health(params?: { endpoint_id?: string }, options?: RequestOptions) {
    return this.transport.request<EndpointHealthSnapshotOut[]>("GET", "/v1/insights/intelligence/health", undefined, {
      ...options,
      query: { ...params },
    });
  }

  /** GET /v1/insights/intelligence/health/{endpointId}/history */
  healthHistory(endpointId: string, params?: { limit?: number; offset?: number }, options?: RequestOptions) {
    return this.transport.request<EndpointHealthSnapshotOut[]>(
      "GET",
      `/v1/insights/intelligence/health/${endpointId}/history`,
      undefined,
      { ...options, query: { ...params } }
    );
  }

  /** GET /v1/insights/intelligence/anomalies */
  anomalies(
    params?: { endpoint_id?: string; metric?: string; since?: string; limit?: number; offset?: number },
    options?: RequestOptions
  ) {
    return this.transport.request<InsightAnomalyOut[]>("GET", "/v1/insights/intelligence/anomalies", undefined, {
      ...options,
      query: { ...params },
    });
  }

  /** GET /v1/insights/intelligence/incidents */
  incidents(params?: { status?: string; endpoint_id?: string; limit?: number; offset?: number }, options?: RequestOptions) {
    return this.transport.request<IncidentOut[]>("GET", "/v1/insights/intelligence/incidents", undefined, {
      ...options,
      query: { ...params },
    });
  }

  /** GET /v1/insights/intelligence/incidents/{incidentId} */
  getIncident(incidentId: string, options?: RequestOptions) {
    return this.transport.request<IncidentDetailOut>("GET", `/v1/insights/intelligence/incidents/${incidentId}`, undefined, options);
  }

  /** GET /v1/insights/intelligence/incidents/{incidentId}/rca */
  incidentRca(incidentId: string, options?: RequestOptions) {
    return this.transport.request<RootCauseAnalysisOut[]>(
      "GET",
      `/v1/insights/intelligence/incidents/${incidentId}/rca`,
      undefined,
      options
    );
  }

  /** GET /v1/insights/intelligence/incidents/{incidentId}/recommendations */
  incidentRecommendations(incidentId: string, options?: RequestOptions) {
    return this.transport.request<RecommendationsOut>(
      "GET",
      `/v1/insights/intelligence/incidents/${incidentId}/recommendations`,
      undefined,
      options
    );
  }

  /** GET /v1/insights/intelligence/incidents/{incidentId}/timeline */
  incidentTimeline(incidentId: string, options?: RequestOptions) {
    return this.transport.request<IncidentTimelineOut>(
      "GET",
      `/v1/insights/intelligence/incidents/${incidentId}/timeline`,
      undefined,
      options
    );
  }
}
