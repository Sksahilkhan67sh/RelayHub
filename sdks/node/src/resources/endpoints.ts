import type { Transport, RequestOptions } from "../transport.js";
import type { EndpointOut, EndpointSecretOut } from "../types.js";

export interface CreateEndpointParams {
  name: string;
  url: string;
  description?: string;
  environment?: "test" | "live";
  custom_headers?: Record<string, string>;
  timeout_seconds?: number;
  subscribed_event_types?: string[];
  ip_allowlist?: string[];
  tls_verification_enabled?: boolean;
  max_retry_attempts?: number;
}

export type UpdateEndpointParams = Partial<CreateEndpointParams> & { is_active?: boolean };

export class EndpointsResource {
  constructor(private readonly transport: Transport) {}

  /** POST /v1/endpoints */
  create(params: CreateEndpointParams, options?: RequestOptions) {
    return this.transport.request<EndpointOut>("POST", "/v1/endpoints", params, options);
  }

  /** GET /v1/endpoints */
  list(options?: RequestOptions) {
    return this.transport.request<EndpointOut[]>("GET", "/v1/endpoints", undefined, options);
  }

  /** GET /v1/endpoints/{id} */
  get(endpointId: string, options?: RequestOptions) {
    return this.transport.request<EndpointOut>("GET", `/v1/endpoints/${endpointId}`, undefined, options);
  }

  /** PATCH /v1/endpoints/{id} */
  update(endpointId: string, params: UpdateEndpointParams, options?: RequestOptions) {
    return this.transport.request<EndpointOut>("PATCH", `/v1/endpoints/${endpointId}`, params, options);
  }

  /** DELETE /v1/endpoints/{id} -- 204 No Content on success. */
  delete(endpointId: string, options?: RequestOptions) {
    return this.transport.request<void>("DELETE", `/v1/endpoints/${endpointId}`, undefined, options);
  }

  /**
   * POST /v1/endpoints/{id}/rotate-secret -- the new secret is returned once, here.
   * `grace_period_hours` keeps the old secret valid in parallel so in-flight
   * verification on the receiving end doesn't break mid-rotation.
   */
  rotateSecret(endpointId: string, params?: { grace_period_hours?: number }, options?: RequestOptions) {
    return this.transport.request<EndpointSecretOut>("POST", `/v1/endpoints/${endpointId}/rotate-secret`, params, options);
  }
}
