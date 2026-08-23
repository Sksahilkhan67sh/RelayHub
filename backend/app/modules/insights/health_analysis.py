"""
Phase 3 -- endpoint health analysis (section 3 of the brief). Pure function over a
WindowMetrics -- no DB access, no AI, fully deterministic and unit-testable in
isolation. The caller (workers/insight_tasks.py) is responsible for persisting the
result as an EndpointHealthSnapshot.
"""

from __future__ import annotations

from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.models import HealthStatus

# Score thresholds. Score is 0-100, computed from a weighted blend of the rates
# that matter most operationally (failure rate and 5xx rate dominate -- those are
# the ones a developer actually needs paged for; 4xx is usually a caller-side
# integration bug, not an incident).
_FAILURE_WEIGHT = 0.5
_HTTP_5XX_WEIGHT = 0.25
_TIMEOUT_WEIGHT = 0.15
_DLQ_WEIGHT = 0.10

_HEALTHY_THRESHOLD = 90.0
_DEGRADED_THRESHOLD = 70.0
_UNHEALTHY_THRESHOLD = 40.0
# Below _UNHEALTHY_THRESHOLD -> CRITICAL


def compute_health(metrics: WindowMetrics) -> dict:
    """Returns a dict matching EndpointHealthSnapshot's scoring fields. Never
    fabricates a score for insufficient data -- returns UNKNOWN with score=None
    instead, per section 3's explicit requirement."""

    if not metrics.has_sufficient_data():
        return {
            "status": HealthStatus.UNKNOWN.value,
            "health_score": None,
            "confidence": 0.0,
            "supporting_signals": {
                "reason": "insufficient_data",
                "sample_size": metrics.sample_size,
            },
        }

    failure_rate = metrics.failure_rate or 0.0
    http_5xx_rate = metrics.http_5xx_rate or 0.0
    timeout_rate = metrics.timeout_rate or 0.0
    dlq_rate = metrics.dlq_rate or 0.0

    penalty = (
        _FAILURE_WEIGHT * failure_rate
        + _HTTP_5XX_WEIGHT * http_5xx_rate
        + _TIMEOUT_WEIGHT * timeout_rate
        + _DLQ_WEIGHT * dlq_rate
    ) * 100
    score = max(0.0, 100.0 - penalty)

    if score >= _HEALTHY_THRESHOLD:
        status = HealthStatus.HEALTHY
    elif score >= _DEGRADED_THRESHOLD:
        status = HealthStatus.DEGRADED
    elif score >= _UNHEALTHY_THRESHOLD:
        status = HealthStatus.UNHEALTHY
    else:
        status = HealthStatus.CRITICAL

    # Confidence grows with sample size, capped at 0.99 (never claim certainty).
    # At exactly the minimum sample size, confidence is ~0.5; it climbs toward 1.0
    # as sample_size grows well past the minimum.
    confidence = min(0.99, 0.5 + 0.5 * (1 - (metrics.sample_size and metrics.sample_size ** -0.5)))

    supporting_signals = {
        "success_rate": metrics.success_rate,
        "failure_rate": metrics.failure_rate,
        "http_4xx_rate": metrics.http_4xx_rate,
        "http_5xx_rate": metrics.http_5xx_rate,
        "timeout_rate": metrics.timeout_rate,
        "retry_rate": metrics.retry_rate,
        "dlq_rate": metrics.dlq_rate,
        "latency_p95_ms": metrics.latency_p95_ms,
        "worker_health_ratio": metrics.worker_health_ratio,
        "status_breakdown": metrics.status_breakdown,
    }

    return {
        "status": status.value,
        "health_score": round(score, 2),
        "confidence": round(confidence, 3),
        "supporting_signals": supporting_signals,
    }
