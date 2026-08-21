import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { Badge } from "@/components/ui/card";
import { CodeTabs } from "@/components/marketing/code-tabs";
import { SDKS, RESOURCES } from "@/lib/sdks-data";

export const metadata: Metadata = {
  title: "SDKs — RelayHub Developers",
  description:
    "Four official RelayHub SDKs -- Node.js, Python, Go, and Java -- thin typed wrappers over the REST API, with real install commands and per-SDK verification status.",
  alternates: { canonical: "/developers/sdks" },
  openGraph: {
    title: "RelayHub SDKs",
    description: "Node.js, Python, Go, and Java clients for the RelayHub API, verified against the actual source.",
    url: "/developers/sdks",
    type: "article",
  },
};

export default function SdksPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link
          href="/developers"
          className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Reference</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
          SDKs
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Four official SDKs, all thin typed wrappers over the same REST API documented in the{" "}
          <Link href="/developers/api" className="text-signal-amber hover:underline">
            API reference
          </Link>
          . No SDK contains business logic the API doesn&apos;t already implement.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Choose a language" title="Install and create a client" />
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            {SDKS.map((sdk) => (
              <div
                key={sdk.name}
                className="rounded-lg border border-graphite-200 bg-white p-5 dark:border-graphite-800 dark:bg-graphite-950"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">{sdk.name}</h3>
                  <Badge tone={sdk.status.tone}>{sdk.status.label}</Badge>
                </div>
                <code className="mt-3 block break-all text-[12.5px] text-graphite-700 dark:text-graphite-300">{sdk.install}</code>
                <div className="mt-4">
                  <CodeTabs
                    filename="client"
                    tabs={[
                      { label: "Direct", code: sdk.clientCode },
                      { label: "Builder", code: sdk.builderCode },
                    ]}
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Resources" title="Identical resource surface across all four" />
        <div className="mt-6 flex flex-wrap gap-2">
          {RESOURCES.map((r) => (
            <code
              key={r}
              className="rounded-md border border-graphite-200 bg-graphite-50 px-2.5 py-1 text-[12.5px] text-graphite-700 dark:border-graphite-800 dark:bg-graphite-900/40 dark:text-graphite-300"
            >
              {r}
            </code>
          ))}
        </div>
        <p className="mt-4 max-w-2xl text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Deliberately not included in any SDK: a &quot;Projects&quot; resource -- no such entity exists in the
          backend. <code>notifications</code> maps to the real <code>/alerts/*</code> endpoints.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Shared behavior" title="Retries, timeouts, pagination, idempotency" />
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Retries</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                All four retry 429 and 5xx responses (and, for Node/Python/Go, network errors) with exponential
                backoff, honoring a <code>Retry-After</code> header when the server sends one.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Timeouts</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                A client-level default timeout plus a per-call override on every SDK.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Pagination</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                List endpoints return a plain array with <code>limit</code>/<code>offset</code> query params -- each
                SDK ships a small pagination helper that walks pages until one comes back shorter than requested.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Idempotency</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                <code>POST /events</code> accepts an <code>idempotency_key</code> in the request body; every SDK
                exposes it as a first-class option on the publish call.
              </p>
            </div>
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Limitations" title="What's not verified yet" />
        <ul className="mt-4 max-w-2xl list-disc space-y-2 pl-5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          <li>
            Go and Java are unverified in this development environment -- both were written and manually reviewed,
            but neither has been mechanically compiled. Run <code>go build ./... &amp;&amp; go test ./...</code> (Go)
            or <code>mvn compile test</code> (Java) with the respective toolchain before depending on them in
            production.
          </li>
          <li>No SDK supports the SMS alert channel end-to-end, because the backend itself doesn&apos;t yet.</li>
          <li>
            No SDK wraps <code>POST /billing/webhook</code> -- it&apos;s Stripe&apos;s inbound receiver, never called
            by an API consumer.
          </li>
        </ul>
      </Section>

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">Prefer a command line to a client library?</p>
        <Link
          href="/developers/cli"
          className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline"
        >
          Read the CLI reference
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
