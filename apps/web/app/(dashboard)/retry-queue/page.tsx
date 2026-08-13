"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RotateCcw, ChevronRight, ChevronDown } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

interface EventGroup {
  event_id: string;
  event_type: string;
  queued_at: string;
  soonestNextAttempt: string | null;
  jobs: DeliveryLogEntryOut[];
}

function groupByEvent(jobs: DeliveryLogEntryOut[]): EventGroup[] {
  const map = new Map<string, DeliveryLogEntryOut[]>();
  for (const j of jobs) {
    const list = map.get(j.event_id) ?? [];
    list.push(j);
    map.set(j.event_id, list);
  }
  return Array.from(map.entries())
    .map(([event_id, jobs]) => {
      const first = jobs[0]!;
      const withNextAttempt = jobs.filter((j) => j.next_attempt_at);
      const soonestNextAttempt =
        withNextAttempt.length > 0
          ? withNextAttempt.reduce((min, j) => (j.next_attempt_at! < min ? j.next_attempt_at! : min), withNextAttempt[0]!.next_attempt_at!)
          : null;
      return {
        event_id,
        event_type: first.event_type,
        queued_at: jobs.reduce((min, j) => (j.queued_at < min ? j.queued_at : min), first.queued_at),
        soonestNextAttempt,
        jobs,
      };
    })
    .sort((a, b) => (a.queued_at < b.queued_at ? 1 : -1));
}

export default function RetryQueuePage() {
  const [jobs, setJobs] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    api
      .get<DeliveryLogEntryOut[]>("/v1/logs?status=retrying&limit=100")
      .then(setJobs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load retry queue"));
  }, []);

  function toggleExpanded(eventId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }

  const eventGroups = useMemo(() => (jobs ? groupByEvent(jobs) : []), [jobs]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Retry Queue</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Deliveries currently scheduled for a retry attempt (exponential backoff with jitter).
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

      <Card>
        {jobs === null ? (
          <TableSkeleton rows={5} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : jobs.length === 0 ? (
          <EmptyState icon={RotateCcw} title="Nothing retrying right now" description="Deliveries scheduled for retry will show up here." />
        ) : !grouped ? (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Attempt</th>
                <th className="px-4 py-2 font-medium">Next attempt</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5">
                    <Link href={`/deliveries/${j.id}`} className="font-mono text-graphite-950 hover:text-signal-amber dark:text-graphite-50">
                      {j.event_type}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot color="amber" label={`Attempt ${j.attempt_number}`} />
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {j.next_attempt_at ? new Date(j.next_attempt_at).toLocaleString() : "—"}
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(j.queued_at).toLocaleString()}
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
                <th className="px-4 py-2 font-medium">Endpoints retrying</th>
                <th className="px-4 py-2 font-medium">Soonest next attempt</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {eventGroups.map((group) => {
                const isOpen = expanded.has(group.event_id);
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
                      <td className="px-4 py-2.5">
                        <StatusDot color="amber" label={`${group.jobs.length} retrying`} />
                      </td>
                      <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {group.soonestNextAttempt ? new Date(group.soonestNextAttempt).toLocaleString() : "—"}
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
                              endpoint {job.endpoint_id.slice(0, 8)}… — attempt {job.attempt_number}
                            </Link>
                          </td>
                          <td className="tabular px-4 py-2 text-graphite-500">
                            {job.next_attempt_at ? new Date(job.next_attempt_at).toLocaleString() : "—"}
                          </td>
                          <td className="px-4 py-2 text-graphite-500">—</td>
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
