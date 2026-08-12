import type { Transport, RequestOptions } from "../transport.js";
import type { ApiKeyCreatedResponse, ApiKeyOut } from "../types.js";

export interface CreateApiKeyParams {
  name: string;
  environment?: "test" | "live";
  scopes?: string[];
  expires_in_days?: number;
}

export class ApiKeysResource {
  constructor(private readonly transport: Transport) {}

  /** POST /v1/api-keys -- the full `key` is only ever present on this response. Store it now; it can't be retrieved again. */
  create(params: CreateApiKeyParams, options?: RequestOptions) {
    return this.transport.request<ApiKeyCreatedResponse>("POST", "/v1/api-keys", params, options);
  }

  /** GET /v1/api-keys */
  list(options?: RequestOptions) {
    return this.transport.request<ApiKeyOut[]>("GET", "/v1/api-keys", undefined, options);
  }

  /** POST /v1/api-keys/{id}/revoke */
  revoke(keyId: string, params?: { reason?: string }, options?: RequestOptions) {
    return this.transport.request<ApiKeyOut>("POST", `/v1/api-keys/${keyId}/revoke`, params, options);
  }

  /** POST /v1/api-keys/{id}/rotate -- revokes the old key and issues a new one; `key` is shown once, same as create(). */
  rotate(keyId: string, options?: RequestOptions) {
    return this.transport.request<ApiKeyCreatedResponse>("POST", `/v1/api-keys/${keyId}/rotate`, undefined, options);
  }
}
