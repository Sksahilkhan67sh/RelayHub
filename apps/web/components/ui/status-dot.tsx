import { cn } from "@/lib/cn";

export type SignalColor = "green" | "amber" | "red" | "gray";

const COLOR_CLASSES: Record<SignalColor, string> = {
  green: "bg-signal-green shadow-glow-green",
  amber: "bg-signal-amber shadow-glow-amber",
  red: "bg-signal-red shadow-glow-red",
  gray: "bg-signal-gray shadow-none",
};

const PULSE_COLORS: Record<SignalColor, string> = {
  green: "bg-signal-green",
  amber: "bg-signal-amber",
  red: "bg-signal-red",
  gray: "bg-signal-gray",
};

/**
 * The signature UI element for RelayHub: a small glowing indicator dot, deliberately
 * evoking the amber/green/red status LEDs on real relay and networking hardware --
 * this product's actual subject matter. Used consistently for delivery status,
 * endpoint health, and queue/system state throughout the dashboard so the person
 * learns one visual language once and reuses it everywhere.
 */
export function StatusDot({
  color,
  pulse = false,
  size = "sm",
  label,
}: {
  color: SignalColor;
  pulse?: boolean;
  size?: "sm" | "md";
  label?: string;
}) {
  const dimension = size === "sm" ? "h-2 w-2" : "h-2.5 w-2.5";

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative inline-flex">
        {pulse && (
          <span
            className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-40", PULSE_COLORS[color])}
          />
        )}
        <span className={cn("relative inline-block rounded-full", dimension, COLOR_CLASSES[color])} />
      </span>
      {label && <span className="text-graphite-700 dark:text-graphite-200">{label}</span>}
    </span>
  );
}

/** Maps backend status/health strings directly onto the indicator-light vocabulary. */
export function statusToSignalColor(status: string): SignalColor {
  switch (status) {
    case "success":
    case "healthy":
    case "active":
    case "sent":
    case "resolved":
    case "paid":
      return "green";
    case "retrying":
    case "degraded":
    case "queued":
    case "processing":
    case "trialing":
    case "pending":
    case "suppressed":
    // Phase 3 AI intelligence layer statuses (see lib/types.ts's IncidentOut /
    // EndpointHealthSnapshotOut) -- "investigating"/"recovering" are active-but-
    // not-yet-resolved, same amber treatment as "processing"/"pending" elsewhere.
    case "investigating":
    case "recovering":
      return "amber";
    case "failed":
    case "dead_letter":
    case "unhealthy":
    case "past_due":
    case "canceled":
    case "open":
    case "critical":
      return "red";
    default:
      return "gray";
  }
}
