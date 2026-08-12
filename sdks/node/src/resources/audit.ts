import type { Transport, RequestOptions } from "../transport.js";
import type { AuditLogOut } from "../types.js";

export class AuditResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/audit-logs */
  list(params?: { limit?: number; offset?: number }, options?: RequestOptions) {
    return this.transport.request<AuditLogOut[]>("GET", "/v1/audit-logs", undefined, { ...options, query: { ...params } });
  }
}
