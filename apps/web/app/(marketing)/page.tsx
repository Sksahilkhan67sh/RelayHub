import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  RefreshCw,
  Inbox,
  BarChart3,
  Bell,
  ShieldCheck,
  Building2,
  ScrollText,
  Webhook,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusDot } from "@/components/ui/status-dot";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { RelayVisualization } from "@/components/marketing/relay-visualization";
import { FaqAccordion } from "@/components/marketing/faq-accordion";

export const metadata: Metadata = {
  title: "RelayHub — Webhook delivery infrastructure that doesn't drop events",
  description:
    "Send, retry, and observe every webhook your product fires. Signed deliveries, automatic retries, a real dead-letter queue, and full delivery logs -- built for teams who can't afford a silently missed event.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "RelayHub — Webhook delivery infrastructure that doesn't drop events",
    description: "Signed deliveries, automatic retries, dead-letter queue, and full delivery logs for event-driven products.",
    url: "/",
    type: "website",
  },
};

const TRUSTED_BY = ["Nordwave", "Fenwick Labs", "Basalt", "Heliogrid", "Harborline", "Halcyon Systems"];

const STEPS = [
  {
    n: "01",
    title: "You send an event",
    body: "One call to the events API -- checkout.completed, user.invited, whatever your product does. RelayHub takes it from there.",
  },
  {
    n: "02",
    title: "RelayHub delivers it",
    body: "Every subscribed endpoint gets a signed POST within milliseconds. Signatures use per-endpoint secrets, so recipients can verify authenticity before they trust the payload.",
  },
  {
    n: "03",
    title: "Failures retry automatically",
    body: "A non-2xx response schedules a retry with exponential backoff. You set the policy per endpoint; RelayHub enforces it.",
  },
  {
    n: "04",
    title: "Everything is observable",
    body: "Every attempt -- success or failure -- is logged with status, latency, and response body. Search it, replay it, or route it to the dead-letter queue.",
  },
];

const FEATURES = [
  { icon: Webhook, title: "Delivery engine", body: "Signed, ordered, at-least-once delivery to every subscribed endpoint." },
  { icon: RefreshCw, title: "Retry engine", body: "Configurable exponential backoff per endpoint, with a hard cap you control." },
  { icon: Inbox, title: "Dead-letter queue", body: "Exhausted deliveries land in a real DLQ you can inspect and replay, not a void." },
  { icon: BarChart3, title: "Analytics", body: "Delivery volume, latency percentiles, and failure rate, broken down by endpoint." },
  { icon: Bell, title: "Alerts", body: "Get paged in Slack, Discord, or email when an endpoint's failure rate spikes." },
  { icon: ShieldCheck, title: "RBAC & audit logs", body: "Owner, admin, member, and viewer roles, with every sensitive action logged." },
  { icon: Building2, title: "Multi-tenancy", body: "Hard tenant isolation at the database layer -- one org's data never leaks into another's." },
  { icon: ScrollText, title: "Delivery logs", body: "Full-text, filterable logs across endpoint, status, environment, and time range." },
];

const TESTIMONIALS = [
  {
    quote:
      "We used to lose maybe one webhook a week to a flaky partner endpoint and never know it happened. RelayHub's retry engine and DLQ mean we find out the same day, not from a support ticket a month later.",
    name: "Priya Ramanathan",
    role: "Staff Engineer, Nordwave",
  },
  {
    quote:
      "The delivery logs are the whole product for us. Being able to search by request ID and see every retry attempt, latency included, cut our webhook-debugging time to almost nothing.",
    name: "Tobias Ahn",
    role: "Founding Engineer, Fenwick Labs",
  },
  {
    quote:
      "Migrating off a hand-rolled retry queue was the best infra decision we made this year. RBAC and audit logs meant we could hand webhook management to support without giving up control.",
    name: "Marguerite Okonkwo",
    role: "VP Engineering, Basalt",
  },
];

const FAQS = [
  {
    q: "How is RelayHub different from rolling our own webhook sender?",
    a: "Most hand-rolled senders handle the happy path fine and quietly fail on the rest: no backoff policy, no DLQ, no per-attempt logs. RelayHub is built around the failure cases -- retries, dead-lettering, replay, and full observability -- because that's where webhook reliability actually breaks down.",
  },
  {
    q: "Do you support multiple environments per organization?",
    a: "Yes. Endpoints, events, and delivery logs are all scoped by environment, so your staging traffic never mixes with production.",
  },
  {
    q: "How are deliveries authenticated?",
    a: "Every delivery is signed with a per-endpoint secret using HMAC. Your endpoint verifies the signature before trusting the payload, the same pattern used by Stripe and GitHub webhooks.",
  },
  {
    q: "What happens when an endpoint is down for an extended period?",
    a: "Deliveries retry on a backoff schedule you configure per endpoint. Once the retry budget is exhausted, the delivery moves to the dead-letter queue, where you can inspect it and replay it manually once the endpoint is back.",
  },
  {
    q: "Can I try RelayHub without talking to sales?",
    a: "Yes -- the Free plan covers a full working setup with no time limit. Pro and Enterprise plans add higher volume, longer retention, and SSO; see Pricing for details.",
  },
];

