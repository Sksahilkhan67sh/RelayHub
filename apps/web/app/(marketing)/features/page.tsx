import type { Metadata } from "next";
import Link from "next/link";
import {
  Webhook,
  RefreshCw,
  RotateCcw,
  Inbox,
  Eye,
  BarChart3,
  Bell,
  Building2,
  ShieldCheck,
  ScrollText,
  Lock,
  Sparkles,
  Package,
  Gauge,
  Server,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Features — RelayHub",
  description: "Every capability in RelayHub's webhook and event delivery platform: delivery, retries, replay, DLQ, observability, security, and more.",
  alternates: { canonical: "/features" },
  openGraph: { title: "Features — RelayHub", description: "Delivery, retries, replay, DLQ, observability, and security for event-driven products.", url: "/features" },
};

interface FeatureSection {
  icon: typeof Webhook;
  title: string;
  body: string;
  bullets: string[];
  status?: "shipping" | "coming-soon";
}

const SECTIONS: FeatureSection[] = [
  {
    icon: Webhook,
    title: "Delivery engine",
    body: "The core of RelayHub: every event you publish is delivered as a signed HTTP POST to each endpoint subscribed to that event type, with the response status and body captured for every attempt.",
    bullets: ["HMAC-SHA256 signed payloads, per-endpoint secrets", "Custom headers and per-endpoint timeout configuration", "IP allowlisting and TLS verification toggles per endpoint"],
  },
  {
    icon: RefreshCw,
    title: "Retry engine",
    body: "A failed delivery isn't a dropped delivery. RelayHub schedules a retry on exponential backoff, up to a maximum attempt count you set per endpoint.",
    bullets: ["Configurable max retry attempts per endpoint", "Exponential backoff schedule, not a fixed interval", "Retry status visible in the delivery log for every attempt"],
  },
  {
    icon: RotateCcw,
    title: "Replay",
    body: "Fixed the bug that was rejecting a webhook? Replay any past delivery -- from the log or from the dead-letter queue -- without re-triggering the original event in the rest of your system.",
    bullets: ["Replay a single delivery or a filtered batch", "Original payload and headers are preserved exactly", "Replays are logged as new attempts, not silently retried"],
  },
  {
    icon: Inbox,
    title: "Dead-letter queue",
    body: "When an endpoint exhausts its retry budget, the delivery lands in a real, inspectable dead-letter queue instead of disappearing.",
    bullets: ["Full payload and failure history retained", "Filter by endpoint, event type, and failure reason", "One-click replay once the downstream issue is fixed"],
  },
  {
    icon: Eye,
    title: "Observability",
    body: "A delivery you can't see is a delivery you can't trust. Every attempt -- success, retry, or failure -- is logged with status, latency, worker, and request ID.",
    bullets: ["Full-text, filterable delivery log explorer", "Search by request ID, endpoint, status, or date range", "Retention scoped per organization's billing plan"],
  },
  {
    icon: BarChart3,
    title: "Analytics",
    body: "Delivery volume, latency percentiles, and failure rate, broken down by endpoint and time window -- so you notice a degrading integration before your partner does.",
    bullets: ["p50/p95/p99 latency per endpoint", "Failure-rate trend lines with configurable windows", "Exportable for your own dashboards"],
  },
  {
    icon: Bell,
    title: "Alerts",
    body: "Get notified the moment an endpoint's failure rate crosses a threshold you define, through the channel your team already watches.",
    bullets: ["Slack, Discord, webhook, and email channels", "Per-rule throttle window to avoid alert storms", "Alert history so you can confirm a rule actually fired"],
  },
  {
    icon: Building2,
    title: "Multi-tenancy",
    body: "Every table, every query, every background job is scoped by organization at the database layer. There is no code path where one tenant's data can leak into another's.",
    bullets: ["Environment scoping within each organization", "Per-organization rate limits and quota", "Independent billing and plan tier per organization"],
  },
  {
    icon: Lock,
    title: "Security",
    body: "Signed deliveries, hashed and encrypted secrets at rest, and a login path hardened against brute force -- security isn't a checkbox feature here, it's load-bearing.",
    bullets: ["Per-endpoint signing secrets, rotatable anytime", "Rate-limited auth endpoints with account lockout", "One-time-use, hashed password-reset and invite tokens"],
  },
  {
    icon: ScrollText,
    title: "Audit logs",
    body: "Every membership change, API key creation, role update, and settings change is recorded with actor, timestamp, and IP address -- queryable from your organization settings.",
    bullets: ["Immutable log of sensitive account actions", "Filterable by actor, action type, and date", "Retained per your organization's billing plan"],
  },
  {
    icon: ShieldCheck,
    title: "RBAC",
    body: "Four roles -- owner, admin, member, viewer -- so you can hand a teammate read access to delivery logs without handing them the ability to rotate a signing secret.",
    bullets: ["Role enforced on every API route, not just the UI", "Invite by email at a specific role", "Role changes are themselves audit-logged"],
  },
  {
    icon: Gauge,
    title: "Performance",
    body: "Delivery latency and retry scheduling run on a dedicated queue, separate from the API request path, so a burst of events never slows down the dashboard or the API.",
    bullets: ["Asynchronous delivery execution, not request-blocking", "Independently scalable delivery workers", "Rate limiting protects both your account and the platform"],
  },
  {
    icon: Server,
    title: "Enterprise",
    body: "The controls a platform team needs once webhooks stop being a side feature and start being infrastructure other teams depend on.",
    bullets: ["Organization-level admin panel and feature-flag overrides", "Dedicated support channel on Enterprise plans", "Custom retention and rate-limit tiers on request"],
  },
  {
    icon: Sparkles,
    title: "AI Copilot",
    body: "An assistant that can explain a failing delivery, suggest a retry policy, or draft an alert rule from a plain-language description.",
    bullets: ["Not yet available", "On the roadmap -- see the Changelog for progress"],
    status: "coming-soon",
  },
  {
    icon: Package,
    title: "SDKs",
    body: "Typed client libraries for publishing events and verifying signatures without hand-writing the HTTP calls.",
    bullets: ["Not yet available -- the REST API is fully documented today", "Node.js and Python are first on the roadmap"],
    status: "coming-soon",
  },
];

