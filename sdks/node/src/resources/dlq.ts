import type { Transport, RequestOptions } from "../transport.js";
import type { BulkRetryResponse, DeadLetterJobOut, RetryDeadLetterResponse } from "../types.js";

export class DlqResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/dlq -- deliveries that exhausted their retry budget. */
  list(params?: { endpoint_id?: string; limit?: number; offset?: number }, options?: RequestOptions) {
    return this.transport.request<DeadLetterJobOut[]>("GET", "/v1/dlq", undefined, { ...options, query: { ...params } });
  }

  /** GET /v1/dlq/{jobId} */
  get(jobId: string, options?: RequestOptions) {
    return this.transport.request<DeadLetterJobOut>("GET", `/v1/dlq/${jobId}`, undefined, options);
  }

  /**
   * POST /v1/dlq/{jobId}/retry -- replays a single dead-lettered delivery as a
   * fresh attempt (same signed payload, doesn't re-trigger the source event).
   * This is what "replay" means in the RelayHub API today: it's a DLQ operation,
   * not a separate top-level `/replay` endpoint.
   */
  retry(jobId: string, options?: RequestOptions) {
    return this.transport.request<RetryDeadLetterResponse>("POST", `/v1/dlq/${jobId}/retry`, undefined, options);
  }

  /** POST /v1/dlq/bulk-retry -- replays up to 500 dead-lettered deliveries in one call. */
  bulkRetry(jobIds: string[], options?: RequestOptions) {
    return this.transport.request<BulkRetryResponse>("POST", "/v1/dlq/bulk-retry", { job_ids: jobIds }, options);
  }

  /** DELETE /v1/dlq/{jobId} -- permanently discards a dead-lettered delivery without replaying it. 204 No Content on success. */
  discard(jobId: string, options?: RequestOptions) {
    return this.transport.request<void>("DELETE", `/v1/dlq/${jobId}`, undefined, options);
  }

  /** GET /v1/dlq/export -- CSV export; returns the raw text body. */
  export(params?: { endpoint_id?: string }, options?: RequestOptions) {
    return this.transport.request<string>("GET", "/v1/dlq/export", undefined, { ...options, query: { ...params } });
  }
}
