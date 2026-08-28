"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { NotificationOut, UnreadCountOut } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000;

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  async function refreshUnreadCount() {
    try {
      const data = await api.get<UnreadCountOut>("/v1/notifications/unread-count");
      setUnreadCount(data.unread_count);
    } catch {
      // Silent -- a failed background poll shouldn't surface an error to the user.
    }
  }

  async function loadNotifications() {
    setError(null);
    try {
      const data = await api.get<NotificationOut[]>("/v1/notifications?limit=20");
      setNotifications(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load notifications");
    }
  }

  useEffect(() => {
    refreshUnreadCount();
    const interval = setInterval(refreshUnreadCount, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (open) loadNotifications();
  }, [open]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleMarkRead(id: string) {
    try {
      await api.post(`/v1/notifications/${id}/read`);
      setNotifications((prev) => prev?.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)) ?? null);
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // Non-critical UI action -- leave state as-is on failure.
    }
  }

  async function handleMarkAllRead() {
    try {
      await api.post("/v1/notifications/read-all");
      setNotifications((prev) => prev?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? null);
      setUnreadCount(0);
    } catch {
      // Non-critical UI action -- leave state as-is on failure.
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-7 w-7 items-center justify-center rounded border border-graphite-200 text-graphite-600 hover:bg-graphite-50 dark:border-graphite-700 dark:text-graphite-400 dark:hover:bg-graphite-800"
        aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : "Notifications"}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Bell className="h-3.5 w-3.5" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-signal-red px-1 text-[10px] font-semibold text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-9 z-20 w-80 rounded border border-graphite-100 bg-white shadow-lg dark:border-graphite-800 dark:bg-graphite-900"
        >
          <div className="flex items-center justify-between border-b border-graphite-100 px-3 py-2 dark:border-graphite-800">
            <span className="text-xs font-semibold text-graphite-950 dark:text-graphite-50">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-[11px] font-medium text-signal-amber hover:underline">
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {notifications === null ? (
              <div className="px-3 py-6 text-center text-xs text-graphite-500">Loading…</div>
            ) : error ? (
              <div className="px-3 py-6 text-center text-xs text-signal-red">{error}</div>
            ) : notifications.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-graphite-500">You&apos;re all caught up.</div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => !n.read_at && handleMarkRead(n.id)}
                  className={`block w-full border-b border-graphite-50 px-3 py-2.5 text-left last:border-0 dark:border-graphite-800/60 ${
                    n.read_at ? "" : "bg-signal-amber-soft/40 dark:bg-signal-amber/10"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-medium text-graphite-950 dark:text-graphite-50">{n.title}</p>
                    {!n.read_at && <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-amber" />}
                  </div>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-graphite-600 dark:text-graphite-400">{n.body}</p>
                  <p className="mt-1 text-[10px] text-graphite-400">{timeAgo(n.created_at)}</p>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
