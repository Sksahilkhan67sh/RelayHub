"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RotateCcw } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function RetryQueuePage() {
  const [jobs, setJobs] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DeliveryLogEntryOut[]>("/v1/logs?status=retrying&limit=100")
      .then(setJobs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load retry queue"));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Retry Queue</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Deliveries currently scheduled for a retry attempt (exponential backoff with jitter).
        </p>
      </div>

      <Card>
        {jobs === null ? (
          <TableSkeleton rows={5} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : jobs.length === 0 ? (
          <EmptyState icon={RotateCcw} title="Nothing retrying right now" description="Deliveries scheduled for retry will show up here." />
        ) : (
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
        )}
      </Card>
    </div>
  );
}
