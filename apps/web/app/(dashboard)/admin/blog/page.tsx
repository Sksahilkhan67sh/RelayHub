"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Newspaper, Plus, Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import type { BlogPostOut, ContentStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, Badge } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";

export default function AdminBlogPage() {
  const toast = useToast();
  const [posts, setPosts] = useState<BlogPostOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingPost, setEditingPost] = useState<BlogPostOut | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BlogPostOut | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<BlogPostOut[]>("/v1/admin/content/blog-posts");
      setPosts(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load blog posts");
    }
  }

  useEffect(() => {
    load();
  }, []);

  function openCreate() {
    setEditingPost(null);
    setEditorOpen(true);
  }

  function openEdit(post: BlogPostOut) {
    setEditingPost(post);
    setEditorOpen(true);
  }

  async function handleTogglePublish(post: BlogPostOut) {
    const nextStatus: ContentStatus = post.status === "published" ? "draft" : "published";
    try {
      await api.patch(`/v1/admin/content/blog-posts/${post.id}`, { status: nextStatus });
      await load();
      toast.success(nextStatus === "published" ? "Post published" : "Post unpublished");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update post");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteError(null);
    try {
      await api.delete(`/v1/admin/content/blog-posts/${deleteTarget.id}`);
      setDeleteTarget(null);
      await load();
      toast.success("Post deleted");
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete post");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Blog</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Posts shown on relayhub.dev/blog. Drafts stay hidden from the public site until published.</p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5" />
          New post
        </Button>
      </div>

      <Card>
        {posts === null ? (
          <TableSkeleton rows={4} />
        ) : error ? (
          <div className="p-6 text-center text-xs text-signal-red">{error}</div>
        ) : posts.length === 0 ? (
          <EmptyState icon={Newspaper} title="No blog posts yet" description="Write your first post for the public blog." actionLabel="New post" onAction={openCreate} />
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Author</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {posts.map((p) => (
                <tr key={p.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-graphite-950 dark:text-graphite-50">{p.title}</p>
                    <p className="font-mono text-[11px] text-graphite-400">/blog/{p.slug}</p>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone="neutral">{p.category}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{p.author_name}</td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => handleTogglePublish(p)} aria-label={`Toggle publish status for ${p.title}`}>
                      <StatusDot color={p.status === "published" ? "green" : "gray"} label={p.status === "published" ? "Published" : "Draft"} />
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(p)}
                        title="Edit post"
                        className="rounded p-1 text-graphite-400 hover:bg-graphite-100 hover:text-graphite-700 dark:hover:bg-graphite-800 dark:hover:text-graphite-200"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(p)}
                        title="Delete post"
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

      <BlogEditorModal
        open={editorOpen}
        post={editingPost}
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
        title="Delete blog post"
        description={
          `Delete "${deleteTarget?.title ?? "this post"}"? This removes it from the public blog immediately and can't be undone.` +
          (deleteError ? ` — ${deleteError}` : "")
        }
        confirmLabel="Delete"
        danger
      />
    </div>
  );
}

function BlogEditorModal({
  open,
  post,
  onClose,
  onSaved,
}: {
  open: boolean;
  post: BlogPostOut | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!post;
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [category, setCategory] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [authorRole, setAuthorRole] = useState("");
  const [readMinutes, setReadMinutes] = useState(5);
  const [bodyText, setBodyText] = useState(""); // paragraphs separated by a blank line
  const [publishedAt, setPublishedAt] = useState("");
  const [status, setStatus] = useState<ContentStatus>("draft");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (post) {
      setSlug(post.slug);
      setTitle(post.title);
      setExcerpt(post.excerpt);
      setCategory(post.category);
      setAuthorName(post.author_name);
      setAuthorRole(post.author_role);
      setReadMinutes(post.read_minutes);
      setBodyText(post.body.join("\n\n"));
      setPublishedAt(post.published_at ?? "");
      setStatus(post.status);
    } else {
      setSlug("");
      setTitle("");
      setExcerpt("");
      setCategory("");
      setAuthorName("");
      setAuthorRole("");
      setReadMinutes(5);
      setBodyText("");
      setPublishedAt("");
      setStatus("draft");
    }
    setError(null);
  }, [open, post]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const body = bodyText
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean);
    const payload = {
      slug,
      title,
      excerpt,
      category,
      author_name: authorName,
      author_role: authorRole,
      read_minutes: readMinutes,
      body,
      status,
      published_at: publishedAt || null,
    };
    try {
      if (isEdit && post) {
        await api.patch(`/v1/admin/content/blog-posts/${post.id}`, payload);
      } else {
        await api.post("/v1/admin/content/blog-posts", payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save post");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Edit post" : "New post"} width="max-w-lg">
      <form onSubmit={handleSubmit} className="flex max-h-[70vh] flex-col gap-3 overflow-y-auto pr-1">
        <Input label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Why webhooks fail in production" />
        <Input
          label="Slug"
          required
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="why-webhooks-fail-in-production"
        />
        <p className="-mt-2 text-[11px] text-graphite-500">Lowercase letters, numbers, and hyphens only. Becomes /blog/{slug || "your-slug"}.</p>
        <Input label="Excerpt" required value={excerpt} onChange={(e) => setExcerpt(e.target.value)} placeholder="One or two sentences shown on the blog index" />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Category" required value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Engineering" />
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Read minutes</label>
            <input
              type="number"
              min={1}
              max={120}
              required
              value={readMinutes}
              onChange={(e) => setReadMinutes(Number(e.target.value))}
              className="h-9 rounded border border-graphite-200 bg-white px-2 text-sm dark:border-graphite-700 dark:bg-graphite-900"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Author name" required value={authorName} onChange={(e) => setAuthorName(e.target.value)} placeholder="Dana Whitfield" />
          <Input label="Author role" required value={authorRole} onChange={(e) => setAuthorRole(e.target.value)} placeholder="Engineering" />
        </div>
        <Input
          label="Display date (optional)"
          value={publishedAt}
          onChange={(e) => setPublishedAt(e.target.value)}
          placeholder="August 14, 2026"
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Body</label>
          <textarea
            required
            rows={10}
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            placeholder="Write each paragraph, separated by a blank line between paragraphs."
            className="rounded border border-graphite-200 bg-white p-2.5 text-xs leading-relaxed dark:border-graphite-700 dark:bg-graphite-900"
          />
          <p className="text-[11px] text-graphite-500">Separate paragraphs with a blank line -- each becomes its own paragraph on the post.</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={status === "draft"} onChange={() => setStatus("draft")} />
            Draft
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={status === "published"} onChange={() => setStatus("published")} />
            Published
          </label>
        </div>
        {error && <p className="text-xs text-signal-red">{error}</p>}
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            {isEdit ? "Save changes" : "Create post"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
