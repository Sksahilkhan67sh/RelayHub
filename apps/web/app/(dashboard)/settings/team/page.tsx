"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { Users, Plus, Trash2, Mail, XCircle, RefreshCw, ArrowUpDown, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ui/toast";
import type { MemberOut, InvitationOut, InvitationStatus } from "@/lib/types";
import { MEMBER_ROLES } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 8;

type SortKey = "full_name" | "role" | "joined_at";

const STATUS_TONE: Record<InvitationStatus, "amber" | "green" | "neutral" | "red"> = {
  pending: "amber",
  accepted: "green",
  revoked: "neutral",
  expired: "red",
};

export default function TeamSettingsPage() {
  const { me } = useAuth();
  const toast = useToast();
  const canManage = me?.role === "owner" || me?.role === "admin";

  const [tab, setTab] = useState<"members" | "invitations">("members");

  const [members, setMembers] = useState<MemberOut[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [memberSearch, setMemberSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("full_name");
  const [sortAsc, setSortAsc] = useState(true);
  const [memberPage, setMemberPage] = useState(0);

  const [invitations, setInvitations] = useState<InvitationOut[] | null>(null);
  const [invitationsError, setInvitationsError] = useState<string | null>(null);
  const [invitationSearch, setInvitationSearch] = useState("");
  const [invitationStatusFilter, setInvitationStatusFilter] = useState<InvitationStatus | "all">("pending");
  const [invitationPage, setInvitationPage] = useState(0);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<MemberOut | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<InvitationOut | null>(null);

  async function loadMembers() {
    try {
      const data = await api.get<MemberOut[]>("/v1/org/members");
      setMembers(data);
    } catch (err) {
      setMembersError(err instanceof ApiError ? err.message : "Failed to load team members");
    }
  }

  async function loadInvitations() {
    try {
      const data = await api.get<InvitationOut[]>("/v1/org/invitations");
      setInvitations(data);
    } catch (err) {
      setInvitationsError(err instanceof ApiError ? err.message : "Failed to load invitations");
    }
  }

  useEffect(() => {
    loadMembers();
    if (canManage) loadInvitations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage]);

  const filteredMembers = useMemo(() => {
    if (!members) return [];
    const q = memberSearch.trim().toLowerCase();
    let result = members.filter(
      (m) =>
        (roleFilter === "all" || m.role === roleFilter) &&
        (!q || m.full_name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q))
    );
    result = [...result].sort((a, b) => {
      const dir = sortAsc ? 1 : -1;
      if (sortKey === "joined_at") return (new Date(a.joined_at).getTime() - new Date(b.joined_at).getTime()) * dir;
      return a[sortKey].localeCompare(b[sortKey]) * dir;
    });
    return result;
  }, [members, memberSearch, roleFilter, sortKey, sortAsc]);

  const pagedMembers = filteredMembers.slice(memberPage * PAGE_SIZE, memberPage * PAGE_SIZE + PAGE_SIZE);

  const filteredInvitations = useMemo(() => {
    if (!invitations) return [];
    const q = invitationSearch.trim().toLowerCase();
    return invitations.filter(
      (inv) => (invitationStatusFilter === "all" || inv.status === invitationStatusFilter) && (!q || inv.email.toLowerCase().includes(q))
    );
  }, [invitations, invitationSearch, invitationStatusFilter]);

  const pagedInvitations = filteredInvitations.slice(invitationPage * PAGE_SIZE, invitationPage * PAGE_SIZE + PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    try {
      await api.patch(`/v1/org/members/${userId}`, { role });
      await loadMembers();
      toast.success("Role updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update role");
    }
  }

  async function handleRemoveMember() {
    if (!removeTarget) return;
    try {
      await api.delete(`/v1/org/members/${removeTarget.user_id}`);
      setRemoveTarget(null);
      await loadMembers();
      toast.success(`${removeTarget.full_name} removed from the organization`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to remove member");
    }
  }

  async function handleRevokeInvitation() {
    if (!revokeTarget) return;
    try {
      await api.post(`/v1/org/invitations/${revokeTarget.id}/revoke`);
      setRevokeTarget(null);
      await loadInvitations();
      toast.success(`Invitation to ${revokeTarget.email} revoked`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to revoke invitation");
    }
  }

  async function handleResendInvitation(inv: InvitationOut) {
    try {
      await api.post(`/v1/org/invitations/${inv.id}/resend`);
      await loadInvitations();
      toast.success(`Invitation resent to ${inv.email}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to resend invitation");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Team</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Members of {me?.organization.name}.</p>
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Invite member
          </Button>
        )}
      </div>

      {canManage && (
        <div className="flex gap-1 border-b border-graphite-100 dark:border-graphite-800" role="tablist">
          <TabButton active={tab === "members"} onClick={() => setTab("members")}>
            Members
          </TabButton>
          <TabButton active={tab === "invitations"} onClick={() => setTab("invitations")}>
            Pending Invitations
            {invitations && invitations.filter((i) => i.status === "pending").length > 0 && (
              <span className="ml-1.5 rounded-full bg-signal-amber-soft px-1.5 py-0 text-[10px] font-semibold text-[#8A5D1F]">
                {invitations.filter((i) => i.status === "pending").length}
              </span>
            )}
          </TabButton>
        </div>
      )}

      {tab === "members" || !canManage ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[180px] flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-graphite-400" />
              <input
                value={memberSearch}
                onChange={(e) => {
                  setMemberSearch(e.target.value);
                  setMemberPage(0);
                }}
                placeholder="Search by name or email"
                aria-label="Search members"
                className="h-8 w-full rounded border border-graphite-200 bg-white pl-8 pr-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setMemberPage(0);
              }}
              aria-label="Filter by role"
              className="h-8 rounded border border-graphite-200 bg-white px-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
            >
              <option value="all">All roles</option>
              {MEMBER_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <Card>
            {members === null ? (
              <TableSkeleton />
            ) : membersError ? (
              <div className="p-6 text-center text-xs text-signal-red">{membersError}</div>
            ) : filteredMembers.length === 0 ? (
              <EmptyState
                icon={Users}
                title={members.length === 0 ? "No members yet" : "No matching members"}
                description={
                  members.length === 0
                    ? "Invite teammates to collaborate on this organization."
                    : "Try a different search or role filter."
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                      <SortableHeader label="Name" active={sortKey === "full_name"} asc={sortAsc} onClick={() => toggleSort("full_name")} />
                      <th className="px-4 py-2 font-medium">Email</th>
                      <SortableHeader label="Role" active={sortKey === "role"} asc={sortAsc} onClick={() => toggleSort("role")} />
                      <SortableHeader label="Joined" active={sortKey === "joined_at"} asc={sortAsc} onClick={() => toggleSort("joined_at")} />
                      <th className="px-4 py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedMembers.map((m) => (
                      <tr key={m.user_id} className="border-b border-graphite-50 last:border-0 hover:bg-graphite-50 dark:border-graphite-800/60 dark:hover:bg-graphite-800/40">
                        <td className="px-4 py-2.5 font-medium text-graphite-950 dark:text-graphite-50">
                          <Link href={`/settings/team/${m.user_id}`} className="hover:text-signal-amber">
                            {m.full_name}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{m.email}</td>
                        <td className="px-4 py-2.5">
                          {canManage ? (
                            <select
                              value={m.role}
                              onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                              aria-label={`Role for ${m.full_name}`}
                              className="rounded border border-graphite-200 bg-white px-1.5 py-0.5 text-xs dark:border-graphite-700 dark:bg-graphite-900"
                            >
                              {MEMBER_ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <Badge tone="neutral">{m.role}</Badge>
                          )}
                        </td>
                        <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{new Date(m.joined_at).toLocaleDateString()}</td>
                        <td className="px-4 py-2.5">
                          {canManage && (
                            <button
                              onClick={() => setRemoveTarget(m)}
                              className="rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red"
                              aria-label={`Remove ${m.full_name}`}
                              title="Remove"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <PaginationFooter
                  offset={memberPage * PAGE_SIZE}
                  count={pagedMembers.length}
                  total={filteredMembers.length}
                  onPrev={() => setMemberPage((p) => Math.max(0, p - 1))}
                  onNext={() => setMemberPage((p) => p + 1)}
                />
              </div>
            )}
          </Card>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[180px] flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-graphite-400" />
              <input
                value={invitationSearch}
                onChange={(e) => {
                  setInvitationSearch(e.target.value);
                  setInvitationPage(0);
                }}
                placeholder="Search by email"
                aria-label="Search invitations"
                className="h-8 w-full rounded border border-graphite-200 bg-white pl-8 pr-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
              />
            </div>
            <select
              value={invitationStatusFilter}
              onChange={(e) => {
                setInvitationStatusFilter(e.target.value as InvitationStatus | "all");
                setInvitationPage(0);
              }}
              aria-label="Filter by status"
              className="h-8 rounded border border-graphite-200 bg-white px-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
            >
              <option value="all">All statuses</option>
              <option value="pending">Pending</option>
              <option value="accepted">Accepted</option>
              <option value="revoked">Revoked</option>
              <option value="expired">Expired</option>
            </select>
          </div>

          <Card>
            {invitations === null ? (
              <TableSkeleton />
            ) : invitationsError ? (
              <div className="p-6 text-center text-xs text-signal-red">{invitationsError}</div>
            ) : filteredInvitations.length === 0 ? (
              <EmptyState
                icon={Mail}
                title={invitations.length === 0 ? "No invitations yet" : "No matching invitations"}
                description={
                  invitations.length === 0
                    ? "Invite a teammate by email -- they'll get a link to join, account or not."
                    : "Try a different search or status filter."
                }
                actionLabel={invitations.length === 0 ? "Invite member" : undefined}
                onAction={invitations.length === 0 ? () => setInviteOpen(true) : undefined}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                      <th className="px-4 py-2 font-medium">Email</th>
                      <th className="px-4 py-2 font-medium">Role</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Sent</th>
                      <th className="px-4 py-2 font-medium">Expires</th>
                      <th className="px-4 py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedInvitations.map((inv) => (
                      <tr key={inv.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                        <td className="px-4 py-2.5 font-medium text-graphite-950 dark:text-graphite-50">{inv.email}</td>
                        <td className="px-4 py-2.5">
                          <Badge tone="neutral">{inv.role}</Badge>
                        </td>
                        <td className="px-4 py-2.5">
                          <Badge tone={STATUS_TONE[inv.status]}>{inv.status}</Badge>
                        </td>
                        <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{new Date(inv.created_at).toLocaleDateString()}</td>
                        <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{new Date(inv.expires_at).toLocaleDateString()}</td>
                        <td className="px-4 py-2.5">
                          {inv.status === "pending" && (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => handleResendInvitation(inv)}
                                className="flex items-center gap-1 rounded p-1.5 text-graphite-500 hover:bg-graphite-100 hover:text-graphite-950 dark:hover:bg-graphite-800 dark:hover:text-graphite-50"
                                aria-label={`Resend invitation to ${inv.email}`}
                                title="Resend"
                              >
                                <RefreshCw className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => setRevokeTarget(inv)}
                                className="flex items-center gap-1 rounded p-1.5 text-graphite-500 hover:bg-signal-red-soft hover:text-signal-red"
                                aria-label={`Revoke invitation to ${inv.email}`}
                                title="Revoke"
                              >
                                <XCircle className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <PaginationFooter
                  offset={invitationPage * PAGE_SIZE}
                  count={pagedInvitations.length}
                  total={filteredInvitations.length}
                  onPrev={() => setInvitationPage((p) => Math.max(0, p - 1))}
                  onNext={() => setInvitationPage((p) => p + 1)}
                />
              </div>
            )}
          </Card>
        </div>
      )}

      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvited={() => {
          setInviteOpen(false);
          loadInvitations();
          setTab("invitations");
          toast.success("Invitation sent");
        }}
      />

      <ConfirmDialog
        open={!!removeTarget}
        onClose={() => setRemoveTarget(null)}
        onConfirm={handleRemoveMember}
        title="Remove member"
        description={`Remove ${removeTarget?.full_name ?? "this member"} from ${me?.organization.name}? They'll lose access immediately.`}
        confirmLabel="Remove"
        danger
      />

      <ConfirmDialog
        open={!!revokeTarget}
        onClose={() => setRevokeTarget(null)}
        onConfirm={handleRevokeInvitation}
        title="Revoke invitation"
        description={`Revoke the invitation sent to ${revokeTarget?.email ?? "this address"}? The link they received will stop working.`}
        confirmLabel="Revoke"
        danger
      />
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`flex items-center border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
        active
          ? "border-signal-amber text-graphite-950 dark:text-graphite-50"
          : "border-transparent text-graphite-500 hover:text-graphite-800 dark:hover:text-graphite-200"
      }`}
    >
      {children}
    </button>
  );
}

function SortableHeader({ label, active, asc, onClick }: { label: string; active: boolean; asc: boolean; onClick: () => void }) {
  return (
    <th className="px-4 py-2 font-medium">
      <button onClick={onClick} className="flex items-center gap-1 hover:text-graphite-800 dark:hover:text-graphite-200">
        {label}
        <ArrowUpDown className={`h-3 w-3 ${active ? "text-graphite-700 dark:text-graphite-200" : "text-graphite-300 dark:text-graphite-600"}`} />
        {active && <span className="sr-only">{asc ? "ascending" : "descending"}</span>}
      </button>
    </th>
  );
}

function PaginationFooter({ offset, count, total, onPrev, onNext }: { offset: number; count: number; total: number; onPrev: () => void; onNext: () => void }) {
  return (
    <div className="flex items-center justify-between border-t border-graphite-100 px-4 py-2.5 dark:border-graphite-800">
      <span className="text-xs text-graphite-500">{total === 0 ? "0 results" : `Showing ${offset + 1}–${offset + count} of ${total}`}</span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={offset === 0} onClick={onPrev}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={offset + count >= total} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}

function InviteMemberModal({ open, onClose, onInvited }: { open: boolean; onClose: () => void; onInvited: () => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/v1/org/invitations", { email, role });
      setEmail("");
      onInvited();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send invitation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Invite member">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          hint="They'll get an email with a link to join -- no existing account required."
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Role</label>
          <select value={role} onChange={(e) => setRole(e.target.value)} className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900">
            {MEMBER_ROLES.filter((r) => r !== "owner").map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        {error && <p className="text-xs text-signal-red">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            Send invitation
          </Button>
        </div>
      </form>
    </Modal>
  );
}
