"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Send, ChevronRight, ChevronDown } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter"] as const;
const IN_FLIGHT = new Set(["queued", "processing", "retrying"]);

interface EventGroup {
  event_id: string;
  event_type: string;
  environment: string;
  queued_at: string;
  jobs: DeliveryLogEntryOut[];
  overallStatus: "retrying" | "dead_letter" | "failed" | "success";
}

// Same worst-case classification as the backend's per-event dashboard logic:
// any job still in flight -> "retrying"; else any dead-lettered -> "dead_letter";
// else any failed -> "failed"; else (every job succeeded) -> "success".
function classify(jobs: DeliveryLogEntryOut[]): EventGroup["overallStatus"] {
  if (jobs.some((j) => IN_FLIGHT.has(j.status))) return "retrying";
  if (jobs.some((j) => j.status === "dead_letter")) return "dead_letter";
  if (jobs.some((j) => j.status === "failed")) return "failed";
  return "success";
}

function groupByEvent(deliveries: DeliveryLogEntryOut[]): EventGroup[] {
  const map = new Map<string, DeliveryLogEntryOut[]>();
  for (const d of deliveries) {
    const list = map.get(d.event_id) ?? [];
    list.push(d);
    map.set(d.event_id, list);
  }
  return Array.from(map.entries())
    .map(([event_id, jobs]) => {
      const first = jobs[0];
      return {
        event_id,
        event_type: first.event_type,
        environment: first.environment,
        queued_at: jobs.reduce((min, j) => (j.queued_at < min ? j.queued_at : min), first.queued_at),
        jobs,
        overallStatus: classify(jobs),
      };
    })
    .sort((a, b) => (a.queued_at < b.queued_at ? 1 : -1));
}

export default function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  async function load() {
    setDeliveries(null);
    try {
      const qs = statusFilter ? `?status=${statusFilter}&limit=50` : "?limit=50";
      const data = await api.get<DeliveryLogEntryOut[]>(`/v1/logs${qs}`);
      setDeliveries(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load deliveries");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  function toggleExpanded(eventId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }

  const eventGroups = useMemo(() => (deliveries ? groupByEvent(deliveries) : []), [deliveries]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Deliveries</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Every delivery attempt across all your endpoints.
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-xs text-graphite-600 dark:text-graphite-400">
          <input
            type="checkbox"
            checked={grouped}
            onChange={(e) => setGrouped(e.target.checked)}
            className="h-3.5 w-3.5 accent-signal-amber"
          />
          Group by event
        </label>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <FilterChip active={statusFilter === null} onClick={() => setStatusFilter(null)}>
          All
        </FilterChip>
        {STATUS_FILTERS.map((s) => (
          <FilterChip key={s} active={statusFilter === s} onClick={() => setStatusFilter(s)}>
            {s}
          </FilterChip>
        ))}
      </div>

      <Card>
        {deliveries === null ? (
          <TableSkeleton rows={6} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : deliveries.length === 0 ? (
          <EmptyState icon={Send} title="No deliveries yet" description="Deliveries will appear here once you publish events." />
        ) : !grouped ? (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Attempts</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.map((d) => (
                <tr key={d.id} className="border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40">
                  <td className="px-4 py-2.5">
                    <Link href={`/deliveries/${d.id}`} className="font-mono text-graphite-950 hover:text-signal-amber dark:text-graphite-50">
                      {d.event_type}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{d.environment}</td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={statusToSignalColor(d.status)} label={d.status} />
                  </td>
                  <td className="tabular px-4 py-2.5">{d.attempt_number}</td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(d.queued_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="w-6 px-4 py-2"></th>
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Overall status</th>
                <th className="px-4 py-2 font-medium">Endpoints</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {eventGroups.map((group) => {
                const isOpen = expanded.has(group.event_id);
                const successCount = group.jobs.filter((j) => j.status === "success").length;
                return (
                  <React.Fragment key={group.event_id}>
                    <tr
                      onClick={() => toggleExpanded(group.event_id)}
                      className="cursor-pointer border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40"
                    >
                      <td className="px-4 py-2.5 text-graphite-400">
                        {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{group.event_type}</td>
                      <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{group.environment}</td>
                      <td className="px-4 py-2.5">
                        <StatusDot color={statusToSignalColor(group.overallStatus)} label={group.overallStatus} />
                      </td>
                      <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {successCount}/{group.jobs.length} succeeded
                      </td>
                      <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {new Date(group.queued_at).toLocaleString()}
                      </td>
                    </tr>
                    {isOpen &&
                      group.jobs.map((job) => (
                        <tr key={job.id} className="border-b border-graphite-50 bg-graphite-50/50 last:border-0 dark:border-graphite-800/60 dark:bg-graphite-900/40">
                          <td className="px-4 py-2"></td>
                          <td className="px-4 py-2 pl-2 font-mono text-[11px] text-graphite-500" colSpan={2}>
                            <Link href={`/deliveries/${job.id}`} className="hover:text-signal-amber">
                              endpoint {job.endpoint_id.slice(0, 8)}…
                            </Link>
                          </td>
                          <td className="px-4 py-2">
                            <StatusDot color={statusToSignalColor(job.status)} label={job.status} />
                          </td>
                          <td className="px-4 py-2 text-graphite-500">attempt {job.attempt_number}</td>
                          <td className="tabular px-4 py-2 text-graphite-500">
                            {job.completed_at ? new Date(job.completed_at).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors ${
        active ? "bg-signal-amber text-white" : "bg-graphite-100 text-graphite-600 dark:bg-graphite-800 dark:text-graphite-400"
      }`}
    >
      {children}
    </button>
  );
}