export default function FeaturesPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <div className="max-w-2xl">
          <Eyebrow>Features</Eyebrow>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
            Everything RelayHub does, in detail
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            RelayHub is built around the parts of webhook delivery that are easy to skip and expensive to skip: retries,
            dead-lettering, and knowing exactly what happened on every attempt.
          </p>
        </div>
      </Section>

      <Section className="pt-0">
        <div className="grid gap-px overflow-hidden rounded-md border border-graphite-100 bg-graphite-100 sm:grid-cols-2 dark:border-graphite-800 dark:bg-graphite-800">
          {SECTIONS.map((s) => (
            <div key={s.title} id={s.title.toLowerCase().replace(/\s+/g, "-")} className="flex flex-col gap-3 bg-white p-6 dark:bg-graphite-950">
              <div className="flex items-center justify-between">
                <s.icon className="h-4 w-4 text-signal-amber" />
                {s.status === "coming-soon" && <Badge tone="amber">Coming soon</Badge>}
              </div>
              <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{s.title}</h2>
              <p className="text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{s.body}</p>
              <ul className="mt-1 flex flex-col gap-1.5">
                {s.bullets.map((b) => (
                  <li key={b} className="flex gap-2 text-xs text-graphite-500">
                    <span className="text-signal-amber">·</span>
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="flex flex-col items-center gap-4 py-16 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-graphite-950 dark:text-graphite-50">Ready to see it running on your events?</h2>
          <div className="flex gap-3">
            <Link href="/register">
              <Button size="md">
                Start free
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button variant="secondary" size="md">
                View pricing
              </Button>
            </Link>
          </div>
        </Section>
      </div>
    </>
  );
}
