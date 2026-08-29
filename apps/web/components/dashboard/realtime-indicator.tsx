import { StatusDot, type SignalColor } from "@/components/ui/status-dot";
import type { RealtimeConnectionState } from "@/lib/realtime";

const STATE_TO_COLOR: Record<RealtimeConnectionState, SignalColor> = {
  live: "green",
  connecting: "amber",
  reconnecting: "amber",
  offline: "gray",
};

const STATE_TO_LABEL: Record<RealtimeConnectionState, string> = {
  live: "Live",
  connecting: "Connecting…",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

/**
 * Small, deliberately non-noisy realtime connection indicator (spec Step 16:
 * "do not make the UI noisy"). Reuses the existing StatusDot amber/green/gray
 * signal-light language (components/ui/status-dot.tsx) instead of inventing a
 * new visual vocabulary for this one widget.
 */
export function RealtimeIndicator({ state }: { state: RealtimeConnectionState }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="text-graphite-500 dark:text-graphite-400">Realtime:</span>
      <StatusDot color={STATE_TO_COLOR[state]} pulse={state === "live"} label={STATE_TO_LABEL[state]} />
    </span>
  );
}
