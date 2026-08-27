"use client";

import { useEffect, useState } from "react";
import { ServerCog } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { SystemHealthOut, BillingOverviewOut } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { StatusDot } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

export default function AdminOverviewPage() {
  const [health, setHealth] = useState<SystemHealthOut | null>(null);
  const [billing, setBilling] = useState<BillingOverviewOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.get<SystemHealthOut>("/v1/admin/system-health"), api.get<BillingOverviewOut>("/v1/admin/billing-overview")])
      .then(([h, b]) => {
        setHealth(h);
        setBilling(b);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load admin overview"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!health || !billing) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Platform Admin</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Cross-organization system health and business metrics.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card>
          <CardBody className="flex flex-col gap-1">
            <span className="text-xs text-graphite-600 dark:text-graphite-400">Database</span>
            <StatusDot color={health.database_ok ? "green" : "red"} label={health.database_ok ? "Connected" : "Unreachable"} size="md" />
          </CardBody>
        </Card>
        <KpiCard label="Queued jobs" value={health.queue_depth.queued} />
        <KpiCard label="Retrying jobs" value={health.queue_depth.retrying} tone={health.queue_depth.retrying ? "amber" : undefined} />
        <KpiCard label="Dead letter jobs" value={health.queue_depth.dead_letter} tone={health.queue_depth.dead_letter ? "red" : undefined} />
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Worker fleet</h2>
        </CardHeader>
        {health.worker_health.workers.length === 0 ? (
          <EmptyState
            icon={ServerCog}
            title="No workers reporting"
            description="No Celery worker process has sent a heartbeat yet. Deliveries may not be processing -- check that a worker process is running and can reach the database."
          />
        ) : (
          <>
            <CardBody className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <KpiCard label="Healthy workers" value={health.worker_health.healthy_count} />
              <KpiCard
                label="Unhealthy workers"
                value={health.worker_health.unhealthy_count}
                tone={health.worker_health.unhealthy_count ? "red" : undefined}
              />
            </CardBody>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Worker</th>
                  <th className="px-4 py-2 font-medium">Host</th>
                  <th className="px-4 py-2 font-medium">PID</th>
                  <th className="px-4 py-2 font-medium">Last heartbeat</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {health.worker_health.workers.map((w) => (
                  <tr key={w.worker_id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{w.worker_id}</td>
                    <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{w.hostname}</td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{w.pid}</td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {new Date(w.last_heartbeat_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusDot color={w.healthy ? "green" : "red"} label={w.healthy ? "Healthy" : "Unhealthy"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Business overview</h2>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Organizations" value={billing.total_organizations} />
          <Stat label="MRR" value={`$${(billing.mrr_cents / 100).toLocaleString()}`} />
          <Stat label="Canceled this month" value={billing.canceled_this_month} />
          <Stat label="Past due" value={billing.past_due_count} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Organizations by plan tier</h2>
        </CardHeader>
        <CardBody className="flex flex-wrap gap-3">
          {Object.entries(billing.organizations_by_tier).map(([tier, count]) => (
            <div key={tier} className="flex items-center gap-2 rounded border border-graphite-100 px-3 py-1.5 dark:border-graphite-800">
              <span className="text-xs text-graphite-600 dark:text-graphite-400">{tier}</span>
              <span className="tabular text-xs font-semibold text-graphite-950 dark:text-graphite-50">{count}</span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-graphite-600 dark:text-graphite-400">{label}</span>
      <span className="tabular text-base font-semibold text-graphite-950 dark:text-graphite-50">{value}</span>
    </div>
  );
}
