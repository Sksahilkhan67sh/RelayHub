"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ScrollText, Search, ChevronRight, ChevronDown, Download } from "lucide-react";
import { api, ApiError, getAccessToken } from "@/lib/api-client";
import type { DeliveryLogEntryOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATUS_FILTERS = ["queued", "processing", "success", "retrying", "failed", "dead_letter", "pending"] as const;
const IN_FLIGHT = new Set(["queued", "processing", "retrying"]);

interface Filters {
  request_id: string;
  event_type: string;
  environment: string;
  endpoint_id: string;
}

const EMPTY_FILTERS: Filters = { request_id: "", event_type: "", environment: "", endpoint_id: "" };

interface EventGroup {
  event_id: string;
  event_type: string;
  environment: string;
  request_id: string;
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

function groupByEvent(logs: DeliveryLogEntryOut[]): EventGroup[] {
  const map = new Map<string, DeliveryLogEntryOut[]>();
  for (const log of logs) {
    const list = map.get(log.event_id) ?? [];
    list.push(log);
    map.set(log.event_id, list);
  }
  return Array.from(map.entries())
    .map(([event_id, jobs]) => {
      // Safe: this group only exists because at least one job was pushed into it above.
      const first = jobs[0]!;
      return {
        event_id,
        event_type: first.event_type,
        environment: first.environment,
        request_id: first.request_id,
        queued_at: jobs.reduce((min, j) => (j.queued_at < min ? j.queued_at : min), first.queued_at),
        jobs,
        overallStatus: classify(jobs),
      };
    })
    .sort((a, b) => (a.queued_at < b.queued_at ? 1 : -1));
}

export default function LogsPage() {
  const [logs, setLogs] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(EMPTY_FILTERS);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  function buildParams() {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (appliedFilters.request_id) params.set("request_id", appliedFilters.request_id);
    if (appliedFilters.event_type) params.set("event_type", appliedFilters.event_type);
    if (appliedFilters.environment) params.set("environment", appliedFilters.environment);
    if (appliedFilters.endpoint_id) params.set("endpoint_id", appliedFilters.endpoint_id);
    return params;
  }

  async function handleExport() {
    setExporting(true);
    try {
      const token = getAccessToken();
      // Exports every delivery job matching the current filters -- every status
      // (queued, processing, success, retrying, failed, dead_letter), not just
      // whichever status chip happens to be selected on screen.
      const resp = await fetch(`${API_BASE_URL}/v1/logs/export?${buildParams().toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        alert("Failed to export CSV");
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "relayhub_delivery_logs.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Failed to export CSV");
    } finally {
      setExporting(false);
    }
  }

  async function load() {
    setLogs(null);
    setError(null);
    try {
      const params = buildParams();
      params.set("limit", "50");

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

  function toggleExpanded(eventId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }

  const hasActiveTextFilters = Object.values(appliedFilters).some(Boolean);
  const eventGroups = useMemo(() => (logs ? groupByEvent(logs) : []), [logs]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Logs</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Search delivery logs by request, event type, environment, or endpoint.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-graphite-600 dark:text-graphite-400">
            <input
              type="checkbox"
              checked={grouped}
              onChange={(e) => setGrouped(e.target.checked)}
              className="h-3.5 w-3.5 accent-signal-amber"
            />
            Group by event
          </label>
          <Button type="button" variant="secondary" size="sm" loading={exporting} onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        </div>
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
        ) : !grouped ? (
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
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="w-6 px-4 py-2"></th>
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Request ID</th>
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
                      <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{group.event_type || "—"}</td>
                      <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{group.environment || "—"}</td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-graphite-500">{group.request_id || "—"}</td>
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
                          <td className="px-4 py-2 font-mono text-[11px] text-graphite-500">attempt {job.attempt_number}</td>
                          <td className="px-4 py-2">
                            <StatusDot color={statusToSignalColor(job.status)} label={job.status} />
                          </td>
                          <td className="px-4 py-2 text-graphite-500">—</td>
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
