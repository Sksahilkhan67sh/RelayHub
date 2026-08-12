// Typed models mirroring the real Pydantic response schemas in
// backend/app/modules/*/schemas.py. Field names and shapes are kept identical to
// the API's actual JSON so the SDK never has to translate or guess -- see each
// resource file for the endpoint it corresponds to.

export type Role = "owner" | "admin" | "member" | "viewer";
export type EndpointEnvironment = "test" | "live";
export type DeliveryStatus = "queued" | "processing" | "success" | "retrying" | "failed" | "dead_letter" | "pending";
export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
}

export interface OrganizationOut {
  id: string;
  name: string;
  slug: string;
}

export interface MeResponse {
  user: UserOut;
  organization: OrganizationOut;
  role: Role;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface MemberOut {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  invited_by_user_id: string | null;
  accepted_at: string | null;
  joined_at: string;
}

export interface InvitationOut {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  invited_by_user_id: string;
  status: InvitationStatus;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyOut {
  id: string;
  name: string;
  environment: string;
  scopes: string[];
  key_prefix: string;
  masked_key: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
  created_at: string;
}

/** Only ever returned once, at creation or rotation time -- `key` is never retrievable again. */
export interface ApiKeyCreatedResponse extends Omit<ApiKeyOut, "masked_key" | "revoked_at" | "is_active" | "last_used_at"> {
  key: string;
}

export interface EndpointOut {
  id: string;
  name: string;
  description: string | null;
  url: string;
  environment: string;
  custom_headers: Record<string, string>;
  timeout_seconds: number;
  subscribed_event_types: string[];
  ip_allowlist: string[];
  is_active: boolean;
  tls_verification_enabled: boolean;
  max_retry_attempts: number | null;
  health_status: string;
  consecutive_failure_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  paused_at: string | null;
  paused_reason: string | null;
  created_at: string;
}

export interface EndpointSecretOut {
  id: string;
  secret: string;
  grace_period_ends_at: string | null;
  created_at: string;
}

export interface DeliveryJobSummary {
  id: string;
  endpoint_id: string;
  status: string;
}

export interface EventOut {
  id: string;
  event: string;
  environment: string;
  payload: Record<string, unknown>;
  request_id: string;
  created_at: string;
  delivery_jobs: DeliveryJobSummary[];
}

export interface DeliveryAttemptOut {
  id: string;
  attempt_number: number;
  status: string;
  response_status_code: number | null;
  latency_ms: number | null;
  error_category: string | null;
  error_message: string | null;
  attempted_at: string;
}

export interface DeliveryJobOut {
  id: string;
  event_id: string;
  endpoint_id: string;
  status: string;
  attempt_number: number;
  queued_at: string;
  next_attempt_at: string | null;
  completed_at: string | null;
  attempts: DeliveryAttemptOut[];
}

export interface DeliveryLogEntryOut {
  id: string;
  event_id: string;
  endpoint_id: string;
  event_type: string;
  environment: string;
  request_id: string;
  status: string;
  attempt_number: number;
  queued_at: string;
  next_attempt_at: string | null;
  completed_at: string | null;
  attempts: DeliveryAttemptOut[];
}

export interface DeadLetterJobOut {
  id: string;
  event_id: string;
  endpoint_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  attempt_number: number;
  queued_at: string;
  completed_at: string | null;
  last_error_category: string | null;
  last_error_message: string | null;
  attempts: DeliveryAttemptOut[];
}

export interface RetryDeadLetterResponse {
  id: string;
  status: string;
}

export interface BulkRetryResponse {
  retried: string[];
  skipped: string[];
}

export interface SummaryOut {
  total_events: number;
  total_deliveries: number;
  success_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
}

export interface TimeSeriesBucket {
  bucket: string;
  success_count: number;
  failure_count: number;
}

export interface EventTypeVolume {
  event_type: string;
  count: number;
}

export interface TopEndpointOut {
  endpoint_id: string;
  endpoint_name: string;
  delivery_count: number;
  failure_rate: number;
}

export interface EndpointHealthOut {
  endpoint_id: string;
  endpoint_name: string;
  health_status: string;
  consecutive_failure_count: number;
}

export interface PlanOut {
  id: string;
  tier: string;
  name: string;
  price_cents: number;
  max_deliveries_per_month: number | null;
  max_endpoints: number | null;
  log_retention_days: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  allow_overage: boolean;
  has_advanced_analytics: boolean;
  has_priority_support: boolean;
  has_sso: boolean;
}

export interface SubscriptionOut {
  id: string;
  plan: PlanOut;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
}

export interface UsageOut {
  period_start: string;
  period_end: string;
  delivery_count: number;
  max_deliveries_per_month: number | null;
  percent_used: number | null;
  endpoint_count: number;
  max_endpoints: number | null;
}

export interface InvoiceOut {
  id: string;
  stripe_invoice_id: string;
  amount_cents: number;
  status: string;
  invoice_pdf_url: string | null;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
}

export interface CheckoutSessionOut {
  checkout_url: string;
}

export interface PortalSessionOut {
  portal_url: string;
}

/**
 * "Notifications" in RelayHub's product surface are alert rules (Slack, Discord,
 * webhook, or email) that fire when an endpoint's failure rate crosses a
 * threshold -- there's no separate "notifications" API, this *is* it.
 */
export interface AlertRuleOut {
  id: string;
  condition_type: string;
  severity: string;
  channel: string;
  channel_config: Record<string, unknown>;
  threshold_config: Record<string, unknown>;
  throttle_window_minutes: number;
  is_enabled: boolean;
  created_at: string;
}

export interface AlertEventOut {
  id: string;
  condition_type: string;
  severity: string;
  message: string;
  resource_id: string | null;
  delivery_status: string;
  delivery_error: string | null;
  triggered_at: string;
  delivered_at: string | null;
}

export interface TestAlertResponse {
  delivery_status: string;
  delivery_error: string | null;
}

export interface AuditLogOut {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}
