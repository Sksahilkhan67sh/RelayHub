"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, XCircle, Loader2, Circle } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryJobOut } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";
import { deriveDeliveryAttemptState, STATUS_LABELS, STATUS_COLORS, formatCountdown } from "@/lib/delivery-attempts";
import { RealtimeIndicator } from "@/components/dashboard/realtime-indicator";
import { useDeliveryRealtimeStream, type DeliveryRealtimeEvent } from "@/lib/realtime";

// Fallback only (spec Step 17: "if realtime connection fails, the application
// must remain usable"). While the SSE stream is `live`, this page relies on
// pushed `delivery.updated` events instead of polling; this interval only
// takes over when the realtime connection is down, so a Redis/SSE outage
// degrades to the same periodic-refetch behavior this page always had, rather
// than going silent.
const FALLBACK_POLL_INTERVAL_MS = 5000;

export default function DeliveryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<DeliveryJobOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const loadRef = useRef<() => Promise<DeliveryJobOut | null>>();

  async function load() {
    try {
      const data = await api.get<DeliveryJobOut>(`/v1/deliveries/${params.id}`);
      setJob(data);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load delivery");
      return null;
    }
  }
  loadRef.current = load;

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  // Live status updates for exactly this job -- ignores events for any other
  // delivery job (this stream is org-scoped, not job-scoped, so events for
  // sibling deliveries do arrive here and are correctly dropped).
  const handleRealtimeEvent = useCallback(
    (event: DeliveryRealtimeEvent) => {
      if (event.delivery_job_id !== params.id) return;
      // A delivery.updated event doesn't carry the full DeliveryAttempt row
      // (response headers/body, duration, worker id, destination ip) that
      // the attempt-history timeline needs -- only the job-level fields. So a
      // live event still triggers one authoritative refetch, but it's now
      // event-driven (fires the instant a transition happens) rather than
      // time-driven (fires up to 5s late).
      loadRef.current?.();
    },
    [params.id]
  );

  const handleReconciliationNeeded = useCallback(() => {
    loadRef.current?.();
  }, []);

  const realtimeState = useDeliveryRealtimeStream(handleRealtimeEvent, handleReconciliationNeeded);

  // Fallback polling: only while the job is in flight AND the realtime stream
  // is not currently live/connecting (spec Step 17 -- realtime failure must
  // never make the page stop reflecting reality, so this is the safety net,
  // not the primary mechanism). Stops entirely once the job reaches a
  // terminal state, same as before this phase.
  useEffect(() => {
    if (!job) return;
    const state = deriveDeliveryAttemptState(job);
    const realtimeCovering = realtimeState === "live" || realtimeState === "connecting";
    if (state.isTerminal || realtimeCovering) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(load, FALLBACK_POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status, job?.attempt_number, realtimeState]);

  // Local 1-second ticker purely to reformat the "in 42 seconds" countdown text
  // between backend refetches -- no network call, just re-rendering the same
  // next_attempt_at against the current clock.
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const state = deriveDeliveryAttemptState(job);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push("/deliveries")}
          className="flex w-fit items-center gap-1 text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to deliveries
        </button>
        <RealtimeIndicator state={realtimeState} />
      </div>

      <div className="flex items-center gap-2">
        <h1 className="font-mono text-sm font-semibold text-graphite-950 dark:text-graphite-50">{job.event_type}</h1>
        <StatusDot color={statusToSignalColor(job.status)} label={job.status} />
      </div>

      <DeliverySummary job={job} now={now} />

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Event payload</h2>
        </CardHeader>
        <CardBody>
          <pre className="overflow-x-auto rounded bg-graphite-50 p-3 font-mono text-xs text-graphite-800 dark:bg-graphite-800 dark:text-graphite-200">
            {JSON.stringify(job.payload, null, 2)}
          </pre>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
            Attempt history ({state.currentAttempt} / {state.maxAttempts})
          </h2>
        </CardHeader>
        <CardBody className="flex flex-col gap-3 p-0">
          <AttemptTimeline job={job} state={state} />
        </CardBody>
      </Card>
    </div>
  );
}

