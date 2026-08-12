import type { Transport, RequestOptions } from "../transport.js";
import type { EndpointHealthOut, EventTypeVolume, SummaryOut, TimeSeriesBucket, TopEndpointOut } from "../types.js";

export interface AnalyticsRangeParams {
  environment?: string;
  start_date?: string;
  end_date?: string;
}

export class AnalyticsResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/analytics/summary -- totals and latency percentiles for the range. */
  summary(params?: AnalyticsRangeParams, options?: RequestOptions) {
    return this.transport.request<SummaryOut>("GET", "/v1/analytics/summary", undefined, { ...options, query: { ...params } });
  }

  /** GET /v1/analytics/deliveries-over-time */
  deliveriesOverTime(params?: AnalyticsRangeParams & { granularity?: "hour" | "day" }, options?: RequestOptions) {
    return this.transport.request<TimeSeriesBucket[]>("GET", "/v1/analytics/deliveries-over-time", undefined, { ...options, query: { ...params } });
  }

  /** GET /v1/analytics/events-by-type */
  eventsByType(params?: AnalyticsRangeParams, options?: RequestOptions) {
    return this.transport.request<EventTypeVolume[]>("GET", "/v1/analytics/events-by-type", undefined, { ...options, query: { ...params } });
  }

  /** GET /v1/analytics/top-endpoints */
  topEndpoints(params?: AnalyticsRangeParams, options?: RequestOptions) {
    return this.transport.request<TopEndpointOut[]>("GET", "/v1/analytics/top-endpoints", undefined, { ...options, query: { ...params } });
  }

  /** GET /v1/analytics/endpoint-health */
  endpointHealth(options?: RequestOptions) {
    return this.transport.request<EndpointHealthOut[]>("GET", "/v1/analytics/endpoint-health", undefined, options);
  }

  /** GET /v1/analytics/export -- CSV export; returns the raw text body. `report` selects which report to export. */
  export(params: AnalyticsRangeParams & { report: "deliveries-over-time" | "top-endpoints"; granularity?: "hour" | "day" }, options?: RequestOptions) {
    return this.transport.request<string>("GET", "/v1/analytics/export", undefined, { ...options, query: { ...params } });
  }
}
