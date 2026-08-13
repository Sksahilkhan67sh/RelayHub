"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, RotateCw, Ban, Play, Copy, Check, Send, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { EndpointOut, EndpointSecretOut, DeliveryLogEntryOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";

export default function EndpointDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [endpoint, setEndpoint] = useState<EndpointOut | null>(null);
  const [deliveries, setDeliveries] = useState<DeliveryLogEntryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rotatedSecret, setRotatedSecret] = useState<EndpointSecretOut | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    try {
      const [ep, logs] = await Promise.all([
        api.get<EndpointOut>(`/v1/endpoints/${params.id}`),
        api.get<DeliveryLogEntryOut[]>(`/v1/logs?endpoint_id=${params.id}&limit=10`),
      ]);
      setEndpoint(ep);
      setDeliveries(logs);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load endpoint");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function handleToggleActive() {
    if (!endpoint) return;
    const action = endpoint.is_active ? "disable" : "enable";
    if (!confirm(`${action === "disable" ? "Disable" : "Enable"} this endpoint?`)) return;
    try {
      await api.patch(`/v1/endpoints/${endpoint.id}`, { is_active: !endpoint.is_active });
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : `Failed to ${action} endpoint`);
    }
  }

  async function handleRotateSecret() {
    if (!endpoint) return;
    if (!confirm("Rotate the signing secret? The old secret stays valid for a grace period.")) return;
    try {
      const rotated = await api.post<EndpointSecretOut>(`/v1/endpoints/${endpoint.id}/rotate-secret`, { grace_period_hours: 24 });
      setRotatedSecret(rotated);
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to rotate secret");
    }
  }

  async function handleDelete() {
    if (!endpoint) return;
    if (
      !confirm(
        `Delete "${endpoint.name}"? Events will stop being delivered here immediately. Its past delivery history is kept for your records, but this endpoint itself can't be recovered.`
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      await api.delete(`/v1/endpoints/${endpoint.id}`);
      router.push("/endpoints");
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to delete endpoint");
      setDeleting(false);
    }
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!endpoint) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const recentAttempts = deliveries?.flatMap((d) => d.attempts) ?? [];
  const failureRate =
    recentAttempts.length > 0
      ? recentAttempts.filter((a) => a.error_category !== "none").length / recentAttempts.length
      : null;
  const avgLatency =
    recentAttempts.length > 0 ? recentAttempts.reduce((sum, a) => sum + a.duration_ms, 0) / recentAttempts.length : null;

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={() => router.push("/endpoints")}
        className="flex w-fit items-center gap-1 text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to endpoints
      </button>

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{endpoint.name}</h1>
            <Badge tone={endpoint.environment === "live" ? "green" : "neutral"}>{endpoint.environment}</Badge>
          </div>
          <p className="mt-0.5 font-mono text-xs text-graphite-600 dark:text-graphite-400">{endpoint.url}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled title="Sends a synthetic ping to verify connectivity -- backend endpoint not yet implemented">
            <Send className="h-3.5 w-3.5" />
            Test webhook
          </Button>
          <Button variant="secondary" size="sm" onClick={handleRotateSecret}>
            <RotateCw className="h-3.5 w-3.5" />
            Rotate secret
          </Button>
          <Button variant={endpoint.is_active ? "danger" : "primary"} size="sm" onClick={handleToggleActive}>
            {endpoint.is_active ? <Ban className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            {endpoint.is_active ? "Disable" : "Enable"}
          </Button>
          <Button variant="danger" size="sm" onClick={handleDelete} loading={deleting}>
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Status">
          <StatusDot color={endpoint.is_active ? "green" : "gray"} label={endpoint.is_active ? "Active" : "Disabled"} />
        </StatCard>
        <StatCard label="Health">
          <StatusDot color={statusToSignalColor(endpoint.health_status)} label={endpoint.health_status} />
        </StatCard>
        <StatCard label="Recent failure rate">
          <span className="tabular text-sm font-medium">{failureRate != null ? `${(failureRate * 100).toFixed(0)}%` : "—"}</span>
        </StatCard>
        <StatCard label="Avg latency (recent)">
          <span className="tabular text-sm font-medium">{avgLatency != null ? `${Math.round(avgLatency)}ms` : "—"}</span>
        </StatCard>
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Configuration</h2>
        </CardHeader>
        <CardBody className="flex flex-col gap-2 text-xs">
          <ConfigRow label="Timeout" value={`${endpoint.timeout_seconds}s`} />
          <ConfigRow
            label="Subscribed events"
            value={endpoint.subscribed_event_types.length === 0 ? "All events" : endpoint.subscribed_event_types.join(", ")}
          />
          <ConfigRow label="TLS verification" value={endpoint.tls_verification_enabled ? "Enabled" : "Disabled"} />
          <ConfigRow label="Max retry attempts" value={endpoint.max_retry_attempts != null ? String(endpoint.max_retry_attempts) : "Plan default"} />
          {endpoint.consecutive_failure_count > 0 && (
            <ConfigRow label="Consecutive failures" value={String(endpoint.consecutive_failure_count)} />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Recent deliveries</h2>
        </CardHeader>
        <CardBody className="p-0">
          {!deliveries || deliveries.length === 0 ? (
            <div className="p-6 text-center text-xs text-graphite-500">No deliveries to this endpoint yet.</div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Event</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Attempts</th>
                  <th className="px-4 py-2 font-medium">Queued</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((d) => (
                  <tr key={d.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{d.event_type}</td>
                    <td className="px-4 py-2.5">
                      <StatusDot color={statusToSignalColor(d.status)} label={d.status} />
                    </td>
                    <td className="tabular px-4 py-2.5">{d.attempt_number}</td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {new Date(d.queued_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      <RotatedSecretModal secret={rotatedSecret} onClose={() => setRotatedSecret(null)} />
    </div>
  );
}

function StatCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardBody className="flex flex-col gap-1">
        <span className="text-xs text-graphite-600 dark:text-graphite-400">{label}</span>
        {children}
      </CardBody>
    </Card>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-graphite-50 py-1.5 last:border-0 dark:border-graphite-800/60">
      <span className="text-graphite-600 dark:text-graphite-400">{label}</span>
      <span className="font-medium text-graphite-950 dark:text-graphite-50">{value}</span>
    </div>
  );
}

function RotatedSecretModal({ secret, onClose }: { secret: EndpointSecretOut | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!secret) return;
    await navigator.clipboard.writeText(secret.secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Modal open={!!secret} onClose={onClose} title="Signing secret rotated">
      {secret && (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-signal-red">This is the only time the new secret will be shown. Copy it now.</p>
          <div className="flex items-center gap-2 rounded border border-graphite-200 bg-graphite-50 px-3 py-2 dark:border-graphite-700 dark:bg-graphite-800">
            <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs">{secret.secret}</code>
            <button onClick={handleCopy} className="shrink-0 rounded p-1 text-graphite-500 hover:bg-graphite-200 dark:hover:bg-graphite-700">
              {copied ? <Check className="h-3.5 w-3.5 text-signal-green" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
          {secret.grace_period_ends_at && (
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              The previous secret remains valid until {new Date(secret.grace_period_ends_at).toLocaleString()}.
            </p>
          )}
          <Button size="sm" onClick={onClose} className="self-end">
            Done
          </Button>
        </div>
      )}
    </Modal>
  );
}
