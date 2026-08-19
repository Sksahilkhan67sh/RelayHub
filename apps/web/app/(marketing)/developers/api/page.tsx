import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Section, Eyebrow } from "@/components/marketing/section";
import { Badge } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "API Reference — RelayHub Developers",
  description: "Complete reference for the RelayHub REST API: authentication, API keys, organizations, events, endpoints, deliveries, logs, and the dead-letter queue -- every method, path, auth requirement, and field verified against source.",
  alternates: { canonical: "/developers/api" },
  openGraph: {
    title: "RelayHub API Reference",
    description: "Method, path, auth, request, and response for every RelayHub endpoint -- verified against the real backend.",
    url: "/developers/api",
    type: "article",
  },
};

interface Field {
  name: string;
  type: string;
  note?: string;
}

interface Endpoint {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  auth: string;
  summary: string;
  params?: Field[];
  body?: Field[];
  response: string;
  example?: string;
}

interface Module {
  id: string;
  title: string;
  intro: string;
  endpoints: Endpoint[];
}

const MODULES: Module[] = [
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
];

function MethodBadge({ method }: { method: Endpoint["method"] }) {
  const tone = method === "GET" ? "neutral" : method === "POST" ? "green" : method === "DELETE" ? "red" : "amber";
  return <Badge tone={tone as "neutral" | "green" | "red" | "amber"}>{method}</Badge>;
}

export default function ApiReferencePage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Reference</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">API Reference</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every field below is copied from the real Pydantic request/response schemas -- nothing paraphrased from
          memory. Covers authentication, API keys, organizations, and the core delivery pipeline: Events, Endpoints,
          Deliveries, Logs, and the DLQ.
        </p>
        <p className="mt-3 max-w-2xl text-[13px] text-graphite-500">
          Not yet covered here: Analytics, Billing, Notifications, Audit, and Admin -- those modules are next.
        </p>
      </Section>

      {MODULES.map((mod, modIndex) => (
        <div key={mod.id} className={modIndex % 2 === 1 ? "border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40" : "border-t border-graphite-100 dark:border-graphite-800"}>
          <Section id={mod.id} className="scroll-mt-20 py-12">
            <h2 className="text-xl font-semibold text-graphite-950 dark:text-graphite-50">{mod.title}</h2>
            <p className="mt-1.5 text-[13.5px] text-graphite-600 dark:text-graphite-400">{mod.intro}</p>
            <div className="mt-6 flex flex-col gap-5">
              {mod.endpoints.map((ep) => (
                <div key={`${ep.method}-${ep.path}`} className="rounded-md border border-graphite-100 bg-white p-4 dark:border-graphite-800 dark:bg-graphite-900">
                  <div className="flex flex-wrap items-center gap-2">
                    <MethodBadge method={ep.method} />
                    <code className="text-[13px] font-medium text-graphite-950 dark:text-graphite-50">{ep.path}</code>
                    <span className="ml-auto text-[11px] text-graphite-500">{ep.auth}</span>
                  </div>
                  <p className="mt-2 text-[13px] text-graphite-600 dark:text-graphite-400">{ep.summary}</p>

                  {ep.params && (
                    <div className="mt-3">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Query params</p>
                      <ul className="mt-1.5 flex flex-col gap-0.5">
                        {ep.params.map((f) => (
                          <li key={f.name} className="font-mono text-[12px] text-graphite-700 dark:text-graphite-300">
                            <span className="text-graphite-950 dark:text-graphite-50">{f.name}</span> <span className="text-graphite-400">{f.type}</span>
                            {f.note && <span className="text-graphite-500"> -- {f.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {ep.body && (
                    <div className="mt-3">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Request body</p>
                      <ul className="mt-1.5 flex flex-col gap-0.5">
                        {ep.body.map((f) => (
                          <li key={f.name} className="font-mono text-[12px] text-graphite-700 dark:text-graphite-300">
                            <span className="text-graphite-950 dark:text-graphite-50">{f.name}</span>{f.type && <span className="text-graphite-400"> {f.type}</span>}
                            {f.note && <span className="text-graphite-500"> -- {f.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="mt-3">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Response</p>
                    <p className="mt-1 font-mono text-[12px] text-graphite-700 dark:text-graphite-300">{ep.response}</p>
                  </div>

                  {ep.example && (
                    <pre className="mt-3 overflow-x-auto rounded bg-graphite-950 p-3 font-mono text-[11.5px] leading-relaxed text-graphite-200">
                      {ep.example}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </Section>
        </div>
      ))}
    </>
  );
}
