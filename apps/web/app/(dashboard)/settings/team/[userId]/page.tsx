"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ui/toast";
import type { MemberOut } from "@/lib/types";
import { MEMBER_ROLES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";

export default function MemberDetailPage() {
  const params = useParams<{ userId: string }>();
  const router = useRouter();
  const { me } = useAuth();
  const toast = useToast();
  const canManage = me?.role === "owner" || me?.role === "admin";

  const [members, setMembers] = useState<MemberOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removeOpen, setRemoveOpen] = useState(false);

  async function load() {
    try {
      const data = await api.get<MemberOut[]>("/v1/org/members");
      setMembers(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load member");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const member = members?.find((m) => m.user_id === params.userId) ?? null;
  const invitedBy = member?.invited_by_user_id ? members?.find((m) => m.user_id === member.invited_by_user_id) : null;

  async function handleRoleChange(role: string) {
    if (!member) return;
    try {
      await api.patch(`/v1/org/members/${member.user_id}`, { role });
      await load();
      toast.success("Role updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update role");
    }
  }

  async function handleRemove() {
    if (!member) return;
    try {
      await api.delete(`/v1/org/members/${member.user_id}`);
      toast.success(`${member.full_name} removed from the organization`);
      router.push("/settings/team");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to remove member");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Link href="/settings/team" className="flex w-fit items-center gap-1.5 text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to team
      </Link>

      {members === null ? (
        <Card>
          <CardBody className="flex flex-col gap-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-4 w-32" />
          </CardBody>
        </Card>
      ) : error ? (
        <Card>
          <CardBody className="text-center text-xs text-signal-red">{error}</CardBody>
        </Card>
      ) : !member ? (
        <Card>
          <CardBody className="text-center text-xs text-graphite-600 dark:text-graphite-400">Member not found.</CardBody>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-signal-amber text-sm font-semibold text-white">
                {member.full_name[0]?.toUpperCase() ?? "?"}
              </div>
              <div>
                <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{member.full_name}</h1>
                <p className="text-xs text-graphite-600 dark:text-graphite-400">{member.email}</p>
              </div>
            </div>
            {canManage && member.user_id !== me?.user.id && (
              <Button variant="danger" size="sm" onClick={() => setRemoveOpen(true)}>
                <Trash2 className="h-3.5 w-3.5" />
                Remove from organization
              </Button>
            )}
          </div>

          <Card>
            <CardHeader>
              <h2 className="text-xs font-semibold text-graphite-950 dark:text-graphite-50">Details</h2>
            </CardHeader>
            <CardBody className="flex flex-col gap-3 text-xs">
              <DetailRow label="Role">
                {canManage && member.user_id !== me?.user.id ? (
                  <select
                    value={member.role}
                    onChange={(e) => handleRoleChange(e.target.value)}
                    className="rounded border border-graphite-200 bg-white px-1.5 py-0.5 text-xs dark:border-graphite-700 dark:bg-graphite-900"
                  >
                    {MEMBER_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Badge tone="neutral">{member.role}</Badge>
                )}
              </DetailRow>
              <DetailRow label="Joined">{new Date(member.joined_at).toLocaleString()}</DetailRow>
              <DetailRow label="Accepted">{member.accepted_at ? new Date(member.accepted_at).toLocaleString() : "—"}</DetailRow>
              <DetailRow label="Invited by">{invitedBy ? `${invitedBy.full_name} (${invitedBy.email})` : member.invited_by_user_id ? "—" : "Organization owner"}</DetailRow>
            </CardBody>
          </Card>

          <ConfirmDialog
            open={removeOpen}
            onClose={() => setRemoveOpen(false)}
            onConfirm={handleRemove}
            title="Remove member"
            description={`Remove ${member.full_name} from ${me?.organization.name}? They'll lose access immediately.`}
            confirmLabel="Remove"
            danger
          />
        </>
      )}
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-graphite-50 pb-2.5 last:border-0 last:pb-0 dark:border-graphite-800/60">
      <span className="text-graphite-500">{label}</span>
      <span className="text-graphite-950 dark:text-graphite-50">{children}</span>
    </div>
  );
}