function DeliverySummary({ job, now }: { job: DeliveryJobOut; now: number }) {
  const state = deriveDeliveryAttemptState(job);
  const label = STATUS_LABELS[state.derivedStatus];
  const color = STATUS_COLORS[state.derivedStatus];

  return (
    <Card>
      <CardBody className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <StatusDot color={color} pulse={state.derivedStatus === "delivering" || state.derivedStatus === "retrying"} size="md" />
          <span className="text-sm font-semibold uppercase tracking-wide text-graphite-950 dark:text-graphite-50">{label}</span>
          {state.derivedStatus === "delivering" && (
            <span className="text-xs text-graphite-500">Attempt {state.currentAttempt} in progress</span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <SummaryStat label="Attempt" value={`${state.currentAttempt} / ${state.maxAttempts}`} />
          <SummaryStat label="Attempts remaining" value={String(state.attemptsRemaining)} />
          <SummaryStat
            label="Next retry"
            value={state.hasScheduledRetry && state.nextAttemptAt ? formatCountdown(state.nextAttemptAt, now) : "—"}
          />
          <SummaryStat
            label="Next retry at"
            value={state.hasScheduledRetry && state.nextAttemptAt ? new Date(state.nextAttemptAt).toLocaleTimeString() : "—"}
          />
        </div>

        {state.derivedStatus === "dead_letter" && (
          <p className="text-xs text-graphite-500">Retry policy exhausted after {state.maxAttempts} attempts. This job will not retry automatically -- see the Dead Letter Queue to replay it manually.</p>
        )}
        {state.derivedStatus === "failed" && !state.hasScheduledRetry && (
          <p className="text-xs text-graphite-500">Permanent failure -- no further attempts are scheduled.</p>
        )}
        {state.derivedStatus === "delivered" && (
          <p className="text-xs text-graphite-500">Delivered successfully. No further attempts will run.</p>
        )}
      </CardBody>
    </Card>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-graphite-500">{label}</p>
      <p className="tabular mt-0.5 text-lg font-semibold text-graphite-950 dark:text-graphite-50">{value}</p>
    </div>
  );
}

function AttemptTimeline({ job, state }: { job: DeliveryJobOut; state: ReturnType<typeof deriveDeliveryAttemptState> }) {
  const rows: React.ReactNode[] = [];

  for (const a of job.attempts) {
    const succeeded = a.error_category === "none" && a.http_status != null && a.http_status < 300;
    rows.push(
      <div key={a.id} className="border-b border-graphite-100 p-4 last:border-0 dark:border-graphite-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {succeeded ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-signal-green" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-signal-red" />
            )}
            <span className="tabular text-xs font-medium text-graphite-950 dark:text-graphite-50">Attempt {a.attempt_number}</span>
            {a.http_status && (
              <Badge tone={a.http_status < 300 ? "green" : a.http_status < 500 ? "amber" : "red"}>HTTP {a.http_status}</Badge>
            )}
            {a.error_category !== "none" && <Badge tone="red">{a.error_category}</Badge>}
            {!succeeded && a.attempt_number < state.maxAttempts && <span className="text-[11px] text-graphite-500">Retry scheduled</span>}
          </div>
          <span className="tabular text-xs text-graphite-500">{a.duration_ms}ms</span>
        </div>
        <div className="mt-1 flex gap-4 text-xs text-graphite-500">
          <span>{new Date(a.started_at).toLocaleString()}</span>
          <span className="font-mono">{a.worker_id}</span>
          {a.destination_ip && <span className="font-mono">{a.destination_ip}</span>}
        </div>
        {a.error_message && <p className="mt-1.5 text-xs text-signal-red">{a.error_message}</p>}
        {a.response_body_truncated && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50">
              Response body
            </summary>
            <pre className="mt-1.5 overflow-x-auto rounded bg-graphite-50 p-2.5 font-mono text-[11px] text-graphite-700 dark:bg-graphite-800 dark:text-graphite-300">
              {a.response_body_truncated}
            </pre>
          </details>
        )}
        {Object.keys(a.response_headers).length > 0 && (
          <details className="mt-1.5">
            <summary className="cursor-pointer text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50">
              Response headers
            </summary>
            <pre className="mt-1.5 overflow-x-auto rounded bg-graphite-50 p-2.5 font-mono text-[11px] text-graphite-700 dark:bg-graphite-800 dark:text-graphite-300">
              {JSON.stringify(a.response_headers, null, 2)}
            </pre>
          </details>
        )}
      </div>
    );
  }

  // The currently-executing attempt has no DeliveryAttempt row yet (the backend only
  // creates one once the attempt finishes -- see executor.py), so it's rendered from
  // job.attempt_number/status directly rather than from the attempts array.
  if (state.derivedStatus === "delivering") {
    rows.push(
      <div key="in-progress" className="flex items-center gap-2 border-b border-graphite-100 p-4 last:border-0 dark:border-graphite-800">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-signal-amber" />
        <span className="tabular text-xs font-medium text-graphite-950 dark:text-graphite-50">Attempt {state.currentAttempt}</span>
        <span className="text-[11px] text-graphite-500">In progress</span>
      </div>
    );
  }

  // Scheduled-but-not-yet-run slots: rendered only while a real retry is genuinely
  // scheduled (state.hasScheduledRetry, backed by a real next_attempt_at from the
  // API), and only up to the real max_attempts -- never fabricated beyond what the
  // backend has actually committed to attempting.
  if (state.hasScheduledRetry) {
    const nextSlot = state.currentAttempt + 1;
    for (let slot = nextSlot; slot <= state.maxAttempts; slot++) {
      rows.push(
        <div key={`scheduled-${slot}`} className="flex items-center gap-2 border-b border-graphite-100 p-4 last:border-0 dark:border-graphite-800">
          <Circle className="h-3.5 w-3.5 text-graphite-300 dark:text-graphite-700" />
          <span className="tabular text-xs font-medium text-graphite-500">Attempt {slot}</span>
          <span className="text-[11px] text-graphite-400">Scheduled</span>
          {slot === nextSlot && state.nextAttemptAt && (
            <span className="tabular text-[11px] text-graphite-400">{new Date(state.nextAttemptAt).toLocaleTimeString()}</span>
          )}
        </div>
      );
    }
  }

  if (rows.length === 0) {
    return <div className="p-6 text-center text-xs text-graphite-500">No attempts recorded yet.</div>;
  }

  return <>{rows}</>;
}
