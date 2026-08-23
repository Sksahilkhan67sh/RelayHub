"""
Phase 3 -- failure classification (section 6). Deterministic, evidence-based: looks
at the dominant signal in a WindowMetrics and maps it to a FailureCategory. No
guessing -- if nothing dominates, returns UNKNOWN rather than picking arbitrarily.

Explicitly does NOT blame RelayHub for destination-side failures (section 6): 4xx/5xx
map to DESTINATION_4XX/DESTINATION_5XX, not to a RelayHub-side category, unless the
evidence points at RelayHub's own infrastructure (worker/queue health).
"""

from __future__ import annotations

from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.models import FailureCategory

# Minimum share of the failing sample a single cause must explain before we're
# willing to name it as THE classification, rather than falling through to UNKNOWN.
_DOMINANCE_THRESHOLD = 0.5


def classify_failure(metrics: WindowMetrics) -> tuple[str, float]:
    """Returns (FailureCategory value, proportion of the sample that supports it).
    Proportion is out of the FULL sample (not just failures) so it directly doubles
    as an RCA confidence input."""

    if not metrics.has_sufficient_data() or metrics.sample_size == 0:
        return FailureCategory.UNKNOWN.value, 0.0

    n = metrics.sample_size

    # Worker/queue infra signals take priority: if RelayHub's own workers are down,
    # that's the story regardless of what destination status codes look like --
    # they're likely a symptom (nothing got delivered), not the cause.
    if metrics.workers_total > 0 and metrics.worker_health_ratio is not None and metrics.worker_health_ratio < 0.5:
        return FailureCategory.WORKER_FAILURE.value, round(1 - metrics.worker_health_ratio, 4)

    candidates = [
        (FailureCategory.RATE_LIMITED, metrics.rate_limited_count),
        (FailureCategory.AUTHENTICATION_FAILURE, metrics.auth_failure_count),
        (FailureCategory.DESTINATION_5XX, metrics.http_5xx_count),
        (FailureCategory.DESTINATION_4XX, metrics.http_4xx_count - metrics.auth_failure_count - metrics.rate_limited_count),
        (FailureCategory.TIMEOUT, metrics.timeout_count),
        (FailureCategory.NETWORK_FAILURE, metrics.connection_error_count),
    ]

    category, count = max(candidates, key=lambda c: c[1])
    proportion = count / n

    if proportion < _DOMINANCE_THRESHOLD or count == 0:
        return FailureCategory.UNKNOWN.value, round(proportion, 4)

    return category.value, round(proportion, 4)
