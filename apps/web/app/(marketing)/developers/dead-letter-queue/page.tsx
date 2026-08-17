import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { CodeTabs } from "@/components/marketing/code-tabs";

export const metadata: Metadata = {
  title: "Dead-Letter Queue — RelayHub Developers",
  description: "How RelayHub's dead-letter queue works: what lands there, what fields are available, required permissions, CSV export, and how to inspect a failed delivery.",
  alternates: { canonical: "/developers/dead-letter-queue" },
  openGraph: {
    title: "RelayHub Dead-Letter Queue",
    description: "What lands in the DLQ, what you can see, and how to inspect it -- real API, real fields.",
    url: "/developers/dead-letter-queue",
    type: "article",
  },
};

export default function DeadLetterQueuePage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Guides</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Dead-letter queue</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          A delivery that exhausts every retry attempt without succeeding doesn&apos;t just disappear -- it lands
          here, fully inspectable.
        </p>
      </Section>

      <Section className="py-8">
        <SectionHeading eyebrow="How it happens" title="The path into the DLQ" />
        <div className="mt-8 flex flex-wrap items-center gap-2">
          {["Delivery", "Retry", "Retry exhausted", "DLQ"].map((step, i, arr) => (
            <div key={step} className="flex items-center gap-2">
              <span className="rounded-md border border-graphite-200 bg-white px-3 py-2 text-xs font-medium text-graphite-800 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-200">
                {step}
              </span>
              {i < arr.length - 1 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-graphite-300 dark:text-graphite-700" />}
            </div>
          ))}
        </div>
        <p className="mt-6 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Only jobs that exhaust the <Link href="/developers/retries" className="text-signal-amber hover:underline">retry schedule</Link>{" "}
          land here -- a permanently-classified failure (a 401, for example) fails immediately without ever entering
          the DLQ, since retrying it wouldn&apos;t help.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Inspecting" title="What you can see" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Each entry includes the event type, the original payload, how many attempts it took (and the max it was
            allowed), when it was queued and when it finally gave up, and the last attempt&apos;s error category and
            message -- plus the full attempt-by-attempt history.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="list-dlq"
              tabs={[
                {
                  label: "cURL",
                  code: `curl https://api.relayhub.dev/v1/dlq \\
  -H "Authorization: Bearer $TOKEN"

# -> [{ "id": "...", "event_type": "payment.success", "attempt_number": 5,
#      "max_attempts": 5, "last_error_category": "transient_http_error",
#      "last_error_message": "Destination returned HTTP 503", ... }]`,
                },
              ]}
            />
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Permissions" title="Who can do what" />
        <div className="mt-6 overflow-hidden rounded-md border border-graphite-100 dark:border-graphite-800">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-graphite-100 bg-graphite-50 text-xs text-graphite-500 dark:border-graphite-800 dark:bg-graphite-900/40">
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Minimum role</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-graphite-50 dark:border-graphite-800/60">
                <td className="px-4 py-2.5 text-graphite-700 dark:text-graphite-300">List / view / export CSV</td>
                <td className="px-4 py-2.5"><code className="text-graphite-950 dark:text-graphite-50">viewer</code></td>
              </tr>
              <tr className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                <td className="px-4 py-2.5 text-graphite-700 dark:text-graphite-300">
                  Retry / delete (single or bulk) --{" "}
                  <Link href="/developers/replay" className="text-signal-amber hover:underline">see Replay</Link>
                </td>
                <td className="px-4 py-2.5"><code className="text-graphite-950 dark:text-graphite-50">admin</code></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Export" title="CSV export for offline analysis" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Export every DLQ entry (optionally filtered to one endpoint) as a CSV download -- useful for a
            postmortem or for sharing with a team that doesn&apos;t have dashboard access.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="export"
              tabs={[
                {
                  label: "cURL",
                  code: `curl https://api.relayhub.dev/v1/dlq/export \\
  -H "Authorization: Bearer $TOKEN" \\
  -o relayhub_dead_letter_export.csv

# Optionally scope to one endpoint:
curl "https://api.relayhub.dev/v1/dlq/export?endpoint_id=YOUR_ENDPOINT_ID" \\
  -H "Authorization: Bearer $TOKEN" -o export.csv`,
                },
              ]}
            />
          </div>
        </Section>
      </div>

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">Fixed the issue that caused these failures?</p>
        <Link href="/developers/replay" className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline">
          Read the replay guide
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
