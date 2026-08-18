import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Troubleshooting — RelayHub Developers",
  description: "Practical fixes for real RelayHub failure modes: undelivered webhooks, endpoint errors, retries, the DLQ, API key rejection, signature failures, and rate limiting.",
  alternates: { canonical: "/developers/troubleshooting" },
  openGraph: {
    title: "RelayHub Troubleshooting",
    description: "What each real error actually means and how to fix it -- grounded in the actual implementation.",
    url: "/developers/troubleshooting",
    type: "article",
  },
};

interface Entry {
  title: string;
  seeing: string;
  why: React.ReactNode;
  fix: React.ReactNode;
}

const ENTRIES: Entry[] = [
  {
    title: "Webhook not delivered",
    seeing: "You published an event but never received the HTTP request at your endpoint.",
    why: (
      <>
        Most often the event type didn&apos;t match any endpoint&apos;s <code>subscribed_event_types</code>, the
        endpoint was inactive, or it&apos;s registered in the wrong environment (<code>test</code> vs{" "}
        <code>live</code>) relative to the event you published.
      </>
    ),
    fix: (
      <>
        Check <code>GET /v1/events/{"{id}"}</code> -- the <code>delivery_jobs</code> array shows exactly which
        endpoints matched. An empty array means nothing was subscribed; that&apos;s a configuration issue, not a
        delivery failure.
      </>
    ),
  },
  {
    title: "Endpoint returns 500",
    seeing: 'A delivery attempt shows error category "transient_http_error" with an HTTP 500 response.',
    why: "Any HTTP 5xx from your endpoint is treated as transient -- RelayHub assumes your server is temporarily struggling, not permanently rejecting the request.",
    fix: (
      <>
        This one retries automatically -- no action needed unless it keeps failing through every attempt. See{" "}
        <Link href="/developers/retries" className="text-signal-amber hover:underline">the retry schedule</Link>.
      </>
    ),
  },
  {
    title: "Endpoint returns 401 or 403",
    seeing: 'A delivery attempt fails with error category "permanent_http_error" and does NOT retry.',
    why: (
      <>
        This is your endpoint rejecting RelayHub&apos;s request (not RelayHub rejecting yours). Only HTTP 408 and 429
        are retried among 4xx responses -- every other 4xx, including 401/403, is treated as permanent, since
        retrying an identical request won&apos;t fix an auth problem on your side.
      </>
    ),
    fix: "If your endpoint expects its own auth header or IP allowlist, confirm RelayHub's requests satisfy it -- then replay the affected deliveries once fixed.",
  },
  {
    title: "Delivery stuck retrying",
    seeing: "A job's status is retrying and attempt_number keeps climbing.",
    why: "Expected behavior -- it means every attempt so far has failed with a retryable error (timeout, connection error, 408/429, or 5xx).",
    fix: (
      <>
        Check <code>GET /v1/deliveries/{"{id}"}</code> for <code>attempt_number</code>, <code>max_attempts</code>,
        and <code>next_attempt_at</code> to see exactly where it stands, and each past attempt&apos;s response for
        why it&apos;s failing.
      </>
    ),
  },
  {
    title: "Delivery moved to the dead-letter queue",
    seeing: 'Status is dead_letter, attempt_number equals max_attempts.',
    why: "Every retryable attempt was exhausted without a success.",
    fix: (
      <>
        Fix whatever the last attempt&apos;s error shows, then{" "}
        <Link href="/developers/replay" className="text-signal-amber hover:underline">replay it</Link> -- see the{" "}
        <Link href="/developers/dead-letter-queue" className="text-signal-amber hover:underline">DLQ guide</Link>.
      </>
    ),
  },
  {
    title: "API key rejected",
    seeing: '401 with "Invalid API key" or "API key is revoked or expired".',
    why: "The key doesn't match any stored key hash, or it's been revoked/expired -- there's no grace period after revocation.",
    fix: "Generate a new key from the dashboard (or POST /v1/api-keys) and update wherever the old one was configured. The full key is only ever shown once, at creation.",
  },
  {
    title: "Missing X-RelayHub-Api-Key header",
    seeing: '401 with "Missing X-RelayHub-Api-Key header".',
    why: (
      <>
        The API key must go in its own <code>X-RelayHub-Api-Key</code> header, not{" "}
        <code>Authorization: Bearer</code> -- that header is reserved for dashboard user sessions (JWTs). This is a
        common mistake; every official SDK made exactly this mistake until a recent fix.
      </>
    ),
    fix: "Send the key as X-RelayHub-Api-Key. If you're on relayhub-sdk before 1.0.1 or the equivalent early SDK versions, update -- earlier versions had this bug built in.",
  },
  {
    title: "Invalid signature on your end",
    seeing: "Your own webhook handler rejects every delivery as unsigned/invalid, even though RelayHub shows it as delivered.",
    why: (
      <>
        The signed string is <code>{"<timestamp>.<nonce>."}</code> concatenated with the raw body -- not the body
        alone. Verifying against the body alone, or against a re-serialized/re-parsed copy of the JSON instead of the
        exact raw bytes, will never match.
      </>
    ),
    fix: (
      <>
        Use the exact verification logic in the{" "}
        <Link href="/developers/quickstart#verify" className="text-signal-amber hover:underline">Quickstart</Link>{" "}
        or the{" "}
        <Link href="/developers/security#signatures" className="text-signal-amber hover:underline">Security guide</Link>{" "}
        -- both are tested against the real backend signing code.
      </>
    ),
  },
  {
    title: "Rate limited",
    seeing: '429 with "rate_limited" as the error code.',
    why: "You've exceeded one of three tiers on this API key: 100/minute, 1,000/hour, or 10,000/day by default.",
    fix: (
      <>
        Check the <code>X-RateLimit-Remaining-*</code> response headers to see which tier, and{" "}
        <code>Retry-After</code> for when to try again. See{" "}
        <Link href="/developers/security#rate-limiting" className="text-signal-amber hover:underline">Security</Link>{" "}
        for the full breakdown.
      </>
    ),
  },
  {
    title: "Authentication failure calling the RelayHub API itself",
    seeing: "401 on a dashboard-style call (endpoints, API keys, deliveries), not on event publishing.",
    why: "These routes use a session JWT (Authorization: Bearer), issued by /v1/auth/login and short-lived -- a stale or expired one will 401.",
    fix: "Re-authenticate via /v1/auth/login, or exchange your refresh token at /v1/auth/refresh instead of logging in again.",
  },
];

export default function TroubleshootingPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Help</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Troubleshooting</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Ten real failure modes, what actually causes each one, and how to fix it -- grounded in the actual
          implementation, not generic advice.
        </p>
      </Section>

      <Section className="pb-24">
        <div className="flex flex-col divide-y divide-graphite-100 dark:divide-graphite-800">
          {ENTRIES.map((entry) => (
            <div key={entry.title} className="grid gap-1.5 py-6 sm:grid-cols-[1fr_2fr]">
              <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{entry.title}</h2>
              <div className="flex flex-col gap-2">
                <p className="text-[13px] text-graphite-500">
                  <span className="font-medium text-graphite-700 dark:text-graphite-300">What you&apos;ll see: </span>
                  {entry.seeing}
                </p>
                <p className="text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  <span className="font-medium text-graphite-700 dark:text-graphite-300">Why: </span>
                  {entry.why}
                </p>
                <p className="text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  <span className="font-medium text-graphite-700 dark:text-graphite-300">Fix: </span>
                  {entry.fix}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
