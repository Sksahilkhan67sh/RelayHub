"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Send } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter"] as const;

export default function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

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

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Deliveries</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Every delivery attempt across all your endpoints.
        </p>
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
        ) : (
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
