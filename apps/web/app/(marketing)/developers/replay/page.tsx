import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { CodeTabs } from "@/components/marketing/code-tabs";

export const metadata: Metadata = {
  title: "Replay — RelayHub Developers",
  description: "How to replay a dead-lettered delivery in RelayHub: single and bulk retry, what resets, and required permissions.",
  alternates: { canonical: "/developers/replay" },
  openGraph: {
    title: "RelayHub Replay",
    description: "Re-deliver a dead-lettered event once you've fixed the underlying issue -- the real API.",
    url: "/developers/replay",
    type: "article",
  },
};

export default function ReplayPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Guides</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Replay</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Fixed whatever caused the failure? Re-queue a dead-lettered delivery as a fresh attempt.
        </p>
      </Section>

      <Section className="py-8">
        <div className="flex flex-wrap items-center gap-2">
          {["DLQ", "Fix endpoint", "Replay", "Delivery", "Success"].map((step, i, arr) => (
            <div key={step} className="flex items-center gap-2">
              <span className="rounded-md border border-graphite-200 bg-white px-3 py-2 text-xs font-medium text-graphite-800 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-200">
                {step}
              </span>
              {i < arr.length - 1 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-graphite-300 dark:text-graphite-700" />}
            </div>
          ))}
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Single replay" title="Retry one delivery" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Requires the <code>admin</code> role. This queues the job again with a reset attempt counter -- it gets
            the <em>full</em> retry schedule again if it fails, not just one extra shot before going straight back to
            the DLQ.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="replay"
              tabs={[
                {
                  label: "cURL",
                  code: `curl -X POST https://api.relayhub.dev/v1/dlq/YOUR_DEAD_LETTER_JOB_ID/retry \\
  -H "Authorization: Bearer $TOKEN"

# -> { "id": "...", "status": "queued" }`,
                },
              ]}
            />
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Bulk replay" title="Retry several at once" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          If a single downstream outage dead-lettered a batch of deliveries, replay all of them in one call. The
          response separates what actually got queued from what was skipped (for example, a job ID that no longer
          exists or wasn&apos;t in the DLQ).
        </p>
        <div className="mt-6">
          <CodeTabs
            filename="bulk-replay"
            tabs={[
              {
                label: "cURL",
                code: `curl -X POST https://api.relayhub.dev/v1/dlq/bulk-retry \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "job_ids": ["job_id_1", "job_id_2", "job_id_3"] }'

# -> { "retried": ["job_id_1", "job_id_2"], "skipped": ["job_id_3"] }`,
              },
            ]}
          />
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Before you replay" title="Fix the endpoint first" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Replaying doesn&apos;t change anything about the destination -- it just gives the same request another
            chance. If the underlying cause (wrong URL, expired auth on your side, a downstream bug) isn&apos;t
            actually fixed, the replayed job will simply exhaust its retries and land back in the DLQ.
          </p>
        </Section>
      </div>

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">Want to see the full delivery attempt history?</p>
        <Link href="/developers/concepts#delivery-attempts" className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
          Back to Concepts
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
