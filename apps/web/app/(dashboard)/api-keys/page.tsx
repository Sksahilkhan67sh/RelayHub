"use client";

import { useEffect, useState, type FormEvent } from "react";
import { KeyRound, Plus, Copy, Check, RotateCw, Ban } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { ApiKeyOut, ApiKeyCreatedOut, ApiKeyEnvironment } from "@/lib/types";
import { API_KEY_SCOPES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [revealSecret, setRevealSecret] = useState<ApiKeyCreatedOut | null>(null);

  async function load() {
    try {
      const data = await api.get<ApiKeyOut[]>("/v1/api-keys");
      setKeys(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load API keys");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this API key? Requests using it will start failing immediately.")) return;
    try {
      await api.post(`/v1/api-keys/${id}/revoke`, { reason: "Revoked from dashboard" });
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to revoke key");
    }
  }

  async function handleRotate(id: string) {
    if (!confirm("Rotate this key? The old secret will stop working immediately and a new one will be shown once.")) return;
    try {
      const rotated = await api.post<ApiKeyCreatedOut>(`/v1/api-keys/${id}/rotate`);
      setRevealSecret(rotated);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to rotate key");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">API Keys</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
            Live and test keys for authenticating the Event Publishing API.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          Create key
        </Button>
      </div>

      <Card>
        {keys === null ? (
          <TableSkeleton />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : keys.length === 0 ? (
          <EmptyState
            icon={KeyRound}
            title="No API keys yet"
            description="Create a key to start publishing events from your backend."
            actionLabel="Create key"
            onAction={() => setCreateOpen(true)}
          />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Environment</th>
                <th className="px-4 py-2 font-medium">Key</th>
                <th className="px-4 py-2 font-medium">Scopes</th>
                <th className="px-4 py-2 font-medium">Last used</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5 font-medium text-graphite-950 dark:text-graphite-50">{key.name}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={key.environment === "live" ? "green" : "neutral"}>{key.environment}</Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-graphite-600 dark:text-graphite-400">{key.masked_key}</td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{key.scopes.join(", ")}</td>
                  <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                    {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={key.is_active ? "green" : "gray"} label={key.is_active ? "Active" : "Revoked"} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      {key.is_active && (
                        <>
                          <button
                            onClick={() => handleRotate(key.id)}
                            className="rounded p-1.5 text-graphite-500 hover:bg-graphite-100 dark:hover:bg-graphite-800"
                            title="Rotate key"
                          >
                            <RotateCw className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleRevoke(key.id)}
                            className="rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red"
                            title="Revoke key"
                          >
                            <Ban className="h-3.5 w-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <CreateApiKeyModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          setCreateOpen(false);
          setRevealSecret(created);
          load();
        }}
      />

      <RevealSecretModal secret={revealSecret} onClose={() => setRevealSecret(null)} />
    </div>
  );
}

function CreateApiKeyModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (key: ApiKeyCreatedOut) => void;
}) {
  const [name, setName] = useState("");
  const [environment, setEnvironment] = useState<ApiKeyEnvironment>("test");
  const [scopes, setScopes] = useState<string[]>(["events:write", "events:read"]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function toggleScope(scope: string) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const created = await api.post<ApiKeyCreatedOut>("/v1/api-keys", { name, environment, scopes });
      setName("");
      setScopes(["events:write", "events:read"]);
      onCreated(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create key");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create API key">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Production backend" />

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
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Scopes</label>
          <div className="flex flex-wrap gap-1.5">
            {API_KEY_SCOPES.map((scope) => (
              <button
                type="button"
                key={scope}
                onClick={() => toggleScope(scope)}
                className={`rounded-sm px-2 py-1 font-mono text-[11px] transition-colors ${
                  scopes.includes(scope)
                    ? "bg-signal-amber text-white"
                    : "bg-graphite-100 text-graphite-600 dark:bg-graphite-800 dark:text-graphite-400"
                }`}
              >
                {scope}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-xs text-signal-red">{error}</p>}

        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading} disabled={scopes.length === 0}>
            Create key
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RevealSecretModal({ secret, onClose }: { secret: ApiKeyCreatedOut | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!secret) return;
    await navigator.clipboard.writeText(secret.key);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Modal open={!!secret} onClose={onClose} title="API key created">
      {secret && (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-signal-red">
            This is the only time the full key will be shown. Copy it now and store it securely.
          </p>
          <div className="flex items-center gap-2 rounded border border-graphite-200 bg-graphite-50 px-3 py-2 dark:border-graphite-700 dark:bg-graphite-800">
            <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs text-graphite-950 dark:text-graphite-50">
              {secret.key}
            </code>
            <button onClick={handleCopy} className="shrink-0 rounded p-1 text-graphite-500 hover:bg-graphite-200 dark:hover:bg-graphite-700">
              {copied ? <Check className="h-3.5 w-3.5 text-signal-green" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
          <Button size="sm" onClick={onClose} className="self-end">
            Done
          </Button>
        </div>
      )}
    </Modal>
  );
}
