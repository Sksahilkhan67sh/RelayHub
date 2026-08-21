import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { Badge } from "@/components/ui/card";
import { CodeTabs } from "@/components/marketing/code-tabs";
import { COMMANDS, GLOBAL_FLAGS } from "@/lib/cli-commands-data";

export const metadata: Metadata = {
  title: "CLI — RelayHub Developers",
  description: "The RelayHub command-line tool: installation, authentication, and every command, verified against the actual source.",
  alternates: { canonical: "/developers/cli" },
  openGraph: {
    title: "RelayHub CLI",
    description: "Every relay command, real usage syntax -- verified against source.",
    url: "/developers/cli",
    type: "article",
  },
};

export default function CliPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Reference</Eyebrow>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">CLI</h1>
          <Badge tone="amber">Not yet published to npm</Badge>
        </div>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          A full command-line tool (<code>relay</code>) exists in the repository&apos;s <code>cli/</code> directory,
          wrapping the Node.js SDK. It isn&apos;t published to npm yet, so build it from source for now.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Setup" title="Build from source, then log in" />
          <div className="mt-6">
            <CodeTabs
              filename="setup"
              tabs={[
                {
                  label: "Shell",
                  code: `git clone https://github.com/relayhub/relayhub.git
cd relayhub/cli
npm install
npm run build
node dist/index.js login`,
                },
              ]}
            />
          </div>
          <p className="mt-3 text-xs text-graphite-500">
            <code>relay login</code> is interactive by default (prompts for email/password) and never stores your
            password -- it creates and stores a dedicated CLI API key instead. Pass{" "}
            <code>--api-key</code> to skip the prompt if you already have one.
          </p>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Commands" title="Every command, real usage syntax" />
        <div className="mt-6 flex flex-col divide-y divide-graphite-100 dark:divide-graphite-800">
          {COMMANDS.map((c) => (
            <div key={c.name} className="grid gap-1 py-4 sm:grid-cols-[100px_1fr]">
              <span className="font-mono text-[13px] font-medium text-graphite-950 dark:text-graphite-50">{c.name}</span>
              <div>
                <code className="text-[12.5px] text-graphite-700 dark:text-graphite-300">{c.usage}</code>
                {c.note && <p className="mt-1 text-[12.5px] text-graphite-500">{c.note}</p>}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-12">
          <SectionHeading eyebrow="Global flags" title="Apply to every command" />
          <div className="mt-6 flex flex-col gap-2">
            {GLOBAL_FLAGS.map((f) => (
              <div key={f.flag} className="flex items-baseline gap-3">
                <code className="w-40 shrink-0 text-[12.5px] text-graphite-950 dark:text-graphite-50">{f.flag}</code>
                <span className="text-[13px] text-graphite-600 dark:text-graphite-400">{f.note}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section className="py-12">
        <SectionHeading eyebrow="Configuration" title="How credentials are resolved" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          In order: the <code>--api-key</code> flag, then the <code>RELAYHUB_API_KEY</code> environment variable,
          then <code>~/.relayhub/config.json</code> (written by <code>relay login</code>). Run{" "}
          <code>relay doctor</code> any time to check which one actually resolved and confirm live connectivity.
        </p>
      </Section>
    </>
  );
}
