"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { AnalyticsSummary, EventTypeVolume, EndpointHealthOut } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [byType, setByType] = useState<EventTypeVolume[] | null>(null);
  const [health, setHealth] = useState<EndpointHealthOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<AnalyticsSummary>("/v1/analytics/summary"),
      api.get<EventTypeVolume[]>("/v1/analytics/events-by-type"),
      api.get<EndpointHealthOut[]>("/v1/analytics/endpoint-health"),
    ])
      .then(([s, t, h]) => {
        setSummary(s);
        setByType(t);
        setHealth(h);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Analytics</h1>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiCard label="Latency p50" value={summary?.latency_p50_ms != null ? Math.round(summary.latency_p50_ms) : "—"} suffix="ms" />
        <KpiCard label="Latency p95" value={summary?.latency_p95_ms != null ? Math.round(summary.latency_p95_ms) : "—"} suffix="ms" />
        <KpiCard label="Latency p99" value={summary?.latency_p99_ms != null ? Math.round(summary.latency_p99_ms) : "—"} suffix="ms" />
        <KpiCard
          label="Success rate"
          value={summary?.success_rate != null ? `${(summary.success_rate * 100).toFixed(1)}%` : "—"}
          tone="green"
        />
        <KpiCard
          label="Failure rate"
          value={summary?.failure_rate != null ? `${(summary.failure_rate * 100).toFixed(1)}%` : "—"}
          tone={summary?.failure_rate ? "red" : undefined}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Volume by event type</h2>
          </CardHeader>
          <CardBody className="p-0">
            {byType === null ? (
              <div className="p-4">
                <Skeleton className="h-32 w-full" />
              </div>
            ) : byType.length === 0 ? (
              <div className="p-6 text-center text-xs text-graphite-500">No events published yet.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <tbody>
                  {byType.map((row) => {
                    const max = byType[0]?.count || 1;
                    const pct = (row.count / max) * 100;
                    return (
                      <tr key={row.event_type} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                        <td className="w-1/2 px-4 py-2 font-mono text-graphite-950 dark:text-graphite-50">{row.event_type}</td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-graphite-100 dark:bg-graphite-800">
                              <div className="h-full bg-signal-amber" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="tabular w-10 text-right text-graphite-600 dark:text-graphite-400">{row.count}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Endpoint health</h2>
          </CardHeader>
          <CardBody className="p-0">
            {health === null ? (
              <div className="p-4">
                <Skeleton className="h-32 w-full" />
              </div>
            ) : health.length === 0 ? (
              <div className="p-6 text-center text-xs text-graphite-500">No endpoints yet.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <tbody>
                  {health.map((ep) => (
                    <tr key={ep.endpoint_id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                      <td className="px-4 py-2 text-graphite-950 dark:text-graphite-50">{ep.name}</td>
                      <td className="px-4 py-2">
                        <StatusDot color={statusToSignalColor(ep.health_status)} label={ep.health_status} />
                      </td>
                      <td className="tabular px-4 py-2 text-right text-graphite-600 dark:text-graphite-400">
                        {ep.consecutive_failure_count > 0 ? `${ep.consecutive_failure_count} failures` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
