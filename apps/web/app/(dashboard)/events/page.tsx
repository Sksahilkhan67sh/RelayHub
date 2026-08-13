"use client";

import React, { useEffect, useState, type FormEvent } from "react";
import { Zap, Send, ChevronDown, ChevronUp } from "lucide-react";
import { api, apiFetch, ApiError } from "@/lib/api-client";
import type { EventOut, EndpointOut } from "@/lib/types";
import { BUILT_IN_EVENT_TYPES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

export default function EventsPage() {
  const [events, setEvents] = useState<EventOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testerOpen, setTesterOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<EventOut[]>("/v1/events");
      setEvents(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load events");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Events</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Events published to RelayHub and their matched deliveries.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={() => setTesterOpen((v) => !v)}>
          <Send className="h-3.5 w-3.5" />
          Publish event tester
          {testerOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </Button>
      </div>

      {testerOpen && <PublishTester onPublished={load} />}

      <Card>
        {events === null ? (
          <TableSkeleton />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : events.length === 0 ? (
          <EmptyState icon={Zap} title="No events published yet" description="Publish an event using the tester above or from your backend." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Event type</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Deliveries</th>
                <th className="px-4 py-2 font-medium">Published</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <React.Fragment key={ev.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === ev.id ? null : ev.id)}
                    className="cursor-pointer border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40"
                  >
                    <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{ev.event}</td>
                    <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{ev.environment}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1">
                        {ev.delivery_jobs.length === 0 ? (
                          <span className="text-graphite-400">No matching endpoints</span>
                        ) : (
                          ev.delivery_jobs.map((j) => <StatusDot key={j.id} color={statusToSignalColor(j.status)} />)
                        )}
                      </div>
                    </td>
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {new Date(ev.created_at).toLocaleString()}
                    </td>
                  </tr>
                  {expandedId === ev.id && (
                    <tr className="border-b border-graphite-50 bg-graphite-50 dark:border-graphite-800/60 dark:bg-graphite-800/30">
                      <td colSpan={4} className="px-4 py-3">
                        <pre className="overflow-x-auto font-mono text-[11px] text-graphite-700 dark:text-graphite-300">
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function PublishTester({ onPublished }: { onPublished: () => void }) {
  const [apiKey, setApiKey] = useState("");
  const [eventType, setEventType] = useState<string>(BUILT_IN_EVENT_TYPES[0]);
  const [payload, setPayload] = useState('{\n  "example": "value"\n}');
  const [environment, setEnvironment] = useState("test");
  const [endpoints, setEndpoints] = useState<EndpointOut[] | null>(null);
  const [endpointsError, setEndpointsError] = useState<string | null>(null);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get<EndpointOut[]>("/v1/endpoints")
      .then(setEndpoints)
      .catch((err) => setEndpointsError(err instanceof ApiError ? err.message : "Failed to load endpoints"));
  }, []);

  const endpointsForEnvironment = (endpoints ?? []).filter((ep) => ep.environment === environment);

  function toggleEndpoint(id: string) {
    setSelectedEndpointIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setResult(null);

    let parsedPayload: unknown;
    try {
      parsedPayload = JSON.parse(payload);
    } catch {
      setResult({ ok: false, message: "Payload must be valid JSON" });
      return;
    }

    setLoading(true);
    try {
      await apiFetch("/v1/events", {
        method: "POST",
        skipAuth: true, // the Event Publishing API uses an API key, not the dashboard JWT
        headers: { "X-RelayHub-Api-Key": apiKey },
        body: {
          event: eventType,
          payload: parsedPayload,
          environment,
          // Omit entirely (rather than sending an empty array) when nothing is picked,
          // so the backend falls back to its normal "deliver to every subscribed
          // endpoint" behavior instead of interpreting an empty list as "deliver to nobody".
          ...(selectedEndpointIds.size > 0 ? { endpoint_ids: Array.from(selectedEndpointIds) } : {}),
        },
      });
      setResult({ ok: true, message: "Event published successfully." });
      onPublished();
    } catch (err) {
      setResult({ ok: false, message: err instanceof ApiError ? err.message : "Failed to publish event" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Publish a test event</h2>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <p className="text-xs text-graphite-600 dark:text-graphite-400">
          This calls the real Event Publishing API using an API key you paste in below -- the dashboard never has access
          to your raw key after creation (by design), so it can&apos;t publish on your behalf automatically. Grab one from{" "}
          <Badge tone="neutral">API Keys</Badge>.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Input
            label="API key"
            required
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="rh_test_..."
            type="password"
          />
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Event type</label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900"
              >
                {BUILT_IN_EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Environment</label>
              <select
                value={environment}
                onChange={(e) => {
                  setEnvironment(e.target.value);
                  setSelectedEndpointIds(new Set()); // selections from the old environment don't apply anymore
                }}
                className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900"
              >
                <option value="test">test</option>
                <option value="live">live</option>
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Payload (JSON)</label>
            <textarea
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
              rows={5}
              className="rounded border border-graphite-200 bg-white p-2.5 font-mono text-xs dark:border-graphite-700 dark:bg-graphite-900"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
              Deliver to
              <span className="ml-1.5 font-normal text-graphite-500">
                {selectedEndpointIds.size === 0
                  ? "(all endpoints subscribed to this event type -- default)"
                  : `(only the ${selectedEndpointIds.size} selected below)`}
              </span>
            </label>
            {endpointsError ? (
              <p className="text-xs text-signal-red">{endpointsError}</p>
            ) : endpoints === null ? (
              <p className="text-xs text-graphite-500">Loading endpoints…</p>
            ) : endpointsForEnvironment.length === 0 ? (
              <p className="text-xs text-graphite-500">No endpoints in the &quot;{environment}&quot; environment yet.</p>
            ) : (
              <div className="flex flex-col gap-1 rounded border border-graphite-200 p-2 dark:border-graphite-700">
                {endpointsForEnvironment.map((ep) => (
                  <label key={ep.id} className="flex items-center gap-2 rounded px-1.5 py-1 text-xs hover:bg-graphite-50 dark:hover:bg-graphite-800/60">
                    <input
                      type="checkbox"
                      checked={selectedEndpointIds.has(ep.id)}
                      onChange={() => toggleEndpoint(ep.id)}
                      className="h-3.5 w-3.5 accent-signal-amber"
                    />
                    <span className="font-medium text-graphite-800 dark:text-graphite-200">{ep.name}</span>
                    <span className="truncate text-graphite-500">{ep.url}</span>
                    {!ep.is_active && <span className="ml-auto shrink-0 text-graphite-400">inactive</span>}
                  </label>
                ))}
              </div>
            )}
          </div>
          {result && <p className={`text-xs ${result.ok ? "text-signal-green" : "text-signal-red"}`}>{result.message}</p>}
          <Button type="submit" size="sm" loading={loading} className="self-end">
            <Send className="h-3.5 w-3.5" />
            Publish event
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
