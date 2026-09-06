import type { Transport } from "../transport.js";
import type { RequestOptions } from "../transport.js";
import type { MeResponse, TokenResponse } from "../types.js";

export class AuthResource {
  constructor(private readonly transport: Transport) {}

  /** POST /v1/auth/register */
  register(params: { email: string; password: string; full_name: string; organization_name: string }, options?: RequestOptions) {
    return this.transport.request<TokenResponse>("POST", "/v1/auth/register", params, options);
  }

  /** POST /v1/auth/login */
  login(params: { email: string; password: string }, options?: RequestOptions) {
    return this.transport.request<TokenResponse>("POST", "/v1/auth/login", params, options);
  }

  /** POST /v1/auth/refresh */
  refresh(params: { refresh_token: string }, options?: RequestOptions) {
    return this.transport.request<TokenResponse>("POST", "/v1/auth/refresh", params, options);
  }

  /** POST /v1/auth/logout -- 204 No Content on success. */
  logout(options?: RequestOptions) {
    return this.transport.request<void>("POST", "/v1/auth/logout", undefined, options);
  }

  /** GET /v1/auth/me */
  me(options?: RequestOptions) {
    return this.transport.request<MeResponse>("GET", "/v1/auth/me", undefined, options);
  }

  /**
   * POST /v1/auth/forgot-password -- always returns the same generic message
   * whether or not the email is registered, by design (see docs/history/PHASE_A_REPORT.md).
   */
  forgotPassword(params: { email: string }, options?: RequestOptions) {
    return this.transport.request<{ message: string }>("POST", "/v1/auth/forgot-password", params, options);
  }

  /** POST /v1/auth/reset-password -- 204 No Content on success. */
  resetPassword(params: { token: string; new_password: string }, options?: RequestOptions) {
    return this.transport.request<void>("POST", "/v1/auth/reset-password", params, options);
  }
}
