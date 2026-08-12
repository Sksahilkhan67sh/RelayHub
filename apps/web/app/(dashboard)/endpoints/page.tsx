"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Webhook, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { EndpointOut } from "@/lib/types";
import { BUILT_IN_EVENT_TYPES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

export default function EndpointsPage() {
  const [endpoints, setEndpoints] = useState<EndpointOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  async function load() {
    try {
      const data = await api.get<EndpointOut[]>("/v1/endpoints");
      setEndpoints(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load endpoints");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Endpoints</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Destinations that receive your webhook deliveries.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          Add endpoint
        </Button>
      </div>

      <Card>
        {endpoints === null ? (
          <TableSkeleton />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : endpoints.length === 0 ? (
          <EmptyState
            icon={Webhook}
            title="No endpoints yet"
            description="Add a destination URL to start receiving webhook deliveries."
            actionLabel="Add endpoint"
            onAction={() => setCreateOpen(true)}
          />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">URL</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Events</th>
                <th className="px-4 py-2 font-medium">Health</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((ep) => (
                <tr key={ep.id} className="border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40">
                  <td className="px-4 py-2.5">
                    <Link href={`/endpoints/${ep.id}`} className="font-medium text-graphite-950 hover:text-signal-amber dark:text-graphite-50">
                      {ep.name}
                    </Link>
                  </td>
                  <td className="max-w-[240px] truncate px-4 py-2.5 font-mono text-graphite-600 dark:text-graphite-400">{ep.url}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={ep.environment === "live" ? "green" : "neutral"}>{ep.environment}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {ep.subscribed_event_types.length === 0 ? "All events" : `${ep.subscribed_event_types.length} type(s)`}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={statusToSignalColor(ep.health_status)} label={ep.health_status} />
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={ep.is_active ? "green" : "gray"} label={ep.is_active ? "Active" : "Disabled"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <CreateEndpointModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => { setCreateOpen(false); load(); }} />
    </div>
  );
}

function CreateEndpointModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [environment, setEnvironment] = useState<"test" | "live">("test");
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function toggleEventType(type: string) {
    setEventTypes((prev) => (prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/v1/endpoints", { name, url, environment, subscribed_event_types: eventTypes });
      setName("");
      setUrl("");
      setEventTypes([]);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create endpoint");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add endpoint" width="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Order fulfillment service" />
        <Input
          label="URL"
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://api.yourapp.com/webhooks/relayhub"
          hint="Must be HTTPS in production. Private/internal IPs are blocked."
        />

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Environment</label>
          <div className="flex gap-2">
            {(["test", "live"] as const).map((env) => (
              <button
                type="button"
                key={env}
                onClick={() => setEnvironment(env)}
                className={`h-8 flex-1 rounded border text-xs font-medium transition-colors ${
                  environment === env
                    ? "border-signal-amber bg-signal-amber-soft text-[#8A5D1F]"
                    : "border-graphite-200 text-graphite-600 dark:border-graphite-700 dark:text-graphite-400"
                }`}
              >
                {env}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
            Subscribed events <span className="font-normal text-graphite-500">(none selected = all events)</span>
          </label>
          <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
            {BUILT_IN_EVENT_TYPES.map((type) => (
              <button
                type="button"
                key={type}
                onClick={() => toggleEventType(type)}
                className={`rounded-sm px-2 py-1 font-mono text-[11px] transition-colors ${
                  eventTypes.includes(type)
                    ? "bg-signal-amber text-white"
                    : "bg-graphite-100 text-graphite-600 dark:bg-graphite-800 dark:text-graphite-400"
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-xs text-signal-red">{error}</p>}

        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            Add endpoint
          </Button>
        </div>
      </form>
    </Modal>
  );
}
