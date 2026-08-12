import type { Transport, RequestOptions } from "../transport.js";
import type { DeliveryJobOut, DeliveryLogEntryOut, DeliveryStatus } from "../types.js";

export interface SearchDeliveryLogsParams {
  endpoint_id?: string;
  status?: DeliveryStatus[];
  event_type?: string;
  environment?: string;
  request_id?: string;
  worker_id?: string;
  queued_after?: string;
  queued_before?: string;
  min_latency_ms?: number;
  max_latency_ms?: number;
  limit?: number;
  offset?: number;
}

export class DeliveriesResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/deliveries/{jobId} */
  get(jobId: string, options?: RequestOptions) {
    return this.transport.request<DeliveryJobOut>("GET", `/v1/deliveries/${jobId}`, undefined, options);
  }

  /** GET /v1/deliveries/by-event/{eventId} -- every delivery job (one per subscribed endpoint) produced by a single event. */
  listByEvent(eventId: string, options?: RequestOptions) {
    return this.transport.request<DeliveryJobOut[]>("GET", `/v1/deliveries/by-event/${eventId}`, undefined, options);
  }

  /**
   * GET /v1/logs -- the searchable delivery log explorer: every attempt, filterable
   * by endpoint, status, event type, environment, request ID, worker, queued-date
   * range, and latency range. This is the read model backing the dashboard's Logs page.
   */
  searchLogs(params?: SearchDeliveryLogsParams, options?: RequestOptions) {
    return this.transport.request<DeliveryLogEntryOut[]>("GET", "/v1/logs", undefined, { ...options, query: { ...params } });
  }
}
