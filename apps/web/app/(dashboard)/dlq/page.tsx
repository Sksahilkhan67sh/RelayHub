"use client";

import { useEffect, useState } from "react";
import { Inbox, RotateCw, Trash2, Download, ChevronDown, ChevronUp } from "lucide-react";
import { api, ApiError, getAccessToken } from "@/lib/api-client";
import type { DeadLetterJobOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DlqPage() {
  const [jobs, setJobs] = useState<DeadLetterJobOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const data = await api.get<DeadLetterJobOut[]>("/v1/dlq");
      setJobs(data);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dead letter queue");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleRetry(id: string) {
    setBusy(true);
    try {
      await api.post(`/v1/dlq/${id}/retry`);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to retry job");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this dead letter entry? This only hides it from the queue, it does not undo the failed delivery.")) return;
    setBusy(true);
    try {
      await api.delete(`/v1/dlq/${id}`);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to delete job");
    } finally {
      setBusy(false);
    }
  }

  async function handleBulkRetry() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const result = await api.post<{ retried: string[]; skipped: string[] }>("/v1/dlq/bulk-retry", {
        job_ids: Array.from(selected),
      });
      if (result.skipped.length > 0) {
        alert(`Retried ${result.retried.length}, skipped ${result.skipped.length} (already handled or not found).`);
      }
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Bulk retry failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE_URL}/v1/dlq/export`, {
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
    a.download = "relayhub_dead_letter_export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Dead Letter Queue</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Deliveries that exhausted all retry attempts.
          </p>
        </div>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <Button size="sm" variant="secondary" onClick={handleBulkRetry} disabled={busy}>
              <RotateCw className="h-3.5 w-3.5" />
              Retry {selected.size} selected
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={handleExport}>
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      <Card>
        {jobs === null ? (
          <TableSkeleton rows={5} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : jobs.length === 0 ? (
          <EmptyState icon={Inbox} title="Dead letter queue is empty" description="Deliveries that exhaust all retries will appear here." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="w-8 px-4 py-2"></th>
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Attempts</th>
                <th className="px-4 py-2 font-medium">Last error</th>
                <th className="px-4 py-2 font-medium">Failed at</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <>
                  <tr key={j.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5">
                      <input type="checkbox" checked={selected.has(j.id)} onChange={() => toggleSelect(j.id)} />
                    </td>
                    <td className="px-4 py-2.5">
                      <button
                        onClick={() => setExpandedId(expandedId === j.id ? null : j.id)}
                        className="flex items-center gap-1 font-mono text-graphite-950 hover:text-signal-amber dark:text-graphite-50"
                      >
                        {j.event_type}
                        {expandedId === j.id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      </button>
                    </td>
                    <td className="tabular px-4 py-2.5">{j.attempt_number}</td>
                    <td className="px-4 py-2.5">
                      {j.last_error_category && <Badge tone="red">{j.last_error_category}</Badge>}
                    </td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {j.completed_at ? new Date(j.completed_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => handleRetry(j.id)} className="rounded p-1.5 text-graphite-500 hover:bg-graphite-100 dark:hover:bg-graphite-800" title="Retry">
                          <RotateCw className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => handleDelete(j.id)} className="rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red" title="Delete">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedId === j.id && (
                    <tr className="border-b border-graphite-50 bg-graphite-50 dark:border-graphite-800/60 dark:bg-graphite-800/30">
                      <td colSpan={6} className="px-4 py-3">
                        <div className="flex flex-col gap-2">
                          {j.last_error_message && <p className="text-xs text-signal-red">{j.last_error_message}</p>}
                          <pre className="overflow-x-auto font-mono text-[11px] text-graphite-700 dark:text-graphite-300">
                            {JSON.stringify(j.payload, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
