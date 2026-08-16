"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/card";
import { cn } from "@/lib/cn";

interface DocSection {
  id: string;
  title: string;
  keywords: string;
  body: React.ReactNode;
  status?: "coming-soon";
}

const SECTIONS: DocSection[] = [
  {
    id: "getting-started",
    title: "Getting started",
    keywords: "getting started organization endpoint publish event sign up create first",
    body: (
      <>
        <p>
          Create an organization from <Link href="/register" className="text-signal-amber hover:underline">the sign-up page</Link>, then create your
          first endpoint from the dashboard&apos;s Endpoints page -- an endpoint is just a URL you want events delivered to.
        </p>
        <p>
          Once an endpoint exists, publish an event from the Events page or via the API, and RelayHub delivers it to every
          endpoint subscribed to that event type. Watch the delivery land in the Logs page in real time.
        </p>
      </>
    ),
  },
  {
    id: "authentication",
    title: "Authentication",
    keywords: "authentication login access token refresh api key password reset",
    body: (
      <>
        <p>
          The dashboard uses short-lived access tokens with a separate refresh token, issued at <code>/v1/auth/login</code>{" "}
          and renewed at <code>/v1/auth/refresh</code>. Programmatic access (publishing events, managing endpoints from a
          script) uses an API key instead -- see API Keys below.
        </p>
        <p>Forgot your password? Use the reset flow from the login page -- reset links expire and can only be used once.</p>
      </>
    ),
  },
  {
    id: "api-keys",
    title: "API keys",
    keywords: "api keys create revoke hash scoped permissions",
    body: (
      <>
        <p>
          Create an API key from Settings → API Keys. The full key is shown exactly once at creation time -- RelayHub only
          stores a hash of it, the same way it stores signing secrets, so keep it somewhere safe.
        </p>
        <p>Each key can be scoped to specific permissions and revoked independently at any time without affecting other keys.</p>
      </>
    ),
  },
  {
    id: "events",
    title: "Events",
    keywords: "events publish payload environment fan out subscribed",
    body: (
      <>
        <p>
          An event is a typed payload -- <code>checkout.completed</code>, <code>user.invited</code>, whatever your product
          does -- published to a specific environment. RelayHub fans it out to every endpoint subscribed to that event type
          in that environment.
        </p>
        <p>Every published event is retained and viewable from the Events page, along with the delivery jobs it produced.</p>
      </>
    ),
  },
  {
    id: "endpoints",
    title: "Endpoints",
    keywords: "endpoints url subscription headers timeout retry allowlist pause health",
    body: (
      <>
        <p>
          An endpoint is a URL plus configuration: which event types it&apos;s subscribed to, custom headers, timeout,
          max retry attempts, and an optional IP allowlist. Endpoints can be paused without deleting them.
        </p>
        <p>
          Each endpoint tracks its own health: consecutive failure count, last success, and last failure -- visible at a
          glance from the Endpoints list.
        </p>
      </>
    ),
  },
  {
    id: "webhooks",
    title: "Webhooks",
    keywords: "webhooks signature hmac sha256 verify signing secret rotate",
    body: (
      <>
        <p>
          Every delivery to your endpoint is a signed HTTP POST. Verify the <code>X-RelayHub-Signature</code> header with
          HMAC-SHA256 against your endpoint&apos;s signing secret before trusting the payload -- see the code sample on the{" "}
          <Link href="/#developer-experience" className="text-signal-amber hover:underline">homepage</Link>.
        </p>
        <p>Signing secrets can be rotated from the endpoint&apos;s settings without any delivery downtime.</p>
      </>
    ),
  },
  {
    id: "retries",
    title: "Retries",
    keywords: "retries backoff exponential attempts non-2xx timeout",
    body: (
      <>
        <p>
          A non-2xx response (or a timeout) schedules a retry on an exponential backoff schedule, up to the endpoint&apos;s
          configured maximum attempts. Each attempt is logged independently.
        </p>
        <p>You don&apos;t need to build retry logic on your end -- RelayHub owns the schedule and the attempt history.</p>
      </>
    ),
  },
  {
    id: "replay",
    title: "Replay",
    keywords: "replay resend deliver again dead letter queue log",
    body: (
      <>
        <p>
          Any past delivery -- from the log or the dead-letter queue -- can be replayed on demand. Replaying sends the
          original payload again as a fresh attempt; it doesn&apos;t re-trigger the event elsewhere in your system.
        </p>
      </>
    ),
  },
  {
    id: "dlq",
    title: "Dead-letter queue",
    keywords: "dead letter queue exhausted failure inspect replay",
    body: (
      <>
        <p>
          Once a delivery exhausts its retry budget, it moves to the dead-letter queue instead of disappearing. Inspect the
          full payload and failure history, and replay it once the downstream issue is resolved.
        </p>
      </>
    ),
  },
  {
    id: "analytics",
    title: "Analytics",
    keywords: "analytics volume latency percentile p50 p95 p99 failure rate",
    body: (
      <>
        <p>
          The Analytics page shows delivery volume, latency percentiles (p50/p95/p99), and failure rate per endpoint over a
          configurable time window, so a degrading integration shows up before it becomes an incident.
        </p>
      </>
    ),
  },
  {
    id: "billing",
    title: "Billing",
    keywords: "billing plan subscription limit upgrade overage cycle",
    body: (
      <>
        <p>
          Your organization&apos;s plan controls delivery volume, endpoint count, and log retention -- see{" "}
          <Link href="/pricing" className="text-signal-amber hover:underline">Pricing</Link> for the full breakdown. Manage
          your subscription from Settings → Billing.
        </p>
        <p>If you hit your plan&apos;s delivery limit, new deliveries pause until you upgrade or the next cycle starts -- there&apos;s no surprise overage bill.</p>
      </>
    ),
  },
  {
    id: "sdks",
    title: "SDKs",
    keywords: "sdks node python go java typed client library rest api install",
    body: (
      <>
        <p>
          The Node.js SDK is published and installable today:{" "}
          <code>npm install relayhub-sdk</code>. It wraps the full REST API -- events, endpoints, deliveries, DLQ,
          analytics, billing, notifications -- in a typed client with automatic retries on 429/5xx.
        </p>
        <p>
          Python, Go, and Java SDKs exist in the repository with the same API surface and are fully tested, but aren&apos;t
          published to their package registries yet (PyPI, a versioned Go module release, and Maven Central respectively).
          Until then, the REST API works with any HTTP client in any language.
        </p>
      </>
    ),
  },
  {
    id: "cli",
    title: "CLI",
    keywords: "cli command line terminal endpoints publish deliveries replay dlq",
    body: (
      <>
        <p>
          A command-line tool (<code>relay</code>) exists in the repository, covering endpoints, publishing events,
          searching deliveries, replaying dead-lettered jobs, DLQ management, analytics, billing, and alert rules --
          run <code>relay --help</code> for the full command list once you have it checked out.
        </p>
        <p>It isn&apos;t published to npm yet, so for now it&apos;s built and run from source rather than installed globally.</p>
      </>
    ),
  },
];

