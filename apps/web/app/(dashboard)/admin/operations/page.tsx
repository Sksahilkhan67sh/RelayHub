"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryMetricsOut, QueueDepthOut, ForceActionResponse } from "@/lib/types";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// Admin-only operations UI, built entirely around existing backend routes
// (all already RBAC-gated server-side via require_platform_admin, and already
// covered by backend tests in tests/integration/test_admin.py):
//   GET  /v1/admin/delivery-metrics
//   GET  /v1/admin/queues
//   POST /v1/admin/delivery-jobs/{job_id}/force-retry
//   POST /v1/admin/delivery-jobs/{job_id}/force-cancel
// No new backend endpoints were added for this page.
export default function AdminOperationsPage() {
  const [metrics, setMetrics] = useState<DeliveryMetricsOut | null>(null);
  const [queues, setQueues] = useState<QueueDepthOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [jobId, setJobId] = useState("");
  const [actionResult, setActionResult] = useState<{ action: string; response: ForceActionResponse } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<"retry" | "cancel" | null>(null);

  async function load() {
    setLoadError(null);
    try {
      const [m, q] = await Promise.all([
        api.get<DeliveryMetricsOut>("/v1/admin/delivery-metrics"),
        api.get<QueueDepthOut>("/v1/admin/queues"),
      ]);
      setMetrics(m);
      setQueues(q);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load operations data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleForceAction(action: "retry" | "cancel") {
    const id = jobId.trim();
    if (!id) return;
    setPendingAction(action);
    setActionError(null);
    setActionResult(null);
    try {
      const response = await api.post<ForceActionResponse>(`/v1/admin/delivery-jobs/${id}/force-${action}`);
      setActionResult({ action, response });
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `Failed to force-${action} delivery job`);
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Operations</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Cross-organization delivery-pipeline metrics and manual job intervention.
        </p>
      </div>

      {loadError ? (
        <div className="rounded border border-signal-red/30 bg-signal-red/5 p-4 text-center text-xs text-signal-red">{loadError}</div>
      ) : !metrics || !queues ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Queue depth</h2>
            </CardHeader>
            <CardBody className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <KpiCard label="Queued" value={queues.queued} />
              <KpiCard label="Processing" value={queues.processing} />
              <KpiCard label="Retrying" value={queues.retrying} tone={queues.retrying ? "amber" : undefined} />
              <KpiCard label="Dead letter" value={queues.dead_letter} tone={queues.dead_letter ? "red" : undefined} />
              <KpiCard label="Succeeded (last hour)" value={queues.success_last_hour} />
              <KpiCard label="Failed (last hour)" value={queues.failed_last_hour} tone={queues.failed_last_hour ? "red" : undefined} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
                Delivery latency &amp; reliability ({Math.round(metrics.window_seconds / 60)}m window)
              </h2>
            </CardHeader>
            {metrics.sample_size === 0 ? (
              <CardBody className="py-6 text-center text-xs text-graphite-500">
                No delivery attempts in this window yet.
              </CardBody>
            ) : (
              <CardBody className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <KpiCard
                  label="Avg latency"
                  value={metrics.avg_delivery_latency_ms != null ? `${Math.round(metrics.avg_delivery_latency_ms)}ms` : "—"}
                />
                <KpiCard
                  label="p95 latency"
                  value={metrics.p95_delivery_latency_ms != null ? `${metrics.p95_delivery_latency_ms}ms` : "—"}
                />
                <KpiCard
                  label="Retry rate"
                  value={metrics.retry_rate != null ? `${(metrics.retry_rate * 100).toFixed(1)}%` : "—"}
                  tone={metrics.retry_rate && metrics.retry_rate > 0.1 ? "amber" : undefined}
                />
                <KpiCard
                  label="DLQ rate"
                  value={metrics.dlq_rate != null ? `${(metrics.dlq_rate * 100).toFixed(1)}%` : "—"}
                  tone={metrics.dlq_rate && metrics.dlq_rate > 0 ? "red" : undefined}
                />
                <KpiCard label="Stuck jobs" value={metrics.stuck_jobs_count} tone={metrics.stuck_jobs_count ? "red" : undefined} />
                <KpiCard label="Sample size" value={metrics.sample_size} />
              </CardBody>
            )}
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Force delivery job action</h2>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          <p className="text-xs text-graphite-600 dark:text-graphite-400">
            Manually retry or cancel a specific delivery job by ID. This is a platform-admin escape hatch for stuck
            jobs -- it acts on one job at a time and is logged to the audit trail.
          </p>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                label="Delivery job ID"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                placeholder="e.g. 5f2b1c3a-..."
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={!jobId.trim()}
              loading={pendingAction === "retry"}
              onClick={() => handleForceAction("retry")}
            >
              Force retry
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={!jobId.trim()}
              loading={pendingAction === "cancel"}
              onClick={() => handleForceAction("cancel")}
            >
              Force cancel
            </Button>
          </div>

          {actionError && <p className="text-xs text-signal-red">{actionError}</p>}
          {actionResult && (
            <p className="text-xs text-signal-green">
              Job {actionResult.response.id} {actionResult.action === "retry" ? "re-queued" : "cancelled"} -- new status:{" "}
              <span className="font-mono">{actionResult.response.status}</span>
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
