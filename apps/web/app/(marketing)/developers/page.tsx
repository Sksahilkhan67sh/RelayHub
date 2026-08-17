import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Zap,
  RefreshCw,
  ScrollText,
  ListChecks,
  Inbox,
  RotateCcw,
  Webhook,
  Package,
  Terminal,
  KeyRound,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Developers — RelayHub",
  description:
    "Build reliable webhook infrastructure with RelayHub: a REST API, a published Node.js SDK, delivery logs, automatic retries, and a dead-letter queue with replay.",
  alternates: { canonical: "/developers" },
  openGraph: {
    title: "RelayHub Developers",
    description: "The webhook API, SDK, and delivery infrastructure docs for building reliable event delivery.",
    url: "/developers",
    type: "website",
  },
};

const ARCHITECTURE_STEPS = [
  "Your application",
  "RelayHub API",
  "Event",
  "Webhook endpoint(s)",
  "Delivery attempt",
  "Retry / DLQ / Replay",
];

const CAPABILITIES = [
  { icon: Zap, title: "Event delivery", body: "Publish a typed event once; RelayHub fans it out, signed, to every endpoint subscribed to that event type." },
  { icon: RefreshCw, title: "Retries", body: "A non-2xx response or timeout schedules a retry on exponential backoff, up to a configurable max per endpoint." },
  { icon: ScrollText, title: "Delivery logs", body: "Every attempt is recorded -- status, latency, response body -- searchable by request ID, status, and endpoint." },
  { icon: ListChecks, title: "Attempt tracking", body: "See exactly which attempt you're on, how many remain, and when the next retry is scheduled, in real time." },
  { icon: Inbox, title: "Dead-letter queue", body: "A delivery that exhausts its retry budget lands in the DLQ instead of disappearing -- inspect it, don't lose it." },
  { icon: RotateCcw, title: "Replay", body: "Fix the downstream issue, then replay any past delivery -- from the log or the DLQ -- as a fresh attempt." },
  { icon: Webhook, title: "REST API", body: "Every capability in the dashboard is also a documented HTTP endpoint -- events, endpoints, deliveries, DLQ, analytics." },
  { icon: Package, title: "Node.js SDK", body: "A typed client on npm (relayhub-sdk) wrapping the full API with automatic retries on 429/5xx." },
  { icon: Terminal, title: "CLI", body: "A command-line tool for endpoints, publishing, deliveries, replay, and DLQ management, run from source today." },
  { icon: KeyRound, title: "Authentication", body: "Scoped API keys for programmatic access, shown once at creation and revocable independently at any time." },
  { icon: BarChart3, title: "Analytics", body: "Delivery volume, latency percentiles (p50/p95/p99), and failure rate per endpoint, over a configurable window." },
];

const CODE_EXAMPLE = `import { RelayHubClient } from "relayhub-sdk";

const client = new RelayHubClient({ apiKey: process.env.RELAYHUB_API_KEY! });

await client.events.publish({
  event: "checkout.completed",
  payload: { orderId: "ord_123", amount: 4200 },
  environment: "live",
});`;

export default function DevelopersPage() {
  return (
    <>
      <div className="relative overflow-hidden bg-graphite-950">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-signal-amber/10 blur-3xl"
        />
        <Section className="relative py-24 sm:py-28">
          <div className="mx-auto max-w-2xl text-center">
            <Eyebrow>Developers</Eyebrow>
            <h1 className="mt-3 text-4xl font-semibold leading-[1.1] tracking-tight text-white sm:text-5xl">
              Build reliable webhook infrastructure with RelayHub.
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-graphite-400">
              One API call publishes an event. RelayHub signs it, delivers it to every subscribed endpoint, retries
              failures on a schedule you control, and gives you a real dead-letter queue instead of a silently dropped
              webhook.
            </p>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
              <Link href="/register">
                <Button size="md">
                  Get Started
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
              <Link href="/docs">
                <Button variant="secondary" size="md">
                  Read Documentation
                </Button>
              </Link>
            </div>
          </div>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Architecture" title="How an event becomes a delivery" />
        <div className="mt-10 flex flex-wrap items-center justify-center gap-2">
          {ARCHITECTURE_STEPS.map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className="rounded-md border border-graphite-200 bg-white px-3 py-2 text-xs font-medium text-graphite-800 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-200">
                {step}
              </span>
              {i < ARCHITECTURE_STEPS.length - 1 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-graphite-300 dark:text-graphite-700" />}
            </div>
          ))}
        </div>
        <Link href="/developers/concepts" className="mt-6 flex w-fit items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
          See every concept in detail
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Capabilities" title="What RelayHub actually gives you" />
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((c) => (
              <div key={c.title} className="rounded-md border border-graphite-100 bg-white p-5 dark:border-graphite-800 dark:bg-graphite-900">
                <c.icon className="h-4 w-4 text-signal-amber" />
                <h3 className="mt-3 text-sm font-semibold text-graphite-950 dark:text-graphite-50">{c.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{c.body}</p>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Quick look" title="Publish your first event" />
        <div className="mt-8 grid gap-8 lg:grid-cols-2 lg:items-center">
          <div className="flex flex-col gap-4">
            <p className="text-[14.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              This is the entire integration for the common case: publish an event with the Node.js SDK, and RelayHub
              handles signing, delivery, retries, and logging for every endpoint subscribed to it. The same call is one
              HTTP request if you&apos;re not using Node -- see the{" "}
              <Link href="/docs#events" className="text-signal-amber hover:underline">Events</Link> section of the docs
              for the raw REST shape.
            </p>
            <Link href="/developers/quickstart" className="flex w-fit items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
              Walk through the full 5-minute quickstart
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="overflow-hidden rounded-md border border-graphite-800 bg-graphite-950">
            <div className="flex items-center justify-between border-b border-graphite-800 px-4 py-2">
              <span className="font-mono text-[11px] text-graphite-500">Node.js</span>
            </div>
            <pre className="overflow-x-auto p-4 font-mono text-[12px] leading-relaxed text-graphite-200">{CODE_EXAMPLE}</pre>
          </div>
        </div>
      </Section>

      <Section className="flex flex-col items-center gap-4 pb-24 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-graphite-950 dark:text-graphite-50">Ready to build?</h2>
        <p className="max-w-md text-[13.5px] text-graphite-600 dark:text-graphite-400">
          Create an account, generate an API key, and publish your first event in a few minutes.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link href="/register">
            <Button size="md">
              Create Your First Endpoint
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
          <Link href="/docs">
            <Button variant="secondary" size="md">
              Browse the docs
            </Button>
          </Link>
        </div>
      </Section>
    </>
  );
}
