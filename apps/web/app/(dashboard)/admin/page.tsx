"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { SystemHealthOut, BillingOverviewOut } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { StatusDot } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";

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

      <div className="flex items-center gap-2 rounded border border-graphite-200 bg-graphite-50 px-3 py-2 text-xs text-graphite-600 dark:border-graphite-800 dark:bg-graphite-800/40 dark:text-graphite-400">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
        Worker registry / live process health isn&apos;t tracked yet (no heartbeat table exists) -- what&apos;s shown
        below is real database and queue-depth data only.
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
