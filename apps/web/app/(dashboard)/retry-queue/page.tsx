"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RotateCcw, ChevronRight, ChevronDown, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

interface EventGroup {
  event_id: string;
  event_type: string;
  queued_at: string;
  soonestNextAttempt: string | null;
  maxAttempt: number;
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
        maxAttempt: Math.max(...jobs.map((j) => j.attempt_number)),
        jobs,
      };
    })
    .sort((a, b) => (a.queued_at < b.queued_at ? 1 : -1));
}

// Formats a millisecond duration as a short, human-readable string: "42s", "5m 12s",
// "2h 6m", "3d 4h". Caps components at two units so it stays scannable in a table cell.
function formatDuration(ms: number): string {
  if (ms < 0) ms = 0;
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}

export default function RetryQueuePage() {
  const [jobs, setJobs] = useState<DeliveryLogEntryOut[] | null>(null);
  const [recovered, setRecovered] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    api
      .get<DeliveryLogEntryOut[]>("/v1/logs?status=retrying&limit=100")
      .then(setJobs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load retry queue"));

    // "Recently recovered" isn't its own status -- it's a successful job that took
    // more than one attempt. There's no min-attempt filter on the logs API, so we
    // fetch recent successes and filter client-side for attempt_number > 1.
    api
      .get<DeliveryLogEntryOut[]>("/v1/logs?status=success&limit=100")
      .then((data) => setRecovered(data.filter((j) => j.attempt_number > 1)))
      .catch(() => setRecovered([])); // non-critical section; fail quietly rather than blocking the page

    // Keep "retrying for" elapsed times ticking without needing a full data refetch.
    const interval = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(interval);
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
  const recoveredSorted = useMemo(
    () => (recovered ? [...recovered].sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? "")).slice(0, 10) : []),
    [recovered]
  );

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
                <th className="px-4 py-2 font-medium">Retrying for</th>
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
                    {formatDuration(now - new Date(j.queued_at).getTime())}
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
                <th className="px-4 py-2 font-medium">Highest attempt</th>
                <th className="px-4 py-2 font-medium">Retrying for</th>
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
                        {group.maxAttempt} {group.maxAttempt === 1 ? "attempt" : "attempts"} so far
                      </td>
                      <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {formatDuration(now - new Date(group.queued_at).getTime())}
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
                            {formatDuration(now - new Date(job.queued_at).getTime())}
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

      <Card>
        <CardHeader>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-signal-green" />
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Recently recovered after retry</h2>
          </div>
        </CardHeader>
        {recovered === null ? (
          <TableSkeleton rows={3} />
        ) : recoveredSorted.length === 0 ? (
          <div className="p-6 text-center text-xs text-graphite-500">Nothing has needed a retry to succeed recently.</div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Delivered after</th>
                <th className="px-4 py-2 font-medium">Total time to deliver</th>
                <th className="px-4 py-2 font-medium">Delivered at</th>
              </tr>
            </thead>
            <tbody>
              {recoveredSorted.map((j) => (
                <tr key={j.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5">
                    <Link href={`/deliveries/${j.id}`} className="font-mono text-graphite-950 hover:text-signal-amber dark:text-graphite-50">
                      {j.event_type}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot color="green" label={`${j.attempt_number} attempts`} />
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {j.completed_at ? formatDuration(new Date(j.completed_at).getTime() - new Date(j.queued_at).getTime()) : "—"}
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {j.completed_at ? new Date(j.completed_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