export function DocsClient() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return SECTIONS;
    return SECTIONS.filter((s) => s.title.toLowerCase().includes(q) || s.keywords.includes(q));
  }, [query]);

  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 lg:grid-cols-[220px_1fr]">
      <aside className="lg:sticky lg:top-20 lg:h-fit">
        <div className="relative mb-4">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-graphite-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search docs"
            aria-label="Search documentation"
            className="h-9 w-full rounded border border-graphite-200 bg-white pl-8 pr-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
          />
        </div>
        <nav className="flex flex-col gap-0.5" aria-label="Documentation sections">
          {filtered.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="flex items-center justify-between rounded px-2.5 py-1.5 text-xs text-graphite-600 hover:bg-graphite-50 hover:text-graphite-950 dark:text-graphite-400 dark:hover:bg-graphite-800 dark:hover:text-graphite-50"
            >
              {s.title}
              {s.status === "coming-soon" && <span className="h-1.5 w-1.5 rounded-full bg-signal-amber" />}
            </a>
          ))}
          {filtered.length === 0 && <p className="px-2.5 py-1.5 text-xs text-graphite-400">No matching topics.</p>}
        </nav>
      </aside>

      <div className="flex flex-col gap-12">
        {filtered.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24 border-b border-graphite-100 pb-10 last:border-0 dark:border-graphite-800">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">{s.title}</h2>
              {s.status === "coming-soon" && <Badge tone="amber">Coming soon</Badge>}
            </div>
            <div className={cn("mt-3 flex flex-col gap-3 text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400", "[&_code]:rounded [&_code]:bg-graphite-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-graphite-800 dark:[&_code]:bg-graphite-800 dark:[&_code]:text-graphite-200")}>
              {s.body}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
