"use client";

import { useEffect, useState } from "react";
import { Building2, Ban, Play, LogIn } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { AdminOrganizationOut } from "@/lib/types";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function AdminOrganizationsPage() {
  const [orgs, setOrgs] = useState<AdminOrganizationOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<AdminOrganizationOut | null>(null);
  const [impersonateResult, setImpersonateResult] = useState<{ email: string; token: string } | null>(null);

  async function load() {
    try {
      const data = await api.get<AdminOrganizationOut[]>("/v1/admin/organizations");
      setOrgs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load organizations");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleUnsuspend(id: string) {
    try {
      await api.post(`/v1/admin/organizations/${id}/unsuspend`);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to unsuspend organization");
    }
  }

  async function handleImpersonate(org: AdminOrganizationOut) {
    if (!confirm(`Impersonate the owner of "${org.name}"? This action is logged to the audit trail.`)) return;
    try {
      const result = await api.post<{ access_token: string; impersonated_user_email: string; expires_in: number }>(
        `/v1/admin/organizations/${org.id}/impersonate`
      );
      setImpersonateResult({ email: result.impersonated_user_email, token: result.access_token });
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to impersonate");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Organizations</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">All organizations on the platform.</p>
      </div>

      <Card>
        {orgs === null ? (
          <TableSkeleton rows={6} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : orgs.length === 0 ? (
          <EmptyState icon={Building2} title="No organizations" description="No organizations have registered yet." />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Organization</th>
                <th className="px-4 py-2 font-medium">Plan</th>
                <th className="px-4 py-2 font-medium">Members</th>
                <th className="px-4 py-2 font-medium">Endpoints</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {orgs.map((org) => (
                <tr key={org.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-graphite-950 dark:text-graphite-50">{org.name}</div>
                    <div className="font-mono text-[11px] text-graphite-500">{org.slug}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone="neutral">{org.plan_tier ?? "—"}</Badge>
                  </td>
                  <td className="tabular px-4 py-2.5">{org.member_count}</td>
                  <td className="tabular px-4 py-2.5">{org.endpoint_count}</td>
                  <td className="px-4 py-2.5">
                    <StatusDot color={org.is_suspended ? "red" : "green"} label={org.is_suspended ? "Suspended" : "Active"} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => handleImpersonate(org)} className="rounded p-1.5 text-graphite-500 hover:bg-graphite-100 dark:hover:bg-graphite-800" title="Impersonate owner">
                        <LogIn className="h-3.5 w-3.5" />
                      </button>
                      {org.is_suspended ? (
                        <button onClick={() => handleUnsuspend(org.id)} className="rounded p-1.5 text-graphite-500 hover:bg-signal-green-soft hover:text-signal-green" title="Unsuspend">
                          <Play className="h-3.5 w-3.5" />
                        </button>
                      ) : (
                        <button onClick={() => setSuspendTarget(org)} className="rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red" title="Suspend">
                          <Ban className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <SuspendModal org={suspendTarget} onClose={() => setSuspendTarget(null)} onSuspended={() => { setSuspendTarget(null); load(); }} />
      <ImpersonateResultModal result={impersonateResult} onClose={() => setImpersonateResult(null)} />
    </div>
  );
}

function SuspendModal({ org, onClose, onSuspended }: { org: AdminOrganizationOut | null; onClose: () => void; onSuspended: () => void }) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setLoading(true);
    setError(null);
    try {
      await api.post(`/v1/admin/organizations/${org.id}/suspend`, { reason });
      setReason("");
      onSuspended();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to suspend organization");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={!!org} onClose={onClose} title={`Suspend ${org?.name ?? ""}`}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input label="Reason" required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. repeated ToS violations" />
        {error && <p className="text-xs text-signal-red">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="danger" size="sm" loading={loading}>
            Suspend
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ImpersonateResultModal({ result, onClose }: { result: { email: string; token: string } | null; onClose: () => void }) {
  return (
    <Modal open={!!result} onClose={onClose} title="Impersonation token issued">
      {result && (
        <div className="flex flex-col gap-3 text-xs">
          <p className="text-signal-red">
            This grants a 5-minute session as <strong>{result.email}</strong>. This action was logged to the audit trail.
          </p>
          <div className="rounded border border-graphite-200 bg-graphite-50 p-2.5 font-mono text-[11px] dark:border-graphite-700 dark:bg-graphite-800">
            {result.token}
          </div>
          <p className="text-graphite-600 dark:text-graphite-400">
            Paste this token as a Bearer token to act as this user for the next 5 minutes.
          </p>
        </div>
      )}
    </Modal>
  );
}
