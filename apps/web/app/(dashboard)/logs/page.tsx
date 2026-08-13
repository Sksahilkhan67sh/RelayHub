"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ScrollText, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter", "pending"] as const;

interface Filters {
  request_id: string;
  event_type: string;
  environment: string;
  endpoint_id: string;
}

const EMPTY_FILTERS: Filters = { request_id: "", event_type: "", environment: "", endpoint_id: "" };

export default function LogsPage() {
  const [logs, setLogs] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(EMPTY_FILTERS);

  async function load() {
    setLogs(null);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (statusFilter) params.set("status", statusFilter);
      if (appliedFilters.request_id) params.set("request_id", appliedFilters.request_id);
      if (appliedFilters.event_type) params.set("event_type", appliedFilters.event_type);
      if (appliedFilters.environment) params.set("environment", appliedFilters.environment);
      if (appliedFilters.endpoint_id) params.set("endpoint_id", appliedFilters.endpoint_id);

      const data = await api.get<DeliveryLogEntryOut[]>(`/v1/logs?${params.toString()}`);
      setLogs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load logs");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, appliedFilters]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setAppliedFilters(filters);
  }

  function handleClear() {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  }

  const hasActiveTextFilters = Object.values(appliedFilters).some(Boolean);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Logs</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Search delivery logs by request, event type, environment, or endpoint.
        </p>
      </div>

      <Card className="p-4">
        <form onSubmit={handleSearch} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <Input
            placeholder="Request ID"
            value={filters.request_id}
            onChange={(e) => setFilters((f) => ({ ...f, request_id: e.target.value }))}
          />
          <Input
            placeholder="Event type (e.g. payment.failed)"
            value={filters.event_type}
            onChange={(e) => setFilters((f) => ({ ...f, event_type: e.target.value }))}
          />
          <Input
            placeholder="Environment"
            value={filters.environment}
            onChange={(e) => setFilters((f) => ({ ...f, environment: e.target.value }))}
          />
          <Input
            placeholder="Endpoint ID"
            value={filters.endpoint_id}
            onChange={(e) => setFilters((f) => ({ ...f, endpoint_id: e.target.value }))}
          />
          <div className="flex gap-2 sm:col-span-4">
            <Button type="submit" size="sm">
              <Search className="h-3.5 w-3.5" />
              Search
            </Button>
            {hasActiveTextFilters && (
              <Button type="button" variant="secondary" size="sm" onClick={handleClear}>
                Clear
              </Button>
            )}
          </div>
        </form>
      </Card>

      <div className="flex flex-wrap gap-1.5">
        <FilterChip active={statusFilter === null} onClick={() => setStatusFilter(null)}>
          All statuses
        </FilterChip>
        {STATUS_FILTERS.map((s) => (
          <FilterChip key={s} active={statusFilter === s} onClick={() => setStatusFilter(s)}>
            {s}
          </FilterChip>
        ))}
      </div>

      <Card>
        {logs === null ? (
          <TableSkeleton rows={6} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : logs.length === 0 ? (
          <EmptyState icon={ScrollText} title="No matching logs" description="Try adjusting your search or status filter." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Request ID</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Attempts</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr
                  key={l.id}
                  className="border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40"
                >
                  <td className="px-4 py-2.5">
                    <Link href={`/deliveries/${l.id}`} className="font-mono text-graphite-950 hover:text-signal-amber dark:text-graphite-50">
                      {l.event_type || "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{l.environment || "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{l.request_id || "—"}</td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={statusToSignalColor(l.status)} label={l.status} />
                  </td>
                  <td className="tabular px-4 py-2.5">{l.attempt_number}</td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(l.queued_at).toLocaleString()}
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