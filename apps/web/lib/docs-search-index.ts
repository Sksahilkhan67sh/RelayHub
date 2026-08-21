import { MODULES } from "@/lib/api-modules-data";
import { COMMANDS } from "@/lib/cli-commands-data";
import { SDKS } from "@/lib/sdks-data";

export interface DocsSearchEntry {
  id: string;
  title: string;
  category: "Page" | "Guide" | "API" | "CLI" | "SDK";
  href: string;
  snippet: string;
}

/**
 * Guide-page sections, hand-listed once here rather than scraped, since these
 * pages are prose (JSX children), not data -- but every href below is a real
 * route or a real in-page anchor id already present in that page's source
 * (verified against each page.tsx), never an invented one.
 */
const GUIDE_ENTRIES: DocsSearchEntry[] = [
  { id: "page:developers", title: "Developers", category: "Page", href: "/developers", snippet: "Overview: API, SDK, CLI, and delivery infrastructure for RelayHub." },
  { id: "page:quickstart", title: "Quickstart", category: "Guide", href: "/developers/quickstart", snippet: "Create an account, an endpoint, and an API key, then publish and verify your first event." },
  { id: "anchor:quickstart-verify", title: "Verify the delivery on your side", category: "Guide", href: "/developers/quickstart#verify", snippet: "Verify a webhook signature so you know a request actually came from RelayHub." },
  { id: "page:concepts", title: "Concepts", category: "Guide", href: "/developers/concepts", snippet: "What happens after you publish: events, endpoints, deliveries, retries, DLQ, replay." },
  { id: "page:security", title: "Security", category: "Guide", href: "/developers/security", snippet: "Authentication, webhook signatures, SSRF protection, rate limiting, tenant isolation, response headers." },
  { id: "anchor:security-authentication", title: "Authentication", category: "Guide", href: "/developers/security#authentication", snippet: "How API keys and session tokens authenticate requests." },
  { id: "anchor:security-signatures", title: "Webhook signatures", category: "Guide", href: "/developers/security#signatures", snippet: "How RelayHub signs outgoing webhook payloads and how to verify them." },
  { id: "anchor:security-ssrf", title: "SSRF protection for destination URLs", category: "Guide", href: "/developers/security#ssrf", snippet: "How endpoint URLs are validated to prevent server-side request forgery." },
  { id: "anchor:security-rate-limiting", title: "Rate limiting", category: "Guide", href: "/developers/security#rate-limiting", snippet: "Request limits and the 429 response shape." },
  { id: "anchor:security-tenant-isolation", title: "Tenant isolation", category: "Guide", href: "/developers/security#tenant-isolation", snippet: "How organizations are isolated from one another." },
  { id: "anchor:security-headers", title: "Response headers", category: "Guide", href: "/developers/security#headers", snippet: "Security-relevant headers on RelayHub API responses." },
  { id: "page:retries", title: "Retries", category: "Guide", href: "/developers/retries", snippet: "The default retry schedule, per-endpoint overrides, and what actually gets retried." },
  { id: "page:dead-letter-queue", title: "Dead-letter queue", category: "Guide", href: "/developers/dead-letter-queue", snippet: "How a delivery lands in the DLQ, what you can inspect, permissions, and CSV export." },
  { id: "page:replay", title: "Replay", category: "Guide", href: "/developers/replay", snippet: "Retry one delivery or several at once, after fixing the downstream issue." },
  { id: "page:troubleshooting", title: "Troubleshooting", category: "Guide", href: "/developers/troubleshooting", snippet: "Webhook not delivered, 500s, 401/403, stuck retries, DLQ, API key and signature problems, rate limiting." },
  { id: "entry:troubleshooting-not-delivered", title: "Webhook not delivered", category: "Guide", href: "/developers/troubleshooting", snippet: "You published an event but never received the HTTP request at your endpoint." },
  { id: "entry:troubleshooting-500", title: "Endpoint returns 500", category: "Guide", href: "/developers/troubleshooting", snippet: "A delivery attempt shows error category transient_http_error with an HTTP 500 response." },
  { id: "entry:troubleshooting-401-403", title: "Endpoint returns 401 or 403", category: "Guide", href: "/developers/troubleshooting", snippet: "A delivery attempt fails with error category permanent_http_error and does not retry." },
  { id: "entry:troubleshooting-stuck-retrying", title: "Delivery stuck retrying", category: "Guide", href: "/developers/troubleshooting", snippet: "A job's status is retrying and attempt_number keeps climbing." },
  { id: "entry:troubleshooting-dlq", title: "Delivery moved to the dead-letter queue", category: "Guide", href: "/developers/troubleshooting", snippet: "Status is dead_letter, attempt_number equals max_attempts." },
  { id: "entry:troubleshooting-api-key-rejected", title: "API key rejected", category: "Guide", href: "/developers/troubleshooting", snippet: "401 with Invalid API key, or API key is revoked or expired." },
  { id: "entry:troubleshooting-missing-header", title: "Missing X-RelayHub-Api-Key header", category: "Guide", href: "/developers/troubleshooting", snippet: "401 with Missing X-RelayHub-Api-Key header." },
  { id: "entry:troubleshooting-invalid-signature", title: "Invalid signature on your end", category: "Guide", href: "/developers/troubleshooting", snippet: "Your own webhook handler rejects every delivery as unsigned or invalid." },
  { id: "entry:troubleshooting-rate-limited", title: "Rate limited", category: "Guide", href: "/developers/troubleshooting", snippet: "429 with rate_limited as the error code." },
  { id: "entry:troubleshooting-auth-failure", title: "Authentication failure calling the RelayHub API itself", category: "Guide", href: "/developers/troubleshooting", snippet: "401 on a dashboard-style call, not on event publishing." },
  { id: "page:api", title: "API Reference", category: "Page", href: "/developers/api", snippet: "Every RelayHub REST endpoint, verified against source." },
  { id: "page:sdks", title: "SDKs", category: "Page", href: "/developers/sdks", snippet: "Node.js, Python, Go, and Java clients for the RelayHub API." },
  { id: "page:cli", title: "CLI", category: "Page", href: "/developers/cli", snippet: "The relay command-line tool: installation, authentication, and every command." },
];

const API_ENTRIES: DocsSearchEntry[] = MODULES.flatMap((mod) => [
  { id: `api-mod:${mod.id}`, title: mod.title, category: "API" as const, href: `/developers/api#${mod.id}`, snippet: mod.intro },
  ...mod.endpoints.map((ep) => ({
    id: `api-ep:${mod.id}:${ep.method}:${ep.path}`,
    title: `${ep.method} ${ep.path}`,
    category: "API" as const,
    href: `/developers/api#${mod.id}`,
    snippet: ep.summary,
  })),
]);

const CLI_ENTRIES: DocsSearchEntry[] = COMMANDS.map((c) => ({
  id: `cli:${c.name}`,
  title: `relay ${c.name}`,
  category: "CLI" as const,
  href: "/developers/cli",
  snippet: c.note ?? c.usage,
}));

const SDK_ENTRIES: DocsSearchEntry[] = SDKS.map((s) => ({
  id: `sdk:${s.name}`,
  title: s.name,
  category: "SDK" as const,
  href: "/developers/sdks",
  snippet: s.install,
}));

export const DOCS_SEARCH_INDEX: DocsSearchEntry[] = [
  ...GUIDE_ENTRIES,
  ...API_ENTRIES,
  ...CLI_ENTRIES,
  ...SDK_ENTRIES,
];
