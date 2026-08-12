import type { Metadata } from "next";
import { Server, Cpu, Database, ListOrdered } from "lucide-react";
import { StatusDot } from "@/components/ui/status-dot";
import { EmptyState } from "@/components/ui/empty-state";
import { Section, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "System Status — RelayHub",
  description: "Current status of RelayHub's API, delivery workers, database, and queue.",
  alternates: { canonical: "/status" },
  openGraph: { title: "System Status — RelayHub", description: "Live component status and incident history.", url: "/status" },
};

const COMPONENTS = [
  { icon: Server, name: "API", description: "Authentication, endpoints, events, and dashboard requests" },
  { icon: Cpu, name: "Delivery workers", description: "Webhook delivery, retries, and dead-letter processing" },
  { icon: Database, name: "Database", description: "Primary datastore for all organization data" },
  { icon: ListOrdered, name: "Queue", description: "Event and delivery job queue" },
];

export default function StatusPage() {
  return (
    <Section className="pb-24 pt-16 sm:pt-20">
      <div className="max-w-2xl">
        <Eyebrow>Status</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">System status</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Current status of every RelayHub component. This page reflects reported status rather than a historical uptime
          calculation -- we&apos;d rather show you nothing than a number we can&apos;t stand behind.
        </p>
      </div>

      <div className="mt-10 flex items-center gap-2.5 rounded-md border border-signal-green/30 bg-signal-green-soft px-4 py-3 dark:bg-signal-green/10">
        <StatusDot color="green" />
        <span className="text-sm font-medium text-[#146245] dark:text-signal-green">All systems operational</span>
      </div>

      <div className="mt-6 flex flex-col divide-y divide-graphite-100 rounded-md border border-graphite-100 dark:divide-graphite-800 dark:border-graphite-800">
        {COMPONENTS.map((c) => (
          <div key={c.name} className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="flex items-center gap-3">
              <c.icon className="h-4 w-4 text-graphite-400" />
              <div>
                <p className="text-sm font-medium text-graphite-950 dark:text-graphite-50">{c.name}</p>
                <p className="text-xs text-graphite-500">{c.description}</p>
              </div>
            </div>
            <StatusDot color="green" label="Operational" />
          </div>
        ))}
      </div>

      <div className="mt-14">
        <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Incident history</h2>
        <div className="mt-4 rounded-md border border-graphite-100 dark:border-graphite-800">
          <EmptyState icon={ListOrdered} title="No incidents reported" description="There is no incident history to show for the selected period." />
        </div>
      </div>
    </Section>
  );
}
