export interface AnalyticsSummary {
  total_events: number;
  total_deliveries: number;
  success_count: number;
  failed_count: number;
  retrying_count: number;
  dead_letter_count: number;
  success_rate: number | null;
  failure_rate: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_p99_ms: number | null;
}

export interface TimeSeriesBucket {
  bucket: string;
  total_count: number;
  success_count: number;
  failed_count: number;
}

export interface TopEndpoint {
  endpoint_id: string;
  name: string;
  delivery_count: number;
  success_count: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
}

export interface UsageSummary {
  period_start: string;
  period_end: string;
  delivery_count: number;
  max_deliveries_per_month: number | null;
  percent_used: number | null;
  endpoint_count: number;
  max_endpoints: number | null;
}

export type ApiKeyEnvironment = "live" | "test";
export const API_KEY_SCOPES = [
  "events:write",
  "events:read",
  "deliveries:read",
  "endpoints:read",
  "endpoints:write",
  "*",
] as const;
export type ApiKeyScope = (typeof API_KEY_SCOPES)[number];

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

export interface ApiKeyCreatedOut {
  id: string;
  name: string;
  environment: string;
  scopes: string[];
  key: string;
  key_prefix: string;
  expires_at: string | null;
  created_at: string;
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

export const BUILT_IN_EVENT_TYPES = [
  "order.created",
  "order.updated",
  "payment.success",
  "payment.failed",
  "invoice.created",
  "invoice.paid",
  "subscription.created",
  "subscription.cancelled",
  "refund.created",
  "shipment.created",
  "shipment.delivered",
] as const;

export interface DeliveryAttemptOut {
  id: string;
  attempt_number: number;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  http_status: number | null;
  response_headers: Record<string, string>;
  response_body_truncated: string | null;
  error_category: string;
  error_message: string | null;
  worker_id: string;
  destination_ip: string | null;
}

export interface DeliveryJobOut {
  id: string;
  event_id: string;
  endpoint_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: string;
  attempt_number: number;
  max_attempts: number;
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
  max_attempts: number;
  queued_at: string;
  next_attempt_at: string | null;
  completed_at: string | null;
  attempts: DeliveryAttemptOut[];
}

export interface EventOut {
  id: string;
  event: string;
  environment: string;
  payload: Record<string, unknown>;
  request_id: string;
  created_at: string;
  delivery_jobs: { id: string; endpoint_id: string; status: string }[];
}

export interface DeadLetterJobOut {
  id: string;
  event_id: string;
  endpoint_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  attempt_number: number;
  max_attempts: number;
  queued_at: string;
  completed_at: string | null;
  last_error_category: string | null;
  last_error_message: string | null;
  attempts: DeliveryAttemptOut[];
}

export const ALERT_CONDITION_TYPES = [
  "endpoint_down",
  "queue_full",
  "dlq_spike",
  "api_key_leak_suspicion",
  "high_latency",
  "repeated_failures",
  "billing_threshold",
  "rate_limit_abuse",
] as const;

export const ALERT_CHANNELS = ["email", "slack", "discord", "webhook", "sms"] as const;
export const ALERT_SEVERITIES = ["info", "warning", "critical"] as const;

export interface AlertRuleOut {
  id: string;
  condition_type: string;
  severity: string;
  channel: string;
  channel_config: Record<string, string>;
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

export interface EventTypeVolume {
  event_type: string;
  count: number;
}

export interface EndpointHealthOut {
  endpoint_id: string;
  name: string;
  health_status: string;
  consecutive_failure_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  is_active: boolean;
}

export const MEMBER_ROLES = ["owner", "admin", "member", "viewer"] as const;

export interface MemberOut {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  invited_by_user_id: string | null;
  accepted_at: string | null;
  joined_at: string;
}

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

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

export interface AuditLogOut {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata_json: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
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

export interface AdminOrganizationOut {
  id: string;
  name: string;
  slug: string;
  is_suspended: boolean;
  suspension_reason: string | null;
  plan_tier: string | null;
  subscription_status: string | null;
  member_count: number;
  endpoint_count: number;
  created_at: string;
}

export interface QueueDepthOut {
  queued: number;
  processing: number;
  retrying: number;
  dead_letter: number;
  success_last_hour: number;
  failed_last_hour: number;
}

export interface WorkerInstanceOut {
  worker_id: string;
  hostname: string;
  pid: number;
  last_heartbeat_at: string;
  healthy: boolean;
}

export interface WorkerHealthOut {
  healthy_count: number;
  unhealthy_count: number;
  workers: WorkerInstanceOut[];
}

export interface SystemHealthOut {
  database_ok: boolean;
  queue_depth: QueueDepthOut;
  worker_health: WorkerHealthOut;
  checked_at: string;
}

export interface DeliveryMetricsOut {
  window_seconds: number;
  avg_delivery_latency_ms: number | null;
  p95_delivery_latency_ms: number | null;
  retry_rate: number | null;
  dlq_rate: number | null;
  stuck_jobs_count: number;
  sample_size: number;
}

export interface ForceActionResponse {
  id: string;
  status: string;
}

export interface BillingOverviewOut {
  total_organizations: number;
  organizations_by_tier: Record<string, number>;
  mrr_cents: number;
  canceled_this_month: number;
  past_due_count: number;
}

export interface AdminFeatureFlagOut {
  id: string;
  key: string;
  description: string;
  is_enabled_globally: boolean;
  created_at: string;
}

export interface FeatureFlagOverrideOut {
  id: string;
  flag_id: string;
  organization_id: string;
  organization_name: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AbuseReportOut {
  id: string;
  organization_id: string;
  reason: string;
  status: string;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AdminLogEntry {
  id: string;
  organization_id: string;
  event_id: string;
  endpoint_id: string;
  status: string;
  attempt_number: number;
  queued_at: string;
  completed_at: string | null;
}

export type ContentStatus = "draft" | "published";

export interface BlogPostOut {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  author_name: string;
  author_role: string;
  read_minutes: number;
  body: string[];
  status: ContentStatus;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobPostingOut {
  id: string;
  title: string;
  team: string;
  location: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// --- Phase 3: AI Intelligence Layer (/v1/insights/intelligence/...) ---
// NOTE: distinct from EndpointHealthOut above (that one is the Phase 1/2
// circuit-breaker health used for auto-pause decisions -- see
// backend/app/modules/endpoints/models.py's EndpointHealth enum). This is the
// separate, analytical health/anomaly/incident/RCA layer added in Phase 3; the
// two "health" concepts are related but not the same field or the same source.

export interface EvidenceItem {
  label: string;
  value: string | number;
}

export interface EndpointHealthSnapshotOut {
  id: string;
  endpoint_id: string;
  window_start: string;
  window_end: string;
  status: "healthy" | "degraded" | "unhealthy" | "critical" | "unknown";
  health_score: number | null;
  confidence: number;
  sample_size: number;
  success_rate: number | null;
  failure_rate: number | null;
  http_4xx_rate: number | null;
  http_5xx_rate: number | null;
  timeout_rate: number | null;
  retry_rate: number | null;
  dlq_rate: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  supporting_signals: Record<string, unknown>;
}

export interface AnomalyOut {
  id: string;
  endpoint_id: string | null;
  metric: string;
  direction: "spike" | "drop" | "trend" | "regression";
  observed_value: number;
  baseline_value: number;
  delta: number;
  observed_at: string;
  confidence: number;
  sample_size: number;
  evidence: EvidenceItem[];
  incident_id: string | null;
}

export interface RootCauseAnalysisOut {
  id: string;
  source: "deterministic" | "ai";
  likely_cause: string;
  confidence_level: "confirmed" | "highly_likely" | "likely" | "possible" | "unknown";
  confidence_score: number;
  evidence: EvidenceItem[];
  recommendations: string[];
  ai_provider: string | null;
  ai_model: string | null;
  created_at: string;
}

export interface IncidentOut {
  id: string;
  endpoint_id: string | null;
  status: "open" | "investigating" | "recovering" | "resolved";
  failure_category: string;
  severity: "info" | "warning" | "critical";
  title: string;
  summary: string;
  opened_at: string;
  recovering_since: string | null;
  resolved_at: string | null;
  last_signal_at: string;
}

export interface IncidentDetailOut extends IncidentOut {
  anomalies: AnomalyOut[];
  rca_entries: RootCauseAnalysisOut[];
}

export interface RecommendationsOut {
  incident_id: string;
  recommendations: string[];
}

export interface TimelineEventOut {
  type: "incident_opened" | "anomaly" | "recovering" | "resolved";
  at: string;
  detail: string;
}

export interface IncidentTimelineOut {
  incident_id: string;
  status: string;
  events: TimelineEventOut[];
}

