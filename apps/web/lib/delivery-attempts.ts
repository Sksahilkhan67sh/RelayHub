/**
 * Delivery Attempt UX state, derived entirely from real backend fields
 * (status, attempt_number, max_attempts, next_attempt_at). No value here is
 * invented or independently counted on the frontend -- every number is a pure
 * function of what the API actually returned for this job.
 *
 * attempt_number semantics (see backend app/modules/delivery/executor.py): it is
 * incremented at the START of each attempt, before the HTTP call, so while a job
 * is "processing" attempt_number already reflects the in-flight attempt. Once an
 * attempt finishes, attempt_number equals the count of completed attempts. This
 * single field, combined with status, is enough to derive every value below
 * without any off-by-one special-casing between states.
 */

export type DerivedDeliveryStatus = "queued" | "delivering" | "delivered" | "retrying" | "dead_letter" | "failed";

export interface DeliveryAttemptState {
  /** Normalized status for display purposes (label/color), distinct from the raw API status string. */
  derivedStatus: DerivedDeliveryStatus;
  /** The current/most-recently-completed attempt number, straight from the API. */
  currentAttempt: number;
  /** The effective max attempts for this specific job (per-endpoint override or platform default), from the API -- never hardcoded. */
  maxAttempts: number;
  /** max(0, maxAttempts - currentAttempt) -- always in [0, maxAttempts], enforced defensively even though the backend should already guarantee this. */
  attemptsRemaining: number;
  /** True once the job is in a state where no further attempts will happen (success, failed, dead_letter). */
  isTerminal: boolean;
  /** Only true when the job is genuinely still retrying and the backend gave a real next_attempt_at -- never fabricated. */
  hasScheduledRetry: boolean;
  /** ISO timestamp of the next attempt, straight from the API. Null whenever hasScheduledRetry is false. */
  nextAttemptAt: string | null;
}

const TERMINAL_STATUSES = new Set(["success", "failed", "dead_letter"]);

export function deriveDeliveryAttemptState(job: {
  status: string;
  attempt_number: number;
  max_attempts: number;
  next_attempt_at: string | null;
}): DeliveryAttemptState {
  const isTerminal = TERMINAL_STATUSES.has(job.status);

  let derivedStatus: DerivedDeliveryStatus;
  switch (job.status) {
    case "queued":
      derivedStatus = "queued";
      break;
    case "processing":
      derivedStatus = "delivering";
      break;
    case "success":
      derivedStatus = "delivered";
      break;
    case "retrying":
      derivedStatus = "retrying";
      break;
    case "dead_letter":
      derivedStatus = "dead_letter";
      break;
    case "failed":
    default:
      derivedStatus = "failed";
      break;
  }

  // Defensive clamping only -- these bounds should already hold from the backend
  // (see test_attempts_remaining_never_negative_or_over_max_across_states), but a
  // UI must never itself display a negative or over-max number even if some future
  // backend change or edge case briefly violates the invariant.
  const currentAttempt = Math.max(0, job.attempt_number);
  const maxAttempts = Math.max(currentAttempt, job.max_attempts);
  // Per spec's own worked examples: SUCCESS explicitly shows a non-zero remaining
  // count (e.g. "Attempt 2/5, Attempts remaining: 3") as purely informational math
  // -- the "do not imply another attempt will run" requirement is satisfied by
  // hasScheduledRetry being false, not by zeroing this number. FAILED (permanent)
  // and DEAD_LETTER are different: the spec's examples show remaining=0 there
  // regardless of the math, since no more attempts were or will be scheduled.
  const forceZeroRemaining = isTerminal && job.status !== "success";
  const attemptsRemaining = forceZeroRemaining ? 0 : Math.max(0, maxAttempts - currentAttempt);

  // hasScheduledRetry requires BOTH a real next_attempt_at from the backend AND a
  // non-terminal status -- guards against ever implying a retry is coming after
  // success/failure/dead-letter, which is exactly the bug this feature fixed in the
  // executor (next_attempt_at is now always cleared on every terminal transition).
  const hasScheduledRetry = !isTerminal && job.status === "retrying" && job.next_attempt_at !== null;

  return {
    derivedStatus,
    currentAttempt,
    maxAttempts,
    attemptsRemaining,
    isTerminal,
    hasScheduledRetry,
    nextAttemptAt: hasScheduledRetry ? job.next_attempt_at : null,
  };
}

export const STATUS_LABELS: Record<DerivedDeliveryStatus, string> = {
  queued: "Queued",
  delivering: "Delivering",
  delivered: "Delivered",
  retrying: "Retrying",
  dead_letter: "Dead Letter",
  failed: "Failed",
};

export const STATUS_COLORS: Record<DerivedDeliveryStatus, "green" | "amber" | "red" | "gray"> = {
  queued: "gray",
  delivering: "amber",
  delivered: "green",
  retrying: "amber",
  dead_letter: "red",
  failed: "red",
};

/** Formats a countdown like "42 seconds", "2 minutes", or "now" for a future ISO timestamp. Never negative. */
export function formatCountdown(targetIso: string, nowMs: number): string {
  const targetMs = new Date(targetIso).getTime();
  const diffMs = targetMs - nowMs;
  if (diffMs <= 0) return "now";
  const totalSeconds = Math.ceil(diffMs / 1000);
  if (totalSeconds < 60) return `${totalSeconds} second${totalSeconds === 1 ? "" : "s"}`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes} minute${minutes === 1 ? "" : "s"}`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}
