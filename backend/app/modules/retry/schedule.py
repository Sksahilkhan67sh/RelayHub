"""
Retry schedule: immediate first queued attempt, then 10s, 30s, 1m, 5m -- 5 total
attempts before a job is declared dead and moved to the Dead Letter Queue.

Attempt numbering convention: attempt_number=1 is that immediate first attempt (already
happened by the time this module is consulted). DEFAULT_RETRY_DELAYS_SECONDS holds the
delay before each subsequent attempt, so delays[0]=10s is the wait before attempt 2,
delays[1]=30s before attempt 3, and so on. DEFAULT_MAX_ATTEMPTS = len(delays) + 1 = 5
total attempts (1 immediate + 4 scheduled retries).

Jitter: +/-20% multiplicative, to avoid many jobs failing at the same instant (e.g. a
destination outage) all retrying in the same synchronized burst against a customer
endpoint that's still recovering.
"""

from __future__ import annotations

import random
from datetime import timedelta

DEFAULT_RETRY_DELAYS_SECONDS: list[int] = [10, 30, 60, 300]
DEFAULT_MAX_ATTEMPTS: int = len(DEFAULT_RETRY_DELAYS_SECONDS) + 1  # 5
JITTER_FACTOR: float = 0.2


def compute_next_retry_delay(
    *, attempt_number: int, max_attempts: int | None = None, rng: random.Random | None = None
) -> timedelta | None:
    """
    attempt_number: the attempt that just failed (>=1).
    max_attempts: per-endpoint override (Endpoint.max_retry_attempts); None uses the
        plan/global default. A value of 0 means "no retries -- dead-letter on first
        failure", which is a valid and sometimes-desired configuration (e.g. an
        endpoint the customer doesn't care about missing occasional events for).

    Returns the delay before the next attempt, or None if attempts are exhausted and
    the job should move to the dead letter queue instead.
    """
    effective_max = max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS
    if attempt_number >= effective_max:
        return None

    delay_index = attempt_number - 1
    if delay_index < len(DEFAULT_RETRY_DELAYS_SECONDS):
        base_delay = DEFAULT_RETRY_DELAYS_SECONDS[delay_index]
    else:
        # Endpoint configured for more retries than our default schedule covers --
        # keep using the longest interval rather than inventing new (untested) tiers.
        base_delay = DEFAULT_RETRY_DELAYS_SECONDS[-1]

    r = rng or random
    jitter_multiplier = 1 + r.uniform(-JITTER_FACTOR, JITTER_FACTOR)
    jittered_seconds = max(1.0, base_delay * jitter_multiplier)
    return timedelta(seconds=jittered_seconds)
