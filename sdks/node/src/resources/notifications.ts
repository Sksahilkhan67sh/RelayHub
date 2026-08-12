import type { Transport, RequestOptions } from "../transport.js";
import type { AlertEventOut, AlertRuleOut, TestAlertResponse } from "../types.js";

/**
 * "Notifications" maps to RelayHub's alert rules: Slack, Discord, webhook, or
 * email notifications fired when an endpoint's failure rate crosses a threshold.
 * There is no separate `/notifications` API in the backend -- this resource is
 * kept under that name because that's the developer-facing concept it serves,
 * while every method below hits the real `/v1/alerts/*` routes.
 */
export class NotificationsResource {
  constructor(private readonly transport: Transport) {}

  /** POST /v1/alerts/rules */
  createRule(
    params: {
      condition_type: string;
      severity?: "info" | "warning" | "critical";
      channel: string;
      channel_config: Record<string, unknown>;
      threshold_config?: Record<string, unknown>;
      throttle_window_minutes?: number;
      is_enabled?: boolean;
    },
    options?: RequestOptions
  ) {
    return this.transport.request<AlertRuleOut>("POST", "/v1/alerts/rules", params, options);
  }

  /** GET /v1/alerts/rules */
  listRules(options?: RequestOptions) {
    return this.transport.request<AlertRuleOut[]>("GET", "/v1/alerts/rules", undefined, options);
  }

  /** PATCH /v1/alerts/rules/{id} */
  updateRule(
    ruleId: string,
    params: Partial<{
      severity: "info" | "warning" | "critical";
      channel: string;
      channel_config: Record<string, unknown>;
      threshold_config: Record<string, unknown>;
      throttle_window_minutes: number;
      is_enabled: boolean;
    }>,
    options?: RequestOptions
  ) {
    return this.transport.request<AlertRuleOut>("PATCH", `/v1/alerts/rules/${ruleId}`, params, options);
  }

  /** DELETE /v1/alerts/rules/{id} -- 204 No Content on success. */
  deleteRule(ruleId: string, options?: RequestOptions) {
    return this.transport.request<void>("DELETE", `/v1/alerts/rules/${ruleId}`, undefined, options);
  }

  /** POST /v1/alerts/rules/{id}/test -- fires a test notification through the rule's configured channel. */
  testRule(ruleId: string, options?: RequestOptions) {
    return this.transport.request<TestAlertResponse>("POST", `/v1/alerts/rules/${ruleId}/test`, undefined, options);
  }

  /** GET /v1/alerts/history */
  history(params?: { condition_type?: string; limit?: number; offset?: number }, options?: RequestOptions) {
    return this.transport.request<AlertEventOut[]>("GET", "/v1/alerts/history", undefined, { ...options, query: { ...params } });
  }
}
