import type { Metadata } from "next";
import { Badge } from "@/components/ui/card";
import { Section, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Changelog — RelayHub",
  description: "Every RelayHub release, in order.",
  alternates: { canonical: "/changelog" },
  openGraph: { title: "Changelog — RelayHub", description: "Version history for the RelayHub platform.", url: "/changelog" },
};

const RELEASES = [
  {
    version: "2.4.0",
    date: "August 2026",
    tag: "Latest",
    title: "Command palette, dark mode, and feature flag overrides",
    items: [
      "Global Cmd/Ctrl+K command palette with live search across endpoints, API keys, events, deliveries, team members, and alerts",
      "Dark mode across the entire dashboard, with system-preference detection and no flash on load",
      "Per-organization feature flag overrides, visible and manageable from the admin panel",
    ],
  },
  {
    version: "2.3.0",
    date: "July 2026",
    title: "Email invitations and a real Team page",
    items: [
      "Invite teammates by email -- no existing account required, with automatic account creation on accept",
      "Password reset flow: one-time, expiring reset links delivered by email",
      "Pending Invitations view with search, filtering, and revoke",
    ],
  },
  {
    version: "2.2.0",
    date: "June 2026",
    title: "Admin panel and billing",
    items: [
      "Organization-level admin panel: suspend, impersonate, and inspect any organization",
      "Global feature flags with per-flag rollout control",
      "Stripe-backed billing across Free, Starter, Pro, and Enterprise plans",
      "Abuse report queue for platform moderation",
    ],
  },
  {
    version: "2.1.0",
    date: "April 2026",
    title: "Alerts and analytics",
    items: [
      "Configurable alert rules across Slack, Discord, webhook, and email channels",
      "Analytics dashboard: delivery volume, p50/p95/p99 latency, and failure rate per endpoint",
      "Sliding-window rate limiting on every write endpoint",
    ],
  },
  {
    version: "2.0.0",
    date: "February 2026",
    title: "Multi-tenant rewrite",
    items: [
      "Organizations, with hard tenant isolation enforced at the database layer",
      "Role-based access control: owner, admin, member, viewer",
      "Full audit logging for every sensitive account action",
    ],
  },
  {
    version: "1.1.0",
    date: "December 2025",
    title: "Dead-letter queue and replay",
    items: [
      "Exhausted deliveries now land in an inspectable dead-letter queue instead of disappearing",
      "One-click replay for any past delivery, from the log or the DLQ",
    ],
  },
  {
    version: "1.0.0",
    date: "October 2025",
    title: "Initial release",
    items: [
      "Signed webhook delivery with per-endpoint secrets",
      "Automatic retries with exponential backoff",
      "API keys and a searchable delivery log",
    ],
  },
];

export default function ChangelogPage() {
  return (
    <Section className="pb-24 pt-16 sm:pt-20">
      <div className="max-w-2xl">
        <Eyebrow>Changelog</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Every release, in order</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          What shipped, and when. Nothing here is aspirational -- see the <a href="/about#roadmap" className="text-signal-amber hover:underline">roadmap</a> for what&apos;s still ahead.
        </p>
      </div>

      <div className="mt-14 flex flex-col">
        {RELEASES.map((release, i) => (
          <div key={release.version} className="relative flex gap-6 pb-12 last:pb-0">
            <div className="flex flex-col items-center">
              <span className="flex h-2.5 w-2.5 shrink-0 rounded-full border-2 border-signal-amber bg-white dark:bg-graphite-950" />
              {i !== RELEASES.length - 1 && <span className="mt-1 w-px flex-1 bg-graphite-100 dark:bg-graphite-800" />}
            </div>
            <div className="flex-1 pb-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="font-mono text-xs text-graphite-500">v{release.version}</span>
                <span className="text-xs text-graphite-400">{release.date}</span>
                {release.tag && <Badge tone="amber">{release.tag}</Badge>}
              </div>
              <div className="mt-3 rounded-md border border-graphite-100 p-5 dark:border-graphite-800">
                <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{release.title}</h2>
                <ul className="mt-3 flex flex-col gap-2">
                  {release.items.map((item) => (
                    <li key={item} className="flex gap-2 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-graphite-400" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
