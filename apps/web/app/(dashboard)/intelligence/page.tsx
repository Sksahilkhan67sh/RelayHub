"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-client";
import type { AnomalyOut, EndpointHealthSnapshotOut, IncidentOut } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton, TableSkeleton } from "@/components/ui/skeleton";

export default function IntelligencePage() {
  const [health, setHealth] = useState<EndpointHealthSnapshotOut[] | null>(null);
  const [incidents, setIncidents] = useState<IncidentOut[] | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<EndpointHealthSnapshotOut[]>("/v1/insights/intelligence/health"),
      api.get<IncidentOut[]>("/v1/insights/intelligence/incidents"),
      api.get<AnomalyOut[]>("/v1/insights/intelligence/anomalies"),
    ])
      .then(([h, i, a]) => {
        setHealth(h);
        setIncidents(i);
        setAnomalies(a);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load intelligence data"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  const activeIncidents = incidents?.filter((i) => i.status !== "resolved") ?? [];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Intelligence</h1>
        <p className="mt-0.5 text-xs text-graphite-500 dark:text-graphite-400">
          Automated health analysis, anomaly detection, and root cause analysis derived from your delivery data.
        </p>
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Endpoint health</h2>
        {health === null ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardBody>
                  <Skeleton className="h-16 w-full" />
                </CardBody>
              </Card>
            ))}
          </div>
        ) : health.length === 0 ? (
          <Card>
            <CardBody className="text-center text-xs text-graphite-500">
              No health data yet. Snapshots are generated automatically as delivery attempts accumulate.
            </CardBody>
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {health.map((h) => (
              <HealthCard key={h.id} snapshot={h} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
          Active incidents {activeIncidents.length > 0 && <span className="text-graphite-400">({activeIncidents.length})</span>}
        </h2>
        <Card>
          <CardBody className="p-0">
            {incidents === null ? (
              <TableSkeleton rows={3} cols={4} />
            ) : activeIncidents.length === 0 ? (
              <div className="p-6 text-center text-xs text-graphite-500">No active incidents. Everything looks healthy.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Title</th>
                    <th className="px-4 py-2 font-medium">Category</th>
                    <th className="px-4 py-2 font-medium">Severity</th>
                    <th className="px-4 py-2 font-medium">Last signal</th>
                  </tr>
                </thead>
                <tbody>
                  {activeIncidents.map((incident) => (
                    <tr
                      key={incident.id}
                      className="cursor-pointer border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-900 dark:hover:bg-graphite-800/50"
                    >
                      <td className="px-4 py-2.5">
                        <Link href={`/intelligence/${incident.id}`} className="flex items-center gap-2">
                          <StatusDot color={statusToSignalColor(incident.status)} label={incident.status} />
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <Link href={`/intelligence/${incident.id}`} className="font-medium text-graphite-900 dark:text-graphite-100">
                          {incident.title}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {incident.failure_category.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-2.5">
                        <SeverityBadge severity={incident.severity} />
                      </td>
                      <td className="px-4 py-2.5 text-graphite-500">{new Date(incident.last_signal_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Recent anomalies</h2>
        <Card>
          <CardBody className="p-0">
            {anomalies === null ? (
              <TableSkeleton rows={3} cols={4} />
            ) : anomalies.length === 0 ? (
              <div className="p-6 text-center text-xs text-graphite-500">No anomalies detected recently.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                    <th className="px-4 py-2 font-medium">Metric</th>
                    <th className="px-4 py-2 font-medium">Direction</th>
                    <th className="px-4 py-2 font-medium">Observed</th>
                    <th className="px-4 py-2 font-medium">Baseline</th>
                    <th className="px-4 py-2 font-medium">Confidence</th>
                    <th className="px-4 py-2 font-medium">Observed at</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalies.slice(0, 20).map((a) => (
                    <tr key={a.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-900">
                      <td className="px-4 py-2.5 font-medium text-graphite-900 dark:text-graphite-100">
                        {a.metric.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge tone={a.direction === "spike" || a.direction === "regression" ? "red" : "green"}>
                          {a.direction}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 tabular text-graphite-700 dark:text-graphite-300">
                        {formatMetricValue(a.metric, a.observed_value)}
                      </td>
                      <td className="px-4 py-2.5 tabular text-graphite-500">{formatMetricValue(a.metric, a.baseline_value)}</td>
                      <td className="px-4 py-2.5 tabular text-graphite-500">{(a.confidence * 100).toFixed(0)}%</td>
                      <td className="px-4 py-2.5 text-graphite-500">{new Date(a.observed_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}

function HealthCard({ snapshot }: { snapshot: EndpointHealthSnapshotOut }) {
  return (
    <Card>
      <CardBody className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <StatusDot color={statusToSignalColor(snapshot.status)} label={snapshot.status} />
          {snapshot.confidence > 0 && (
            <span className="text-[10px] text-graphite-400">{(snapshot.confidence * 100).toFixed(0)}% confidence</span>
          )}
        </div>
        <span className="tabular text-xl font-semibold text-graphite-950 dark:text-graphite-50">
          {snapshot.health_score != null ? snapshot.health_score.toFixed(0) : "—"}
          <span className="ml-0.5 text-sm font-normal text-graphite-500">/100</span>
        </span>
        <span className="text-[10px] text-graphite-500">
          {snapshot.sample_size} attempts · {new Date(snapshot.window_end).toLocaleTimeString()}
        </span>
      </CardBody>
    </Card>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "critical" ? "red" : severity === "warning" ? "amber" : "neutral";
  return <Badge tone={tone}>{severity}</Badge>;
}

function formatMetricValue(metric: string, value: number): string {
  if (metric === "latency") return `${value.toFixed(0)}ms`;
  return `${(value * 100).toFixed(1)}%`;
}
