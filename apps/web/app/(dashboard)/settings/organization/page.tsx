"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardBody } from "@/components/ui/card";

export default function OrganizationSettingsPage() {
  const { me, refetchMe } = useAuth();
  const [name, setName] = useState(me?.organization.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const canManage = me?.role === "owner" || me?.role === "admin";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setLoading(true);
    try {
      await api.patch("/v1/org", { name });
      await refetchMe();
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update organization");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Organization</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">General settings for your organization.</p>
      </div>

      <Card className="max-w-md">
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">General</h2>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Input label="Organization name" required value={name} onChange={(e) => setName(e.target.value)} disabled={!canManage} />
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Slug</span>
              <span className="font-mono text-xs text-graphite-500">{me?.organization.slug}</span>
            </div>
            {error && <p className="text-xs text-signal-red">{error}</p>}
            {success && <p className="text-xs text-signal-green">Organization updated.</p>}
            {canManage && (
              <Button type="submit" size="sm" loading={loading} className="self-start">
                Save changes
              </Button>
            )}
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
