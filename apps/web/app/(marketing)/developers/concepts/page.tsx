import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Concepts — RelayHub Developers",
  description: "The core RelayHub concepts: organizations, API keys, events, endpoints, delivery jobs and attempts, retry policies, the DLQ, replay, signatures, and workers.",
  alternates: { canonical: "/developers/concepts" },
  openGraph: {
    title: "RelayHub Concepts",
    description: "Everything RelayHub is built from, in plain terms -- verified against the actual implementation.",
    url: "/developers/concepts",
    type: "article",
  },
};

const LIFECYCLE = ["Event", "Delivery Job", "Attempt", "Success", "(or) Retry -> DLQ -> Replay"];

const CONCEPTS: { id: string; title: string; body: React.ReactNode }[] = [
  {
    id: "organizations",
    title: "Organizations",
    body: (
      <>
        The multi-tenant boundary -- every event, endpoint, key, and delivery belongs to exactly one organization.
        Members hold one of four roles with a strict hierarchy: <code>owner</code> &gt; <code>admin</code> &gt;{" "}
        <code>member</code> &gt; <code>viewer</code>. Registering an account creates your first organization
        automatically.
      </>
    ),
  },
  {
    id: "api-keys",
    title: "API keys",
    body: (
      <>
        A scoped, environment-bound credential (<code>test</code> or <code>live</code>) for server-to-server calls --
        separate from the session token your dashboard login uses. The full key is shown exactly once at creation and
        can be revoked independently at any time without affecting other keys.
      </>
    ),
  },
  {
    id: "events",
    title: "Events",
    body: (
      <>
        A typed occurrence you publish once (<code>POST /v1/events</code>) with an event type string and an arbitrary
        JSON payload. RelayHub fans it out to every active endpoint subscribed to that type -- one event can produce
        several deliveries.
      </>
    ),
  },
  {
    id: "endpoints",
    title: "Endpoints",
    body: (
      <>
        A destination URL plus delivery configuration: which event types it receives, a request timeout, an optional
        IP allowlist, TLS verification, and a per-endpoint retry-attempt override. Endpoints belong to an
        environment, same as API keys.
      </>
    ),
  },
  {
    id: "delivery-jobs",
    title: "Delivery jobs",
    body: (
      <>
        The unit of tracking for one event going to one endpoint. A job carries a status (<code>queued</code>,{" "}
        <code>processing</code>, <code>retrying</code>, <code>success</code>, <code>failed</code>,{" "}
        <code>dead_letter</code>), a running attempt count, and the effective max attempts for that specific job.
      </>
    ),
  },
  {
    id: "delivery-attempts",
    title: "Delivery attempts",
    body: (
      <>
        One HTTP try within a job&apos;s lifetime -- recorded after it finishes, with the response status, latency,
        response body, and error category if it failed. A job with 3 failed tries followed by a success has 4 attempt
        records.
      </>
    ),
  },
  {
    id: "retry-policies",
    title: "Retry policies",
    body: (
      <>
        The default schedule is 5 total attempts: an immediate first try, then retries at 10s, 30s, 1m, and 5m (each
        with +/-20% jitter, so many simultaneously failing jobs don&apos;t retry in lockstep against a still-recovering
        endpoint). Any endpoint can override the max-attempts count individually.
      </>
    ),
  },
  {
    id: "delivery-logs",
    title: "Delivery logs",
    body: (
      <>
        A searchable history of every job across your organization (<code>GET /v1/logs</code>) -- filterable by
        status, event type, environment, endpoint, and request ID. This is what backs the dashboard&apos;s Logs and
        Deliveries pages.
      </>
    ),
  },
  {
    id: "dlq",
    title: "Dead-letter queue",
    body: (
      <>
        Where a job lands after exhausting every retry attempt without succeeding -- it doesn&apos;t just disappear.
        DLQ entries are listable, individually inspectable, exportable, and deletable via{" "}
        <code>/v1/dlq</code>.
      </>
    ),
  },
  {
    id: "replay",
    title: "Replay",
    body: (
      <>
        Once you&apos;ve fixed whatever caused the failure, re-queue a dead-lettered job as a fresh delivery attempt
        with <code>POST /v1/dlq/{"{id}"}/retry</code>, or replay several at once with{" "}
        <code>POST /v1/dlq/bulk-retry</code>.
      </>
    ),
  },
  {
    id: "signatures",
    title: "Webhook signatures",
    body: (
      <>
        Every delivery is signed: HMAC-SHA256 over <code>{"<timestamp>.<nonce>."}</code> concatenated with the raw
        request body, sent as <code>X-RelayHub-Signature</code> alongside <code>X-RelayHub-Timestamp</code> and{" "}
        <code>X-RelayHub-Nonce</code>. Signing the timestamp and nonce, not just the body, is what makes a captured
        request unusable for replay attacks.
      </>
    ),
  },
  {
    id: "workers",
    title: "Workers",
    body: (
      <>
        Delivery runs on Celery background workers, separate from the API process. <code>deliver_webhook</code>{" "}
        executes a single attempt for one job; <code>check_due_retries</code> runs on a schedule to find jobs whose
        retry time has arrived and re-queue them; <code>cleanup_expired_delivery_logs</code> handles log retention.
      </>
    ),
  },
];

export default function ConceptsPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Concepts</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
          The building blocks
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Twelve concepts cover everything RelayHub does. Each one maps directly to something real in the API -- no
          abstractions invented for the sake of a diagram.
        </p>
      </Section>

      <Section className="py-8">
        <SectionHeading eyebrow="Lifecycle" title="What happens after you publish" />
        <div className="mt-8 flex flex-wrap items-center gap-2">
          {LIFECYCLE.map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className="rounded-md border border-graphite-200 bg-white px-3 py-2 text-xs font-medium text-graphite-800 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-200">
                {step}
              </span>
              {i < LIFECYCLE.length - 1 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-graphite-300 dark:text-graphite-700" />}
            </div>
          ))}
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-16">
          <div className="grid gap-8 sm:grid-cols-2">
            {CONCEPTS.map((c) => (
              <div key={c.id} id={c.id} className="scroll-mt-20 rounded-md border border-graphite-100 bg-white p-5 dark:border-graphite-800 dark:bg-graphite-900">
                <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{c.title}</h2>
                <p className="mt-2 text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">{c.body}</p>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">Ready to see these in action?</p>
        <Link href="/developers/quickstart" className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
          Walk through the quickstart
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