export default function LandingPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "RelayHub",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Web",
    description: "Webhook and event delivery infrastructure with signed deliveries, automatic retries, a dead-letter queue, and full delivery logs.",
    // Reflects the real Free/Starter/Pro tiers (components/marketing/pricing-client.tsx,
    // sourced from backend/app/modules/billing/service.py PLAN_DEFAULTS). Enterprise is
    // custom-quoted and excluded rather than assigned a fabricated number.
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "USD",
      lowPrice: "0",
      highPrice: "99",
      offerCount: "3",
    },
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {/* Hero */}
      <div className="relative overflow-hidden bg-graphite-950">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-signal-amber/10 blur-3xl"
          style={{ animation: "relay-drift 14s ease-in-out infinite" }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -right-16 h-96 w-96 rounded-full bg-signal-green/10 blur-3xl"
          style={{ animation: "relay-drift 18s ease-in-out infinite reverse" }}
        />

        <Section className="relative py-24 sm:py-28">
          <div className="grid items-center gap-14 lg:grid-cols-[1fr_1fr]">
            <div className="flex flex-col gap-6">
              <Eyebrow>Webhook &amp; event delivery infrastructure</Eyebrow>
              <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-white sm:text-5xl">
                Every event you send, delivered — or you&apos;ll know exactly why not.
              </h1>
              <p className="max-w-xl text-[15px] leading-relaxed text-graphite-400">
                RelayHub sends your webhooks with signed payloads, retries failures on a backoff schedule you set, and logs
                every single attempt. No more guessing whether a partner&apos;s endpoint actually got the event.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Link href="/register">
                  <Button size="md">
                    Start free
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
                <Link href="/docs">
                  <Button variant="secondary" size="md">
                    Read the docs
                  </Button>
                </Link>
              </div>
              <p className="font-mono text-xs text-graphite-600">No credit card required · Free plan available forever</p>
            </div>

            <RelayVisualization />
          </div>
        </Section>
      </div>

      {/* Trusted by */}
      <div className="border-b border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <div className="mx-auto max-w-6xl px-5 py-10">
          <p className="text-center text-xs font-medium uppercase tracking-wide text-graphite-500">
            Trusted by engineering teams shipping event-driven products
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {TRUSTED_BY.map((name) => (
              <span key={name} className="text-sm font-semibold tracking-tight text-graphite-400 dark:text-graphite-600">
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* How it works */}
      <Section>
        <SectionHeading eyebrow="How it works" title="From event to delivery in four steps" />
        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <div key={step.n} className="flex flex-col gap-2.5">
              <span className="font-mono text-xs text-signal-amber">{step.n}</span>
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{step.title}</h3>
              <p className="text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{step.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Product preview */}
      <div className="bg-graphite-50 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading
            eyebrow="See it in action"
            title="Delivery logs you can actually search"
            description="Every attempt is filterable by endpoint, status, event type, environment, request ID, and latency -- not a raw event feed you have to grep."
          />
          <div className="mt-10 overflow-hidden rounded-md border border-graphite-100 bg-white shadow-card dark:border-graphite-800 dark:bg-graphite-900">
            <div className="flex items-center gap-1.5 border-b border-graphite-100 px-4 py-2.5 dark:border-graphite-800">
              <span className="h-2.5 w-2.5 rounded-full bg-signal-red/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-signal-amber/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-signal-green/60" />
              <span className="ml-3 font-mono text-[11px] text-graphite-400">relayhub.app/logs</span>
            </div>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Event</th>
                  <th className="px-4 py-2 font-medium">Endpoint</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Latency</th>
                  <th className="px-4 py-2 font-medium">Attempt</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {[
                  { event: "checkout.completed", endpoint: "api.nordwave.io", status: "green" as const, label: "success", latency: "142ms", attempt: "1/5" },
                  { event: "invoice.paid", endpoint: "hooks.fenwick.dev", status: "amber" as const, label: "retrying", latency: "—", attempt: "2/5" },
                  { event: "user.invited", endpoint: "svc.basalt.app", status: "green" as const, label: "success", latency: "88ms", attempt: "1/5" },
                  { event: "payout.failed", endpoint: "svc.basalt.app", status: "red" as const, label: "dead_letter", latency: "—", attempt: "5/5" },
                ].map((row) => (
                  <tr key={row.event} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 text-graphite-950 dark:text-graphite-50">{row.event}</td>
                    <td className="px-4 py-2.5 text-graphite-500">{row.endpoint}</td>
                    <td className="px-4 py-2.5">
                      <StatusDot color={row.status} label={row.label} />
                    </td>
                    <td className="px-4 py-2.5 text-graphite-500">{row.latency}</td>
                    <td className="px-4 py-2.5 text-graphite-500">{row.attempt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-graphite-400">A representative view of the delivery log explorer inside the RelayHub dashboard.</p>
        </Section>
      </div>

      {/* Features grid */}
      <Section>
        <SectionHeading
          eyebrow="Everything included"
          title="Built around the failure cases, not just the happy path"
          description="Retries, dead-lettering, and full observability aren't add-ons -- they're the reason RelayHub exists."
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="flex flex-col gap-3 rounded-md border border-graphite-100 p-5 dark:border-graphite-800">
              <f.icon className="h-4 w-4 text-signal-amber" />
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{f.title}</h3>
              <p className="text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{f.body}</p>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <Link href="/features" className="inline-flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
            See every feature in detail
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </Section>

      {/* Developer experience */}
      <div className="bg-graphite-950">
        <Section className="py-20">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div className="flex flex-col gap-4">
              <Eyebrow>Developer experience</Eyebrow>
              <h2 className="text-3xl font-semibold tracking-tight text-white">Verify a delivery in four lines</h2>
              <p className="text-[15px] leading-relaxed text-graphite-400">
                Every delivery is signed with HMAC-SHA256 using a per-endpoint secret. Verify it before you trust the
                payload -- the same pattern Stripe and GitHub use for their own webhooks.
              </p>
              <ul className="mt-1 flex flex-col gap-2 text-[13px] text-graphite-400">
                <li className="flex gap-2">
                  <span className="text-signal-amber">→</span> One signing secret per endpoint, rotatable anytime
                </li>
                <li className="flex gap-2">
                  <span className="text-signal-amber">→</span> Timestamp included to reject replayed requests
                </li>
                <li className="flex gap-2">
                  <span className="text-signal-amber">→</span> Works with any language that can compute HMAC-SHA256
                </li>
              </ul>
            </div>
            <div className="overflow-hidden rounded-md border border-graphite-800 bg-graphite-900">
              <div className="border-b border-graphite-800 px-4 py-2.5 font-mono text-[11px] text-graphite-500">verify.js</div>
              <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-graphite-200">
{`import { createHmac, timingSafeEqual } from "crypto";

// rawBody must be the exact bytes RelayHub sent (e.g. a Buffer from your
// framework's raw-body middleware) -- re-serializing parsed JSON can shift
// whitespace/key order and silently break verification.
function isValid(rawBody, headers, secret) {
  const signature = headers["x-relayhub-signature"];
  const timestamp = headers["x-relayhub-timestamp"];
  const nonce = headers["x-relayhub-nonce"];

  const signedString = \`\${timestamp}.\${nonce}.\` + rawBody;
  const expected = createHmac("sha256", secret)
    .update(signedString)
    .digest("hex");

  return timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}`}
              </pre>
            </div>
          </div>
        </Section>
      </div>

      {/* Enterprise */}
      <Section>
        <SectionHeading eyebrow="Enterprise" title="The controls a growing platform team actually needs" />
        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {[
            { title: "Role-based access control", body: "Owner, admin, member, and viewer roles scoped to the organization -- not a single shared API key." },
            { title: "Full audit logging", body: "Every membership change, API key creation, and settings update is recorded with actor, time, and IP." },
            { title: "Hard tenant isolation", body: "Every query is scoped at the database layer by organization -- there is no code path that crosses tenants." },
          ].map((item) => (
            <div key={item.title} className="rounded-md border border-graphite-100 p-5 dark:border-graphite-800">
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{item.title}</h3>
              <p className="mt-2 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{item.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Testimonials */}
      <div className="bg-graphite-50 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Teams on RelayHub" title="What engineering teams say after switching" align="center" />
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="flex flex-col justify-between rounded-md border border-graphite-100 bg-white p-6 dark:border-graphite-800 dark:bg-graphite-900">
                <p className="text-[13.5px] leading-relaxed text-graphite-700 dark:text-graphite-300">&ldquo;{t.quote}&rdquo;</p>
                <div className="mt-5 flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-signal-amber text-xs font-semibold text-white">
                    {t.name[0]}
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-graphite-950 dark:text-graphite-50">{t.name}</p>
                    <p className="text-[11px] text-graphite-500">{t.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* FAQ */}
      <Section className="max-w-3xl">
        <SectionHeading eyebrow="FAQ" title="Common questions" align="center" />
        <div className="mt-10">
          <FaqAccordion items={FAQS} />
        </div>
      </Section>

      {/* Final CTA */}
      <div className="border-t border-graphite-800 bg-graphite-950">
        <Section className="flex flex-col items-center gap-5 py-20 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Stop finding out about missed webhooks from support tickets.</h2>
          <p className="max-w-lg text-[15px] text-graphite-400">Set up your first endpoint in a few minutes. The free plan has no time limit.</p>
          <Link href="/register">
            <Button size="md">
              Start free
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </Section>
      </div>
    </>
  );
}
