/**
 * Shared data for the API reference page and the docs search index --
 * kept in one place so the two can never drift apart.
 */
export interface Field {
  name: string;
  type: string;
  note?: string;
}

export interface Endpoint {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  auth: string;
  summary: string;
  params?: Field[];
  body?: Field[];
  response: string;
  example?: string;
}

export interface Module {
  id: string;
  title: string;
  intro: string;
  endpoints: Endpoint[];
}

export const MODULES: Module[] = [
  {
    id: "authentication",
    title: "Authentication",
    intro: "Dashboard user sessions -- separate from API keys, which have their own module below.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/auth/register",
        auth: "None (public)",
        summary: "Create a user account and its first organization in one call.",
        body: [
          { name: "email", type: "string" },
          { name: "password", type: "string", note: "8-128 chars, needs 1 uppercase + 1 digit" },
          { name: "full_name", type: "string" },
          { name: "organization_name", type: "string" },
        ],
        response: "TokenResponse -- access_token, refresh_token, token_type: \"bearer\", expires_in",
      },
      { method: "POST", path: "/v1/auth/login", auth: "None (public)", summary: "Exchange email/password for a session.", body: [{ name: "email", type: "string" }, { name: "password", type: "string" }], response: "TokenResponse" },
      { method: "POST", path: "/v1/auth/refresh", auth: "None (public)", summary: "Exchange a refresh token for a new access token.", body: [{ name: "refresh_token", type: "string" }], response: "TokenResponse" },
      { method: "POST", path: "/v1/auth/logout", auth: "Session", summary: "Invalidate the current session.", response: "204 No Content" },
      {
        method: "GET",
        path: "/v1/auth/me",
        auth: "Session",
        summary: "Fetch the current user, their organization, and their role in it.",
        response: "MeResponse -- user (id, email, full_name, is_email_verified, is_platform_admin), organization (id, name, slug), role",
      },
      { method: "POST", path: "/v1/auth/forgot-password", auth: "None (public)", summary: "Request a password reset email.", body: [{ name: "email", type: "string" }], response: "ForgotPasswordResponse -- message (always generic, to avoid confirming whether an email exists)" },
      { method: "POST", path: "/v1/auth/reset-password", auth: "None (public)", summary: "Complete a password reset with the emailed token.", body: [{ name: "token", type: "string" }, { name: "new_password", type: "string", note: "same complexity rule as registration" }], response: "204 No Content" },
    ],
  },
  {
    id: "api-keys",
    title: "API keys",
    intro: "Scoped, environment-bound credentials for server-to-server calls -- see the Authentication concept for how these differ from sessions.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/api-keys",
        auth: "Session (admin)",
        summary: "Create a key. The full secret is returned exactly once, in this response only.",
        body: [
          { name: "name", type: "string" },
          { name: "environment", type: "\"test\" | \"live\"", note: "default: test" },
          { name: "scopes", type: "string[]", note: "default: [events:write, events:read]" },
          { name: "expires_in_days", type: "int? (1-3650)" },
        ],
        response: "ApiKeyCreatedResponse -- id, name, environment, scopes, key (full secret, shown once), key_prefix, expires_at, created_at",
      },
      {
        method: "GET",
        path: "/v1/api-keys",
        auth: "Session (viewer)",
        summary: "List keys. Never includes the secret -- only a masked representation.",
        response: "ApiKeyOut[] -- id, name, environment, scopes, key_prefix, masked_key, last_used_at, expires_at, revoked_at, is_active, created_at",
      },
      { method: "POST", path: "/v1/api-keys/{key_id}/revoke", auth: "Session (admin)", summary: "Revoke a key immediately -- no grace period.", body: [{ name: "reason", type: "string?" }], response: "ApiKeyOut" },
      { method: "POST", path: "/v1/api-keys/{key_id}/rotate", auth: "Session (admin)", summary: "Revoke the old key and issue a new one with the same name/scopes in one call.", response: "ApiKeyCreatedResponse" },
    ],
  },
  {
    id: "organizations",
    title: "Organizations & members",
    intro: "Manage your organization's settings, members, and pending invitations.",
    endpoints: [
      { method: "PATCH", path: "/v1/org", auth: "Session (admin)", summary: "Rename your organization.", body: [{ name: "name", type: "string" }], response: "OrganizationOut -- id, name, slug" },
      { method: "GET", path: "/v1/org/members", auth: "Session (viewer)", summary: "List every member of your organization.", response: "MemberOut[] -- user_id, email, full_name, role, invited_by_user_id, accepted_at, joined_at" },
      { method: "PATCH", path: "/v1/org/members/{user_id}", auth: "Session (admin)", summary: "Change a member's role.", body: [{ name: "role", type: "\"owner\" | \"admin\" | \"member\" | \"viewer\"" }], response: "204 No Content" },
      { method: "DELETE", path: "/v1/org/members/{user_id}", auth: "Session (admin)", summary: "Remove a member from the organization.", response: "204 No Content" },
      { method: "POST", path: "/v1/org/invitations", auth: "Session (admin)", summary: "Invite someone by email.", body: [{ name: "email", type: "string" }, { name: "role", type: "Role", note: "default: member" }], response: "InvitationOut -- id, organization_id, email, role, invited_by_user_id, status, expires_at, accepted_at, revoked_at, created_at" },
      { method: "GET", path: "/v1/org/invitations", auth: "Session (admin)", summary: "List pending/past invitations.", response: "InvitationOut[]" },
      { method: "POST", path: "/v1/org/invitations/{invitation_id}/revoke", auth: "Session (admin)", summary: "Revoke a pending invitation.", response: "InvitationOut" },
      {
        method: "GET",
        path: "/v1/invitations/{token}",
        auth: "None (public)",
        summary: "Look up an invitation by its emailed token -- deliberately minimal fields since this is reachable before any login.",
        response: "InvitationPublicOut -- organization_name, email, role, status, expires_at",
      },
      {
        method: "POST",
        path: "/v1/invitations/accept",
        auth: "None (public)",
        summary: "Accept an invitation. If the invitee has no account yet, full_name/password also create one.",
        body: [{ name: "token", type: "string" }, { name: "full_name", type: "string?", note: "required only for a brand-new account" }, { name: "password", type: "string?", note: "required only for a brand-new account" }],
        response: "TokenResponse",
      },
    ],
  },
  {
    id: "events",
    title: "Events",
    intro: "Publish events and read back what was published.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/events",
        auth: "API key (events:write scope)",
        summary: "Publish an event. Fans out to every active endpoint subscribed to this event type.",
        body: [
          { name: "event", type: "string", note: "e.g. \"payment.success\"" },
          { name: "payload", type: "object", note: "arbitrary JSON" },
          { name: "environment", type: "\"test\" | \"live\"", note: "default: test" },
          { name: "idempotency_key", type: "string?" },
          { name: "endpoint_ids", type: "uuid[]?", note: "restrict delivery to specific endpoints, bypassing subscription filtering" },
        ],
        response: "EventOut -- id, event, environment, payload, request_id, created_at, delivery_jobs[] (each with id, endpoint_id, status)",
        example: `curl -X POST https://api.relayhub.dev/v1/events \\
  -H "X-RelayHub-Api-Key: YOUR_API_KEY" -H "Content-Type: application/json" \\
  -d '{"event": "payment.success", "payload": {"order_id": "ord_123"}, "environment": "test"}'`,
      },
      {
        method: "GET",
        path: "/v1/events/{event_id}",
        auth: "Session (viewer)",
        summary: "Fetch one published event by ID.",
        response: "EventOut (same shape as above)",
      },
      {
        method: "GET",
        path: "/v1/events",
        auth: "Session (viewer)",
        summary: "List every event published in your organization.",
        response: "EventOut[]",
      },
    ],
  },
  {
    id: "endpoints",
    title: "Endpoints",
    intro: "Manage delivery destinations.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/endpoints",
        auth: "Session (admin)",
        summary: "Create an endpoint. The URL is validated against SSRF protections at registration time.",
        body: [
          { name: "name", type: "string" },
          { name: "description", type: "string?" },
          { name: "url", type: "string" },
          { name: "environment", type: "\"test\" | \"live\"", note: "default: test" },
          { name: "custom_headers", type: "object", note: "default: {}" },
          { name: "timeout_seconds", type: "int", note: "1-120, default 15" },
          { name: "subscribed_event_types", type: "string[]", note: "empty = all event types" },
          { name: "ip_allowlist", type: "string[]" },
          { name: "tls_verification_enabled", type: "bool", note: "default: true" },
          { name: "max_retry_attempts", type: "int? (0-20)", note: "overrides the platform default of 5" },
        ],
        response: "EndpointOut -- see the field list below",
      },
      { method: "GET", path: "/v1/endpoints", auth: "Session (viewer)", summary: "List every endpoint in your organization.", response: "EndpointOut[]" },
      { method: "GET", path: "/v1/endpoints/{endpoint_id}", auth: "Session (viewer)", summary: "Fetch one endpoint.", response: "EndpointOut" },
      {
        method: "PATCH",
        path: "/v1/endpoints/{endpoint_id}",
        auth: "Session (admin)",
        summary: "Partially update an endpoint. Every field is optional -- only fields you send are changed.",
        body: [
          { name: "name, description, url, custom_headers, timeout_seconds,", type: "" },
          { name: "subscribed_event_types, ip_allowlist, is_active,", type: "" },
          { name: "tls_verification_enabled, max_retry_attempts", type: "all optional, same types as create" },
        ],
        response: "EndpointOut",
      },
      { method: "DELETE", path: "/v1/endpoints/{endpoint_id}", auth: "Session (admin)", summary: "Soft-delete an endpoint. Past delivery history is preserved.", response: "204 No Content" },
      {
        method: "POST",
        path: "/v1/endpoints/{endpoint_id}/rotate-secret",
        auth: "Session (admin)",
        summary: "Rotate the signing secret. The old secret stays valid for a grace period so in-flight verification doesn't break.",
        body: [{ name: "grace_period_hours", type: "int", note: "0-720, default 24" }],
        response: "EndpointSecretOut -- id, secret (shown once), grace_period_ends_at, created_at",
      },
    ],
  },
  {
    id: "deliveries",
    title: "Deliveries",
    intro: "Inspect individual delivery jobs and their full attempt history.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/deliveries/{job_id}",
        auth: "Session (viewer)",
        summary: "Fetch one delivery job with its full attempt history.",
        response: "DeliveryJobOut -- id, event_id, endpoint_id, event_type, payload, status, attempt_number, max_attempts, queued_at, next_attempt_at, completed_at, attempts[]",
      },
      {
        method: "GET",
        path: "/v1/deliveries/by-event/{event_id}",
        auth: "Session (viewer)",
        summary: "List every delivery job that resulted from one event (one per subscribed endpoint).",
        response: "DeliveryJobOut[]",
      },
    ],
  },
  {
    id: "logs",
    title: "Logs",
    intro: "Search delivery history across your whole organization with flexible filters.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/logs",
        auth: "Session (viewer)",
        summary: "Search delivery jobs. All filters are optional and combine with AND.",
        params: [
          { name: "endpoint_id", type: "uuid?" },
          { name: "status", type: "string[]?", note: "queued, processing, success, retrying, failed, dead_letter, or the synthetic \"pending\"" },
          { name: "event_type", type: "string?" },
          { name: "environment", type: "string?" },
          { name: "request_id", type: "string?" },
          { name: "worker_id", type: "string?" },
          { name: "queued_after / queued_before", type: "datetime?" },
          { name: "min_latency_ms / max_latency_ms", type: "int?" },
          { name: "limit", type: "int", note: "1-200, default 50" },
          { name: "offset", type: "int", note: "default 0" },
        ],
        response: "DeliveryLogEntryOut[] -- same shape as DeliveryJobOut plus environment and request_id",
      },
    ],
  },
  {
    id: "dlq",
    title: "Dead-letter queue",
    intro: "Inspect, export, retry, and delete deliveries that exhausted every retry attempt.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/dlq",
        auth: "Session (viewer)",
        summary: "List dead-lettered jobs.",
        params: [{ name: "endpoint_id", type: "uuid?" }, { name: "limit", type: "int (1-200, default 50)" }, { name: "offset", type: "int (default 0)" }],
        response: "DeadLetterJobOut[]",
      },
      { method: "GET", path: "/v1/dlq/export", auth: "Session (viewer)", summary: "Download every DLQ entry as CSV.", params: [{ name: "endpoint_id", type: "uuid?" }], response: "text/csv (Content-Disposition: attachment)" },
      { method: "GET", path: "/v1/dlq/{job_id}", auth: "Session (viewer)", summary: "Fetch one dead-lettered job.", response: "DeadLetterJobOut" },
      { method: "POST", path: "/v1/dlq/{job_id}/retry", auth: "Session (admin)", summary: "Replay one job. Resets its attempt counter to 0 -- it gets the full retry schedule again.", response: "RetryDeadLetterResponse -- id, status" },
      { method: "DELETE", path: "/v1/dlq/{job_id}", auth: "Session (admin)", summary: "Permanently delete a dead-lettered job.", response: "204 No Content" },
      {
        method: "POST",
        path: "/v1/dlq/bulk-retry",
        auth: "Session (admin)",
        summary: "Replay several jobs in one call.",
        body: [{ name: "job_ids", type: "uuid[]", note: "1-500 items" }],
        response: "BulkRetryResponse -- retried: uuid[], skipped: uuid[]",
      },
    ],
  },
  {
    id: "analytics",
    title: "Analytics",
    intro: "Aggregate delivery metrics -- volume, latency percentiles, and per-endpoint health. All endpoints accept optional environment / start_date / end_date filters.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/analytics/summary",
        auth: "Session (viewer)",
        summary: "Org-wide totals for the selected window.",
        params: [{ name: "environment", type: "string?" }, { name: "start_date / end_date", type: "datetime?" }],
        response: "SummaryOut -- total_events, total_deliveries, success_count, failed_count, retrying_count, dead_letter_count, success_rate, failure_rate, latency_p50_ms, latency_p95_ms, latency_p99_ms",
      },
      {
        method: "GET",
        path: "/v1/analytics/deliveries-over-time",
        auth: "Session (viewer)",
        summary: "Delivery volume bucketed by hour or day.",
        params: [{ name: "granularity", type: "\"hour\" | \"day\"", note: "default: hour" }, { name: "environment, start_date, end_date", type: "same as above" }],
        response: "TimeSeriesBucket[] -- bucket, total_count, success_count, failed_count",
      },
      { method: "GET", path: "/v1/analytics/events-by-type", auth: "Session (viewer)", summary: "Event volume grouped by event type.", response: "EventTypeVolume[] -- event_type, count" },
      { method: "GET", path: "/v1/analytics/top-endpoints", auth: "Session (viewer)", summary: "Busiest endpoints by delivery volume.", response: "TopEndpointOut[] -- endpoint_id, name, delivery_count, success_count, success_rate, avg_latency_ms" },
      { method: "GET", path: "/v1/analytics/endpoint-health", auth: "Session (viewer)", summary: "Current health snapshot for every endpoint.", response: "EndpointHealthOut[] -- endpoint_id, name, health_status, consecutive_failure_count, last_success_at, last_failure_at, is_active" },
      { method: "GET", path: "/v1/analytics/export", auth: "Session (viewer)", summary: "Download analytics data for offline analysis.", response: "File download" },
    ],
  },
  {
    id: "billing",
    title: "Billing",
    intro: "Plan, subscription, usage, and invoice data. Checkout and portal sessions are Stripe-hosted.",
    endpoints: [
      { method: "GET", path: "/v1/billing/plans", auth: "Session (viewer)", summary: "List every available plan tier.", response: "PlanOut[] -- id, tier, name, price_cents, max_deliveries_per_month, max_endpoints, log_retention_days, rate_limit_per_minute/hour/day, allow_overage, has_advanced_analytics, has_priority_support, has_sso" },
      { method: "GET", path: "/v1/billing/subscription", auth: "Session (viewer)", summary: "Your organization's current subscription.", response: "SubscriptionOut -- id, plan (full PlanOut), status, current_period_start/end, trial_end, cancel_at_period_end" },
      { method: "GET", path: "/v1/billing/usage", auth: "Session (viewer)", summary: "Usage against your plan's limits for the current period.", response: "UsageOut -- period_start/end, delivery_count, max_deliveries_per_month, percent_used, endpoint_count, max_endpoints" },
      { method: "GET", path: "/v1/billing/invoices", auth: "Session (viewer)", summary: "Past invoices.", response: "InvoiceOut[] -- id, stripe_invoice_id, amount_cents, status, invoice_pdf_url, period_start/end, created_at" },
      { method: "POST", path: "/v1/billing/checkout", auth: "Session (owner)", summary: "Start a Stripe Checkout session to upgrade/subscribe.", body: [{ name: "tier", type: "\"starter\" | \"pro\" | \"enterprise\"" }], response: "CheckoutSessionOut -- Stripe-hosted checkout URL" },
      { method: "POST", path: "/v1/billing/portal", auth: "Session (owner)", summary: "Start a Stripe Billing Portal session to manage payment methods/cancel.", response: "PortalSessionOut -- Stripe-hosted portal URL" },
      { method: "POST", path: "/v1/billing/webhook", auth: "Stripe webhook signature (not a user/API-key call)", summary: "Receives Stripe's own webhook events to keep subscription state in sync. Not something you call directly.", response: "204 No Content" },
    ],
  },
  {
    id: "notifications",
    title: "Notifications (alerts)",
    intro: "Called \"alerts\" in the backend and CLI/SDKs' \"notifications\" resources wrap this same module. Configure rules that fire on conditions like endpoint downtime or a DLQ spike.",
    endpoints: [
      {
        method: "POST",
        path: "/v1/alerts/rules",
        auth: "Session (admin)",
        summary: "Create an alert rule.",
        body: [
          { name: "condition_type", type: "endpoint_down | queue_full | dlq_spike | api_key_leak_suspicion | high_latency | repeated_failures | billing_threshold | rate_limit_abuse" },
          { name: "severity", type: "info | warning | critical", note: "default: warning" },
          { name: "channel", type: "email | slack | discord | webhook | sms", note: "sms is an architecture hook, not yet wired to a real provider" },
          { name: "channel_config", type: "object" },
          { name: "threshold_config", type: "object" },
          { name: "throttle_window_minutes", type: "int (0-1440)", note: "default: see DEFAULT_THROTTLE_WINDOW_MINUTES" },
          { name: "is_enabled", type: "bool", note: "default: true" },
        ],
        response: "AlertRuleOut",
      },
      { method: "GET", path: "/v1/alerts/rules", auth: "Session (viewer)", summary: "List alert rules.", response: "AlertRuleOut[]" },
      { method: "PATCH", path: "/v1/alerts/rules/{rule_id}", auth: "Session (admin)", summary: "Update a rule. All fields optional.", response: "AlertRuleOut" },
      { method: "DELETE", path: "/v1/alerts/rules/{rule_id}", auth: "Session (admin)", summary: "Delete a rule.", response: "204 No Content" },
      { method: "POST", path: "/v1/alerts/rules/{rule_id}/test", auth: "Session (admin)", summary: "Send a test firing of a rule to its configured channel.", response: "TestAlertResponse" },
      { method: "GET", path: "/v1/alerts/history", auth: "Session (viewer)", summary: "Past alert firings.", response: "AlertEventOut[] -- id, condition_type, severity, message, resource_id, delivery_status, delivery_error, triggered_at" },
    ],
  },
  {
    id: "audit",
    title: "Audit logs",
    intro: "Every mutating action in your organization, recorded automatically.",
    endpoints: [
      {
        method: "GET",
        path: "/v1/audit-logs",
        auth: "Session (admin)",
        summary: "List audit entries.",
        response: "AuditLogOut[] -- id, actor_user_id, action, resource_type, resource_id, metadata_json, ip_address, created_at",
      },
    ],
  },
  {
    id: "admin",
    title: "Admin",
    intro: "Platform-operator endpoints, not for regular integrations -- requires is_platform_admin on your user account, a flag set on RelayHub's own team members, not a role your organization can grant itself. Included for completeness, not as something a typical customer will call.",
    endpoints: [
      { method: "GET", path: "/v1/admin/organizations", auth: "Platform admin", summary: "List every organization on the platform.", response: "AdminOrganizationOut[]" },
      { method: "POST", path: "/v1/admin/organizations/{id}/suspend", auth: "Platform admin", summary: "Suspend an organization.", response: "AdminOrganizationOut" },
      { method: "POST", path: "/v1/admin/organizations/{id}/unsuspend", auth: "Platform admin", summary: "Lift a suspension.", response: "ForceActionResponse" },
      { method: "POST", path: "/v1/admin/organizations/{id}/impersonate", auth: "Platform admin", summary: "Get a session token for a customer's organization, for support purposes.", response: "ImpersonationResponse" },
      { method: "GET", path: "/v1/admin/queues", auth: "Platform admin", summary: "Current queue depth across the platform.", response: "QueueDepthOut" },
      { method: "GET", path: "/v1/admin/system-health", auth: "Platform admin", summary: "Platform-wide health snapshot.", response: "SystemHealthOut" },
      { method: "GET", path: "/v1/admin/billing-overview", auth: "Platform admin", summary: "Platform-wide billing/revenue overview.", response: "BillingOverviewOut" },
      { method: "GET", path: "/v1/admin/logs", auth: "Platform admin", summary: "Delivery jobs across every organization -- see Global Logs in the dashboard.", response: "Cross-org delivery job list" },
      { method: "POST", path: "/v1/admin/delivery-jobs/{id}/force-retry", auth: "Platform admin", summary: "Force-retry any organization's delivery job.", response: "ForceActionResponse" },
      { method: "POST", path: "/v1/admin/delivery-jobs/{id}/force-cancel", auth: "Platform admin", summary: "Force-cancel any organization's delivery job.", response: "ForceActionResponse" },
      { method: "POST", path: "/v1/admin/feature-flags", auth: "Platform admin", summary: "Create a feature flag.", response: "FeatureFlagOut" },
      { method: "GET", path: "/v1/admin/feature-flags", auth: "Platform admin", summary: "List feature flags.", response: "FeatureFlagOut[]" },
      { method: "PATCH", path: "/v1/admin/feature-flags/{key}", auth: "Platform admin", summary: "Update a feature flag.", response: "FeatureFlagOut" },
      { method: "POST", path: "/v1/admin/feature-flags/{key}/override", auth: "Platform admin", summary: "Override a flag for one organization.", response: "Override confirmation" },
      { method: "GET", path: "/v1/admin/feature-flags/{key}/overrides", auth: "Platform admin", summary: "List per-organization overrides for a flag.", response: "FeatureFlagOverrideOut[]" },
      { method: "POST", path: "/v1/admin/abuse-reports", auth: "Platform admin", summary: "File an abuse report against an organization.", response: "AbuseReportOut" },
      { method: "GET", path: "/v1/admin/abuse-reports", auth: "Platform admin", summary: "List abuse reports.", response: "AbuseReportOut[]" },
      { method: "PATCH", path: "/v1/admin/abuse-reports/{id}", auth: "Platform admin", summary: "Update an abuse report's status.", response: "AbuseReportOut" },
    ],
  },
];
