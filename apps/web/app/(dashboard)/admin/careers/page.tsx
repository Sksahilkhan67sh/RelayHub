"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Briefcase, Plus, Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import type { JobPostingOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function AdminCareersPage() {
  const toast = useToast();
  const [postings, setPostings] = useState<JobPostingOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingPosting, setEditingPosting] = useState<JobPostingOut | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<JobPostingOut | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<JobPostingOut[]>("/v1/admin/content/job-postings");
      setPostings(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load job postings");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function openCreate() {
    setEditingPosting(null);
    setEditorOpen(true);
  }

  function openEdit(posting: JobPostingOut) {
    setEditingPosting(posting);
    setEditorOpen(true);
  }

  async function handleToggleActive(posting: JobPostingOut) {
    try {
      await api.patch(`/v1/admin/content/job-postings/${posting.id}`, { is_active: !posting.is_active });
      await load();
      toast.success(posting.is_active ? "Posting hidden from careers page" : "Posting is now live on careers page");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update posting");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteError(null);
    try {
      await api.delete(`/v1/admin/content/job-postings/${deleteTarget.id}`);
      setDeleteTarget(null);
      await load();
      toast.success("Posting deleted");
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete posting");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Careers</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Open positions shown on relayhub.dev/careers. Inactive postings stay hidden from the public site.</p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5" />
          New posting
        </Button>
      </div>

      <Card>
        {postings === null ? (
          <TableSkeleton rows={4} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : postings.length === 0 ? (
          <EmptyState icon={Briefcase} title="No job postings yet" description="Add your first open position." actionLabel="New posting" onAction={openCreate} />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Team</th>
                <th className="px-4 py-2 font-medium">Location</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {postings.map((p) => (
                <tr key={p.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5 font-medium text-graphite-950 dark:text-graphite-50">{p.title}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone="neutral">{p.team}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{p.location}</td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => handleToggleActive(p)} aria-label={`Toggle active status for ${p.title}`}>
                      <StatusDot color={p.is_active ? "green" : "gray"} label={p.is_active ? "Active" : "Inactive"} />
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(p)}
                        title="Edit posting"
                        className="rounded p-1 text-graphite-400 hover:bg-graphite-100 hover:text-graphite-700 dark:hover:bg-graphite-800 dark:hover:text-graphite-200"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(p)}
                        title="Delete posting"
                        className="rounded p-1 text-graphite-400 hover:bg-signal-red-soft hover:text-signal-red"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <CareersEditorModal
        open={editorOpen}
        posting={editingPosting}
        onClose={() => setEditorOpen(false)}
        onSaved={() => {
          setEditorOpen(false);
          load();
        }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => {
          setDeleteTarget(null);
          setDeleteError(null);
        }}
        onConfirm={handleDelete}
        title="Delete job posting"
        description={
          `Delete "${deleteTarget?.title ?? "this posting"}"? This removes it from the public careers page immediately and can't be undone.` +
          (deleteError ? ` — ${deleteError}` : "")
        }
        confirmLabel="Delete"
        danger
      />
    </div>
  );
}

function CareersEditorModal({
  open,
  posting,
  onClose,
  onSaved,
}: {
  open: boolean;
  posting: JobPostingOut | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!posting;
  const [title, setTitle] = useState("");
  const [team, setTeam] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (posting) {
      setTitle(posting.title);
      setTeam(posting.team);
      setLocation(posting.location);
      setDescription(posting.description);
      setIsActive(posting.is_active);
    } else {
      setTitle("");
      setTeam("");
      setLocation("");
      setDescription("");
      setIsActive(true);
    }
    setError(null);
  }, [open, posting]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const payload = { title, team, location, description, is_active: isActive };
    try {
      if (isEdit && posting) {
        await api.patch(`/v1/admin/content/job-postings/${posting.id}`, payload);
      } else {
        await api.post("/v1/admin/content/job-postings", payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save posting");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Edit posting" : "New posting"}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Input label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Senior Backend Engineer" />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Team" required value={team} onChange={(e) => setTeam(e.target.value)} placeholder="Engineering" />
          <Input label="Location" required value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Remote (US/EU)" />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Description</label>
          <textarea
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Role summary, responsibilities, requirements..."
            className="rounded border border-graphite-200 bg-white p-2.5 text-xs leading-relaxed dark:border-graphite-700 dark:bg-graphite-900"
          />
        </div>
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active (visible on the public careers page)
        </label>
        {error && <p className="text-xs text-signal-red">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            {isEdit ? "Save changes" : "Create posting"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
