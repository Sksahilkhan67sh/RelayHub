"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Bell, Plus, Send, Trash2, History } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { AlertRuleOut, AlertEventOut } from "@/lib/types";
import { ALERT_CONDITION_TYPES, ALERT_CHANNELS, ALERT_SEVERITIES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRuleOut[] | null>(null);
  const [history, setHistory] = useState<AlertEventOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  async function load() {
    try {
      const [r, h] = await Promise.all([
        api.get<AlertRuleOut[]>("/v1/alerts/rules"),
        api.get<AlertEventOut[]>("/v1/alerts/history"),
      ]);
      setRules(r);
      setHistory(h);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alerts");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleToggle(rule: AlertRuleOut) {
    try {
      await api.patch(`/v1/alerts/rules/${rule.id}`, { is_enabled: !rule.is_enabled });
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to update rule");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this alert rule?")) return;
    try {
      await api.delete(`/v1/alerts/rules/${id}`);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to delete rule");
    }
  }

  async function handleTest(id: string) {
    try {
      const result = await api.post<{ delivery_status: string; delivery_error: string | null }>(`/v1/alerts/rules/${id}/test`);
      alert(
        result.delivery_status === "sent"
          ? "Test alert sent successfully."
          : `Test alert failed to send: ${result.delivery_error || "unknown error"}`
      );
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to send test alert");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Alerts</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Notification rules and delivery history.</p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          Create rule
        </Button>
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Alert rules</h2>
        </CardHeader>
        <CardBody className="p-0">
          {rules === null ? (
            <div className="p-4">
              <Skeleton className="h-24 w-full" />
            </div>
          ) : error ? (
            <div className="p-6 text-center text-xs text-signal-red">{error}</div>
          ) : rules.length === 0 ? (
            <EmptyState icon={Bell} title="No alert rules yet" description="Create a rule to get notified when something needs attention." actionLabel="Create rule" onAction={() => setCreateOpen(true)} />
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Condition</th>
                  <th className="px-4 py-2 font-medium">Severity</th>
                  <th className="px-4 py-2 font-medium">Channel</th>
                  <th className="px-4 py-2 font-medium">Enabled</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{rule.condition_type}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={rule.severity === "critical" ? "red" : rule.severity === "warning" ? "amber" : "neutral"}>
                        {rule.severity}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{rule.channel}</td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => handleToggle(rule)}>
                        <StatusDot color={rule.is_enabled ? "green" : "gray"} label={rule.is_enabled ? "On" : "Off"} />
                      </button>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => handleTest(rule.id)} className="rounded p-1.5 text-graphite-500 hover:bg-graphite-100 dark:hover:bg-graphite-800" title="Send test alert">
                          <Send className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => handleDelete(rule.id)} className="rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red" title="Delete">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Alert history</h2>
        </CardHeader>
        <CardBody className="p-0">
          {history === null ? (
            <div className="p-4">
              <Skeleton className="h-24 w-full" />
            </div>
          ) : history.length === 0 ? (
            <EmptyState icon={History} title="No alerts triggered yet" description="Triggered alerts will show up here, including throttled/suppressed ones." />
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Condition</th>
                  <th className="px-4 py-2 font-medium">Message</th>
                  <th className="px-4 py-2 font-medium">Delivery</th>
                  <th className="px-4 py-2 font-medium">Triggered</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{h.condition_type}</td>
                    <td className="max-w-[320px] truncate px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{h.message}</td>
                    <td className="px-4 py-2.5">
                      <StatusDot color={statusToSignalColor(h.delivery_status)} label={h.delivery_status} />
                    </td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {new Date(h.triggered_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      <CreateAlertRuleModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => { setCreateOpen(false); load(); }} />
    </div>
  );
}

function CreateAlertRuleModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [conditionType, setConditionType] = useState<string>(ALERT_CONDITION_TYPES[0]);
  const [severity, setSeverity] = useState<string>("warning");
  const [channel, setChannel] = useState<string>("webhook");
  const [channelConfigValue, setChannelConfigValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const configKey = channel === "webhook" ? "url" : channel === "email" ? "to_address" : "webhook_url";
  const configPlaceholder = channel === "webhook" ? "https://your-app.com/hooks/alerts" : channel === "email" ? "ops@yourapp.com" : "https://hooks.slack.com/...";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/v1/alerts/rules", {
        condition_type: conditionType,
        severity,
        channel,
        channel_config: { [configKey]: channelConfigValue },
      });
      setChannelConfigValue("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create rule");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create alert rule">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Condition</label>
          <select value={conditionType} onChange={(e) => setConditionType(e.target.value)} className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900">
            {ALERT_CONDITION_TYPES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Severity</label>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900">
            {ALERT_SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Channel</label>
          <select value={channel} onChange={(e) => setChannel(e.target.value)} className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900">
            {ALERT_CHANNELS.map((c) => (
              <option key={c} value={c} disabled={c === "sms"}>
                {c === "sms" ? "sms (not yet available)" : c}
              </option>
            ))}
          </select>
        </div>

        <Input label={configKey} required value={channelConfigValue} onChange={(e) => setChannelConfigValue(e.target.value)} placeholder={configPlaceholder} />

        {error && <p className="text-xs text-signal-red">{error}</p>}

        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            Create rule
          </Button>
        </div>
      </form>
    </Modal>
  );
}
