"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Flag, Plus, Settings2, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import type { AdminFeatureFlagOut, FeatureFlagOverrideOut, AdminOrganizationOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function FeatureFlagsPage() {
  const toast = useToast();
  const [flags, setFlags] = useState<AdminFeatureFlagOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [overridesFlag, setOverridesFlag] = useState<AdminFeatureFlagOut | null>(null);

  async function load() {
    try {
      const data = await api.get<AdminFeatureFlagOut[]>("/v1/admin/feature-flags");
      setFlags(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load feature flags");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleToggle(flag: AdminFeatureFlagOut) {
    try {
      await api.patch(`/v1/admin/feature-flags/${flag.key}`, { is_enabled_globally: !flag.is_enabled_globally });
      await load();
      toast.success(`${flag.key} is now ${!flag.is_enabled_globally ? "on" : "off"} globally`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update flag");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Feature Flags</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Global toggles, with per-organization overrides.</p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          Create flag
        </Button>
      </div>

      <Card>
        {flags === null ? (
          <TableSkeleton rows={4} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : flags.length === 0 ? (
          <EmptyState icon={Flag} title="No feature flags yet" description="Create a flag to gate a feature globally or per-organization." actionLabel="Create flag" onAction={() => setCreateOpen(true)} />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Key</th>
                <th className="px-4 py-2 font-medium">Description</th>
                <th className="px-4 py-2 font-medium">Enabled globally</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={f.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5 font-mono text-graphite-950 dark:text-graphite-50">{f.key}</td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{f.description || "—"}</td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => handleToggle(f)} aria-label={`Toggle ${f.key} globally`}>
                      <StatusDot color={f.is_enabled_globally ? "green" : "gray"} label={f.is_enabled_globally ? "On" : "Off"} />
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => setOverridesFlag(f)}
                      className="flex items-center gap-1 rounded border border-graphite-200 px-2 py-1 text-xs text-graphite-600 hover:bg-graphite-50 dark:border-graphite-700 dark:text-graphite-400 dark:hover:bg-graphite-800"
                    >
                      <Settings2 className="h-3 w-3" />
                      Overrides
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <CreateFlagModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => { setCreateOpen(false); load(); }} />

      {overridesFlag && <OverridesModal flag={overridesFlag} onClose={() => setOverridesFlag(null)} />}
    </div>
  );
}

function CreateFlagModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [key, setKey] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/v1/admin/feature-flags", { key, description, is_enabled_globally: false });
      setKey("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create flag");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create feature flag">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input label="Key" required value={key} onChange={(e) => setKey(e.target.value)} placeholder="new-analytics-ui" />
        <Input label="Description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this flag controls" />
        {error && <p className="text-xs text-signal-red">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            Create
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function OverridesModal({ flag, onClose }: { flag: AdminFeatureFlagOut; onClose: () => void }) {
  const toast = useToast();
  const [overrides, setOverrides] = useState<FeatureFlagOverrideOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [orgs, setOrgs] = useState<AdminOrganizationOut[] | null>(null);
  const [orgSearch, setOrgSearch] = useState("");
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [enableNew, setEnableNew] = useState(true);
  const [pendingChange, setPendingChange] = useState<{ organizationId: string; organizationName: string; isEnabled: boolean } | null>(null);

  async function load() {
    try {
      const [overridesData, orgsData] = await Promise.all([
        api.get<FeatureFlagOverrideOut[]>(`/v1/admin/feature-flags/${flag.key}/overrides`),
        orgs ?? api.get<AdminOrganizationOut[]>("/v1/admin/organizations?limit=200"),
      ]);
      setOverrides(overridesData);
      setOrgs(orgsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load overrides");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flag.key]);

  const overriddenOrgIds = useMemo(() => new Set((overrides ?? []).map((o) => o.organization_id)), [overrides]);

  const filteredOrgs = useMemo(() => {
    if (!orgs) return [];
    const q = orgSearch.trim().toLowerCase();
    return orgs
      .filter((o) => !overriddenOrgIds.has(o.id))
      .filter((o) => !q || o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q))
      .slice(0, 20);
  }, [orgs, orgSearch, overriddenOrgIds]);

  async function applyOverride(organizationId: string, isEnabled: boolean) {
    try {
      await api.post(`/v1/admin/feature-flags/${flag.key}/override`, { organization_id: organizationId, is_enabled: isEnabled });
      setPendingChange(null);
      setSelectedOrgId("");
      await load();
      toast.success(`Override saved`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save override");
    }
  }

  function requestAddOverride(e: FormEvent) {
    e.preventDefault();
    const org = orgs?.find((o) => o.id === selectedOrgId);
    if (!org) return;
    setPendingChange({ organizationId: org.id, organizationName: org.name, isEnabled: enableNew });
  }

  function requestToggle(override: FeatureFlagOverrideOut) {
    setPendingChange({ organizationId: override.organization_id, organizationName: override.organization_name, isEnabled: !override.is_enabled });
  }

  return (
    <>
      <Modal open onClose={onClose} title={`Overrides — ${flag.key}`} width="max-w-lg">
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="mb-1.5 text-xs font-semibold text-graphite-700 dark:text-graphite-200">Current overrides</h3>
            {error ? (
              <p className="text-xs text-signal-red">{error}</p>
            ) : overrides === null ? (
              <TableSkeleton rows={2} cols={2} />
            ) : overrides.length === 0 ? (
              <p className="text-xs text-graphite-500">No per-organization overrides yet -- every org follows the global toggle.</p>
            ) : (
              <div className="overflow-hidden rounded border border-graphite-100 dark:border-graphite-800">
                <table className="w-full text-left text-xs">
                  <tbody>
                    {overrides.map((o) => (
                      <tr key={o.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                        <td className="px-3 py-2 text-graphite-950 dark:text-graphite-50">{o.organization_name}</td>
                        <td className="px-3 py-2">
                          <button onClick={() => requestToggle(o)} aria-label={`Toggle override for ${o.organization_name}`}>
                            <StatusDot color={o.is_enabled ? "green" : "gray"} label={o.is_enabled ? "Enabled" : "Disabled"} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="border-t border-graphite-100 pt-3 dark:border-graphite-800">
            <h3 className="mb-1.5 text-xs font-semibold text-graphite-700 dark:text-graphite-200">Add an override</h3>
            <form onSubmit={requestAddOverride} className="flex flex-col gap-2.5">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-graphite-400" />
                <input
                  value={orgSearch}
                  onChange={(e) => setOrgSearch(e.target.value)}
                  placeholder="Search organizations"
                  aria-label="Search organizations"
                  className="h-8 w-full rounded border border-graphite-200 bg-white pl-8 pr-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
                />
              </div>
              <select
                value={selectedOrgId}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                required
                aria-label="Organization"
                className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900"
              >
                <option value="">Select an organization…</option>
                {filteredOrgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.slug})
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-3 text-xs">
                <label className="flex items-center gap-1.5">
                  <input type="radio" checked={enableNew} onChange={() => setEnableNew(true)} />
                  Enable
                </label>
                <label className="flex items-center gap-1.5">
                  <input type="radio" checked={!enableNew} onChange={() => setEnableNew(false)} />
                  Disable
                </label>
              </div>
              <div className="flex justify-end">
                <Button type="submit" size="sm" disabled={!selectedOrgId}>
                  Add override
                </Button>
              </div>
            </form>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!pendingChange}
        onClose={() => setPendingChange(null)}
        onConfirm={async () => {
          if (pendingChange) await applyOverride(pendingChange.organizationId, pendingChange.isEnabled);
        }}
        title={pendingChange?.isEnabled ? "Enable override" : "Disable override"}
        description={`${pendingChange?.isEnabled ? "Enable" : "Disable"} "${flag.key}" for ${pendingChange?.organizationName}? This overrides the global setting for that organization only.`}
        confirmLabel={pendingChange?.isEnabled ? "Enable" : "Disable"}
        danger={!pendingChange?.isEnabled}
      />
    </>
  );
}
