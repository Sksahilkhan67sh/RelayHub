"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { AbuseReportOut } from "@/lib/types";
import { Card, Badge } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

function statusTone(status: string) {
  if (status === "open") return "red" as const;
  if (status === "investigating") return "amber" as const;
  return "neutral" as const;
}

export default function OrgAbuseReportsPage() {
  const [reports, setReports] = useState<AbuseReportOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AbuseReportOut[]>("/v1/org/abuse-reports")
      .then(setReports)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load abuse reports (admin role required)")
      );
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Abuse Reports</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Reports filed against your organization by our platform team, along with their current review status.
        </p>
      </div>

      <Card>
        {reports === null ? (
          <TableSkeleton rows={3} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : reports.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No reports"
            description="Your organization has no abuse reports on file."
          />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Reason</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Filed</th>
                <th className="px-4 py-2 font-medium">Resolution</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="max-w-[320px] px-4 py-2.5 text-graphite-950 dark:text-graphite-50">{r.reason}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                  </td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {r.resolution_notes ?? "—"}
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
