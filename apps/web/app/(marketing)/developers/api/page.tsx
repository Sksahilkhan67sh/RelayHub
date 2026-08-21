import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Section, Eyebrow } from "@/components/marketing/section";
import { Badge } from "@/components/ui/card";
import type { Endpoint } from "@/lib/api-modules-data";
import { MODULES } from "@/lib/api-modules-data";

export const metadata: Metadata = {
  title: "API Reference — RelayHub Developers",
  description: "Complete reference for the entire RelayHub REST API -- authentication, API keys, organizations, events, endpoints, deliveries, logs, DLQ, analytics, billing, notifications, audit logs, and admin -- every method, path, auth requirement, and field verified against source.",
  alternates: { canonical: "/developers/api" },
  openGraph: {
    title: "RelayHub API Reference",
    description: "Method, path, auth, request, and response for every RelayHub endpoint -- verified against the real backend.",
    url: "/developers/api",
    type: "article",
  },
};

function MethodBadge({ method }: { method: Endpoint["method"] }) {
  const tone = method === "GET" ? "neutral" : method === "POST" ? "green" : method === "DELETE" ? "red" : "amber";
  return <Badge tone={tone as "neutral" | "green" | "red" | "amber"}>{method}</Badge>;
}

export default function ApiReferencePage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Reference</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">API Reference</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every field below is copied from the real Pydantic request/response schemas -- nothing paraphrased from
          memory. Covers every module: authentication, API keys, organizations, events, endpoints, deliveries, logs,
          DLQ, analytics, billing, notifications, audit logs, and admin.
        </p>
      </Section>

      {MODULES.map((mod, modIndex) => (
        <div key={mod.id} className={modIndex % 2 === 1 ? "border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40" : "border-t border-graphite-100 dark:border-graphite-800"}>
          <Section id={mod.id} className="scroll-mt-20 py-12">
            <h2 className="text-xl font-semibold text-graphite-950 dark:text-graphite-50">{mod.title}</h2>
            <p className="mt-1.5 text-[13.5px] text-graphite-600 dark:text-graphite-400">{mod.intro}</p>
            <div className="mt-6 flex flex-col gap-5">
              {mod.endpoints.map((ep) => (
                <div key={`${ep.method}-${ep.path}`} className="rounded-md border border-graphite-100 bg-white p-4 dark:border-graphite-800 dark:bg-graphite-900">
                  <div className="flex flex-wrap items-center gap-2">
                    <MethodBadge method={ep.method} />
                    <code className="text-[13px] font-medium text-graphite-950 dark:text-graphite-50">{ep.path}</code>
                    <span className="ml-auto text-[11px] text-graphite-500">{ep.auth}</span>
                  </div>
                  <p className="mt-2 text-[13px] text-graphite-600 dark:text-graphite-400">{ep.summary}</p>

                  {ep.params && (
                    <div className="mt-3">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Query params</p>
                      <ul className="mt-1.5 flex flex-col gap-0.5">
                        {ep.params.map((f) => (
                          <li key={f.name} className="font-mono text-[12px] text-graphite-700 dark:text-graphite-300">
                            <span className="text-graphite-950 dark:text-graphite-50">{f.name}</span> <span className="text-graphite-400">{f.type}</span>
                            {f.note && <span className="text-graphite-500"> -- {f.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {ep.body && (
                    <div className="mt-3">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Request body</p>
                      <ul className="mt-1.5 flex flex-col gap-0.5">
                        {ep.body.map((f) => (
                          <li key={f.name} className="font-mono text-[12px] text-graphite-700 dark:text-graphite-300">
                            <span className="text-graphite-950 dark:text-graphite-50">{f.name}</span>{f.type && <span className="text-graphite-400"> {f.type}</span>}
                            {f.note && <span className="text-graphite-500"> -- {f.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="mt-3">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-graphite-500">Response</p>
                    <p className="mt-1 font-mono text-[12px] text-graphite-700 dark:text-graphite-300">{ep.response}</p>
                  </div>

                  {ep.example && (
                    <pre className="mt-3 overflow-x-auto rounded bg-graphite-950 p-3 font-mono text-[11.5px] leading-relaxed text-graphite-200">
                      {ep.example}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </Section>
        </div>
      ))}

      <Section className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-sm text-graphite-600 dark:text-graphite-400">Prefer a typed client to raw HTTP?</p>
        <Link
          href="/developers/sdks"
          className="flex items-center gap-1 text-sm font-medium text-signal-amber hover:underline"
        >
          Browse the SDKs
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Section>
    </>
  );
}
