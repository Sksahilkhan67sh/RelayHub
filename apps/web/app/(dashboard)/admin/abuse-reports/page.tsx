"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { AbuseReportOut } from "@/lib/types";
import { Card, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

export default function AbuseReportsPage() {
  const [reports, setReports] = useState<AbuseReportOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string | null>("open");

  async function load() {
    setReports(null);
    try {
      const qs = filter ? `?status=${filter}` : "";
      const data = await api.get<AbuseReportOut[]>(`/v1/admin/abuse-reports${qs}`);
      setReports(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load abuse reports");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function handleResolve(id: string, status: string) {
    const notes = status === "resolved" ? prompt("Resolution notes (optional):") ?? "" : null;
    try {
      await api.patch(`/v1/admin/abuse-reports/${id}`, { status, resolution_notes: notes });
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to update report");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Abuse Reports</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Flagged organizations awaiting review.</p>
      </div>

      <div className="flex gap-1.5">
        {[null, "open", "investigating", "resolved", "dismissed"].map((s) => (
          <button
            key={s ?? "all"}
            onClick={() => setFilter(s)}
            className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors ${
              filter === s ? "bg-signal-amber text-white" : "bg-graphite-100 text-graphite-600 dark:bg-graphite-800 dark:text-graphite-400"
            }`}
          >
            {s ?? "All"}
          </button>
        ))}
      </div>

      <Card>
        {reports === null ? (
          <TableSkeleton rows={4} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : reports.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="No reports" description="No abuse reports match this filter." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Reason</th>
                <th className="px-4 py-2 font-medium">Reported by</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Reported</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="max-w-[320px] px-4 py-2.5 text-graphite-950 dark:text-graphite-50">{r.reason}</td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {r.reported_by_user_id ? (
                      <span className="font-mono text-[11px]">{r.reported_by_user_id.slice(0, 8)}</span>
                    ) : (
                      <span className="text-graphite-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={r.status === "open" ? "red" : r.status === "investigating" ? "amber" : "neutral"}>{r.status}</Badge>
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2.5">
                    {(r.status === "open" || r.status === "investigating") && (
                      <div className="flex justify-end gap-1.5">
                        {r.status === "open" && (
                          <Button size="sm" variant="secondary" onClick={() => handleResolve(r.id, "investigating")}>
                            Investigate
                          </Button>
                        )}
                        <Button size="sm" variant="secondary" onClick={() => handleResolve(r.id, "resolved")}>
                          Resolve
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => handleResolve(r.id, "dismissed")}>
                          Dismiss
                        </Button>
                      </div>
                    )}
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
