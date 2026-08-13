"use client";

import { useEffect, useState } from "react";
import { FileSearch, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter", "pending"] as const;

interface AdminLogEntry {
  id: string;
  organization_id: string;
  event_id: string;
  endpoint_id: string;
  status: string;
  attempt_number: number;
  queued_at: string;
  completed_at: string | null;
}

export default function AdminGlobalLogsPage() {
  const [logs, setLogs] = useState<AdminLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [orgIdInput, setOrgIdInput] = useState("");
  const [appliedOrgId, setAppliedOrgId] = useState("");

  async function load() {
    setLogs(null);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (statusFilter) params.set("status", statusFilter);
      if (appliedOrgId) params.set("organization_id", appliedOrgId);

      const data = await api.get<AdminLogEntry[]>(`/v1/admin/logs?${params.toString()}`);
      setLogs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load global logs");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, appliedOrgId]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setAppliedOrgId(orgIdInput.trim());
  }

  function handleClear() {
    setOrgIdInput("");
    setAppliedOrgId("");
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Global Logs</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Delivery jobs across every organization on the platform.
        </p>
      </div>

      <Card className="p-4">
        <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
          <Input
            className="flex-1"
            placeholder="Filter by organization ID"
            value={orgIdInput}
            onChange={(e) => setOrgIdInput(e.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm">
              <Search className="h-3.5 w-3.5" />
              Search
            </Button>
            {appliedOrgId && (
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
          <EmptyState icon={FileSearch} title="No matching logs" description="Try a different organization ID or status filter." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Organization</th>
                <th className="px-4 py-2 font-medium">Endpoint</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Attempts</th>
                <th className="px-4 py-2 font-medium">Queued</th>
                <th className="px-4 py-2 font-medium">Completed</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr
                  key={l.id}
                  className="border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40"
                >
                  <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{l.organization_id}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{l.endpoint_id}</td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={statusToSignalColor(l.status)} label={l.status} />
                  </td>
                  <td className="tabular px-4 py-2.5">{l.attempt_number}</td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(l.queued_at).toLocaleString()}
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {l.completed_at ? new Date(l.completed_at).toLocaleString() : "—"}
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