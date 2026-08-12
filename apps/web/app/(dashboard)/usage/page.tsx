"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { UsageSummary, SubscriptionOut } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.get<UsageSummary>("/v1/billing/usage"), api.get<SubscriptionOut>("/v1/billing/subscription")])
      .then(([u, s]) => {
        setUsage(u);
        setSubscription(s);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load usage"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!usage || !subscription) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const periodStart = new Date(usage.period_start).toLocaleDateString();
  const periodEnd = new Date(usage.period_end).toLocaleDateString();

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Usage</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Current billing period: {periodStart} – {periodEnd} ({subscription.plan.name} plan)
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <UsageCard
          label="Deliveries"
          current={usage.delivery_count}
          max={usage.max_deliveries_per_month}
          overageAllowed={subscription.plan.allow_overage}
        />
        <UsageCard label="Endpoints" current={usage.endpoint_count} max={usage.max_endpoints} overageAllowed={false} />
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Plan limits</h2>
        </CardHeader>
        <CardBody className="flex flex-col gap-2 text-xs">
          <Row label="Log retention" value={`${subscription.plan.log_retention_days} days`} />
          <Row label="Rate limit" value={`${subscription.plan.rate_limit_per_minute}/min · ${subscription.plan.rate_limit_per_hour}/hr · ${subscription.plan.rate_limit_per_day}/day`} />
          <Row label="Overage allowed" value={subscription.plan.allow_overage ? "Yes" : "No"} />
        </CardBody>
      </Card>
    </div>
  );
}

function UsageCard({
  label,
  current,
  max,
  overageAllowed,
}: {
  label: string;
  current: number;
  max: number | null;
  overageAllowed: boolean;
}) {
  const pct = max ? Math.min(100, (current / max) * 100) : 0;
  const overLimit = max != null && current >= max;
  const color = overLimit ? (overageAllowed ? "bg-signal-amber" : "bg-signal-red") : pct >= 80 ? "bg-signal-amber" : "bg-signal-green";

  return (
    <Card>
      <CardBody className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-graphite-600 dark:text-graphite-400">{label}</span>
          <span className="tabular text-sm font-semibold text-graphite-950 dark:text-graphite-50">
            {current.toLocaleString()}
            {max != null && <span className="font-normal text-graphite-500"> / {max.toLocaleString()}</span>}
            {max == null && <span className="font-normal text-graphite-500"> / unlimited</span>}
          </span>
        </div>
        {max != null && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-graphite-100 dark:bg-graphite-800">
            <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
          </div>
        )}
        {overLimit && (
          <p className="text-xs text-graphite-500">
            {overageAllowed ? "Over plan limit -- tracked for overage, not blocked." : "Limit reached. Upgrade to continue."}
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-graphite-50 py-1.5 last:border-0 dark:border-graphite-800/60">
      <span className="text-graphite-600 dark:text-graphite-400">{label}</span>
      <span className="font-medium text-graphite-950 dark:text-graphite-50">{value}</span>
    </div>
  );
}
