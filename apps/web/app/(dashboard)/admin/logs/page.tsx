"use client";

import React, { useEffect, useMemo, useState } from "react";
import { FileSearch, Search, ChevronRight, ChevronDown } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter", "pending"] as const;
const IN_FLIGHT = new Set(["queued", "processing", "retrying"]);

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

interface EventGroup {
  key: string;
  organization_id: string;
  event_id: string;
  queued_at: string;
  jobs: AdminLogEntry[];
  overallStatus: "retrying" | "dead_letter" | "failed" | "success";
}

// Same worst-case classification used on the org-scoped Logs/Deliveries pages and
// the dashboard summary: any job still in flight -> "retrying"; else any
// dead-lettered -> "dead_letter"; else any failed -> "failed"; else -> "success".
function classify(jobs: AdminLogEntry[]): EventGroup["overallStatus"] {
  if (jobs.some((j) => IN_FLIGHT.has(j.status))) return "retrying";
  if (jobs.some((j) => j.status === "dead_letter")) return "dead_letter";
  if (jobs.some((j) => j.status === "failed")) return "failed";
  return "success";
}

function groupByEvent(logs: AdminLogEntry[]): EventGroup[] {
  // Group by org+event since this view spans multiple tenants -- event_id alone
  // is unique per-org already, but the composite key keeps things explicit.
  const map = new Map<string, AdminLogEntry[]>();
  for (const log of logs) {
    const key = `${log.organization_id}:${log.event_id}`;
    const list = map.get(key) ?? [];
    list.push(log);
    map.set(key, list);
  }
  return Array.from(map.entries())
    .map(([key, jobs]) => {
      const first = jobs[0]!;
      return {
        key,
        organization_id: first.organization_id,
        event_id: first.event_id,
        queued_at: jobs.reduce((min, j) => (j.queued_at < min ? j.queued_at : min), first.queued_at),
        jobs,
        overallStatus: classify(jobs),
      };
    })
    .sort((a, b) => (a.queued_at < b.queued_at ? 1 : -1));
}

export default function AdminGlobalLogsPage() {
  const [logs, setLogs] = useState<AdminLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [orgIdInput, setOrgIdInput] = useState("");
  const [appliedOrgId, setAppliedOrgId] = useState("");
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

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

  function toggleExpanded(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const eventGroups = useMemo(() => (logs ? groupByEvent(logs) : []), [logs]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Global Logs</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Delivery jobs across every organization on the platform.
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
        ) : !grouped ? (
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
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="w-6 px-4 py-2"></th>
                <th className="px-4 py-2 font-medium">Organization</th>
                <th className="px-4 py-2 font-medium">Event ID</th>
                <th className="px-4 py-2 font-medium">Overall status</th>
                <th className="px-4 py-2 font-medium">Endpoints</th>
                <th className="px-4 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {eventGroups.map((group) => {
                const isOpen = expanded.has(group.key);
                const successCount = group.jobs.filter((j) => j.status === "success").length;
                return (
                  <React.Fragment key={group.key}>
                    <tr
                      onClick={() => toggleExpanded(group.key)}
                      className="cursor-pointer border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40"
                    >
                      <td className="px-4 py-2.5 text-graphite-400">
                        {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{group.organization_id}</td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{group.event_id}</td>
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
                            endpoint {job.endpoint_id.slice(0, 8)}…
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
