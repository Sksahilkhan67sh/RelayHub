"use client";

import { useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api-client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type RealtimeConnectionState = "connecting" | "live" | "reconnecting" | "offline";

/** Matches backend/app/modules/realtime/events.py's `emit_delivery_update` contract exactly. */
export interface DeliveryRealtimeEvent {
  type: "delivery.updated";
  delivery_job_id: string;
  event_id: string;
  endpoint_id: string;
  organization_id: string;
  status: "queued" | "processing" | "success" | "retrying" | "failed" | "dead_letter";
  attempt_number: number;
  max_attempts: number | null;
  http_status: number | null;
  error_category: string | null;
  queued_at: string;
  next_attempt_at: string | null;
  completed_at: string | null;
  timestamp: string;
}

const BASE_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;

/**
 * Subscribes to GET /v1/realtime/deliveries/stream for as long as the
 * component using it is mounted.
 *
 * Deliberately does NOT rely on the browser's native `EventSource`
 * auto-reconnect: that retries against the SAME URL it was constructed with,
 * but the access token embedded in that URL (query string, since
 * `EventSource` can't set an Authorization header) rotates every 15 minutes
 * (api-client.ts). Left to its own devices, `EventSource` would keep
 * retrying with an increasingly stale token forever after the first
 * rotation. Instead, every (re)connect here explicitly closes any existing
 * connection and opens a brand new `EventSource` against a freshly-read
 * `getAccessToken()`, with its own exponential backoff (spec Step 7: "do not
 * create aggressive reconnect loops").
 *
 * On every successful (re)connect -- including the very first one --
 * `onReconciliationNeeded` fires so the caller refetches the authoritative
 * REST state. SSE delivery isn't guaranteed (a Redis restart, a dropped
 * connection, or a backgrounded tab can all lose events silently), so the UI
 * must always be able to self-heal from the database via the existing REST
 * endpoints rather than trust the stream as the sole source of truth (spec
 * Step 8).
 */
export function useDeliveryRealtimeStream(
  onEvent: (event: DeliveryRealtimeEvent) => void,
  onReconciliationNeeded: () => void
): RealtimeConnectionState {
  const [state, setState] = useState<RealtimeConnectionState>("connecting");
  const onEventRef = useRef(onEvent);
  const onReconciliationRef = useRef(onReconciliationNeeded);
  onEventRef.current = onEvent;
  onReconciliationRef.current = onReconciliationNeeded;

  useEffect(() => {
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let cancelled = false;

    function scheduleReconnect() {
      if (cancelled) return;
      setState("reconnecting");
      const delay = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
      attempt += 1;
      reconnectTimer = setTimeout(connect, delay);
    }

    function connect() {
      if (cancelled) return;

      const token = getAccessToken();
      if (!token) {
        // Not authenticated (yet, or session ended) -- nothing to stream.
        // The surrounding page's own auth guard handles redirecting; this
        // hook just stays quietly offline rather than retrying forever.
        setState("offline");
        return;
      }

      setState((prev) => (prev === "live" ? prev : "connecting"));

      const url = `${API_BASE_URL}/v1/realtime/deliveries/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      source = es;

      es.addEventListener("delivery.updated", (rawEvent) => {
        try {
          const parsed = JSON.parse((rawEvent as MessageEvent).data) as DeliveryRealtimeEvent;
          onEventRef.current(parsed);
        } catch {
          // Malformed frame -- drop it rather than crash the stream handler;
          // the next reconciliation fetch (on the next reconnect) will still
          // catch up correctly regardless.
        }
      });

      es.onopen = () => {
        attempt = 0;
        setState("live");
        onReconciliationRef.current();
      };

      es.onerror = () => {
        es.close();
        source = null;
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (source) source.close();
    };
  }, []);

  return state;
}
