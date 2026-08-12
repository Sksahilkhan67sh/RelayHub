"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { AuditLogOut } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AuditLogOut[]>("/v1/audit-logs")
      .then(setLogs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load audit logs (admin role required)"));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Audit Logs</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          A record of sensitive actions taken in this organization -- key creation/rotation, member changes, endpoint
          changes, and more.
        </p>
      </div>

      <Card>
        {logs === null ? (
          <TableSkeleton />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : logs.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No audit entries yet" description="Actions like creating API keys or inviting members will show up here." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Resource</th>
                <th className="px-4 py-2 font-medium">IP address</th>
                <th className="px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{log.action}</td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {log.resource_type}
                    {log.resource_id && <span className="text-graphite-400"> #{log.resource_id.slice(0, 8)}</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-graphite-600 dark:text-graphite-400">{log.ip_address ?? "—"}</td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {new Date(log.created_at).toLocaleString()}
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
