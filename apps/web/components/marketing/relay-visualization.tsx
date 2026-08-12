"use client";

import { RelayHubMark } from "@/components/ui/logo";
import { StatusDot } from "@/components/ui/status-dot";
import { cn } from "@/lib/cn";

const ENDPOINTS: { label: string; status: "green" | "amber"; delay: number }[] = [
  { label: "api.nordwave.io", status: "green", delay: 0 },
  { label: "hooks.fenwick.dev", status: "green", delay: 0.6 },
  { label: "svc.basalt.app", status: "amber", delay: 1.2 },
];

function Connector({ tone, delay = 0 }: { tone: "amber" | "green"; delay?: number }) {
  return (
    <div className="relative h-px min-w-[28px] flex-1 bg-graphite-700" aria-hidden="true">
      <span className="absolute inset-0 border-t border-dashed border-graphite-700" />
      <span
        className={cn("absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full", tone === "amber" ? "bg-signal-amber" : "bg-signal-green")}
        style={{ animation: `relay-pulse 2.6s ${delay}s infinite ease-in-out` }}
      />
    </div>
  );
}

export function RelayVisualization() {
  return (
    <div
      role="img"
      aria-label="Diagram: an event from checkout.completed flows through RelayHub and is delivered to three endpoints, with retries applied automatically"
      className="relative flex w-full max-w-2xl flex-col gap-6 rounded-lg border border-graphite-800 bg-graphite-900/60 p-6 sm:p-8"
    >
      <div className="flex items-center gap-3 sm:gap-5">
        <div className="flex flex-col items-start gap-1.5 rounded border border-graphite-700 bg-graphite-900 px-3 py-2.5">
          <span className="text-[10px] uppercase tracking-wide text-graphite-500">Event</span>
          <span className="font-mono text-xs text-graphite-100">checkout.completed</span>
        </div>

        <Connector tone="amber" />

        <div
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-graphite-700 bg-graphite-950"
          style={{ animation: "relay-hub-glow 2.6s infinite ease-in-out" }}
        >
          <RelayHubMark size={28} />
        </div>

        <div className="flex flex-1 flex-col gap-2.5">
          {ENDPOINTS.map((ep) => (
            <div key={ep.label} className="flex items-center gap-2.5">
              <Connector tone={ep.status} delay={ep.delay} />
              <div className="flex shrink-0 items-center gap-2 rounded border border-graphite-700 bg-graphite-900 px-2.5 py-1.5">
                <StatusDot color={ep.status} />
                <span className="font-mono text-[11px] text-graphite-200">{ep.label}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-graphite-500">
        Every delivery is signed, retried with exponential backoff on failure, and logged -- nothing silently disappears.
      </p>
    </div>
  );
}
