import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { CodeTabs } from "@/components/marketing/code-tabs";

export const metadata: Metadata = {
  title: "Retries — RelayHub Developers",
  description: "How RelayHub's retry schedule actually works: attempt counting, backoff timing, jitter, per-endpoint overrides, and which failures are retried at all.",
  alternates: { canonical: "/developers/retries" },
  openGraph: {
    title: "RelayHub Retries",
    description: "The real retry schedule, attempt counting, and retryable-vs-permanent failure classification.",
    url: "/developers/retries",
    type: "article",
  },
};

const SCHEDULE = [
  { attempt: 1, delay: "immediate" },
  { attempt: 2, delay: "10s later" },
  { attempt: 3, delay: "30s later" },
  { attempt: 4, delay: "1m later" },
  { attempt: 5, delay: "5m later" },
];

export default function RetriesPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Guides</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Retries</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          The real schedule, exactly as implemented -- not a rounded-off approximation.
        </p>
      </Section>

      <Section className="py-8">
        <SectionHeading eyebrow="Default schedule" title="5 attempts, escalating delay" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          The platform default is 5 total attempts. Each delay below has +/-20% jitter applied, so many endpoints
          failing at the same moment (e.g. a shared downstream outage) don&apos;t all retry in the same synchronized
          burst against a service that&apos;s still recovering.
        </p>
        <div className="mt-6 overflow-hidden rounded-md border border-graphite-100 dark:border-graphite-800">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-graphite-100 bg-graphite-50 text-xs text-graphite-500 dark:border-graphite-800 dark:bg-graphite-900/40">
                <th className="px-4 py-2 font-medium">Attempt</th>
                <th className="px-4 py-2 font-medium">Runs</th>
              </tr>
            </thead>
            <tbody>
              {SCHEDULE.map((row) => (
                <tr key={row.attempt} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{row.attempt} / 5</td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{row.delay}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-graphite-500">
          After attempt 5 fails, the job moves to the{" "}
          <Link href="/developers/dead-letter-queue" className="text-signal-amber hover:underline">dead-letter queue</Link>{" "}
          instead of retrying again.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Per-endpoint override" title="Change the max for one endpoint" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Any endpoint can set its own <code>max_retry_attempts</code>, independent of the platform default. A
            lower-traffic internal tool might want fewer attempts; a critical payment webhook might want more.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="update-endpoint"
              tabs={[
                {
                  label: "cURL",
                  code: `curl -X PATCH https://api.relayhub.dev/v1/endpoints/YOUR_ENDPOINT_ID \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "max_retry_attempts": 3 }'`,
                },
              ]}
            />
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Classification" title="What actually gets retried" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Not every failure schedules a retry. RelayHub classifies each failed attempt, and only some categories are
          retryable:
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-md border border-graphite-100 p-4 dark:border-graphite-800">
            <h3 className="text-sm font-semibold text-signal-green">Retried</h3>
            <ul className="mt-2 flex flex-col gap-1 text-[13px] text-graphite-600 dark:text-graphite-400">
              <li>Connection timeout</li>
              <li>Connection error (DNS failure, refused connection)</li>
              <li>HTTP 408, 429</li>
              <li>Any HTTP 5xx</li>
            </ul>
          </div>
          <div className="rounded-md border border-graphite-100 p-4 dark:border-graphite-800">
            <h3 className="text-sm font-semibold text-signal-red">Not retried -- fails immediately</h3>
            <ul className="mt-2 flex flex-col gap-1 text-[13px] text-graphite-600 dark:text-graphite-400">
              <li>Any other HTTP 4xx (400, 401, 403, 404, 422, ...)</li>
              <li>SSRF-blocked destination</li>
              <li>Request-signing error</li>
            </ul>
          </div>
        </div>
        <p className="mt-4 max-w-2xl text-[13.5px] text-graphite-500">
          The reasoning: a 4xx (other than 408/429) usually means the request itself is wrong -- retrying an
          identical request won&apos;t fix a 401 or a 404. A 5xx or timeout usually means the destination is
          temporarily struggling, which retrying can genuinely help with.
        </p>
      </Section>

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">What happens after every attempt is exhausted?</p>
        <Link href="/developers/dead-letter-queue" className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
          Read the dead-letter queue guide
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
