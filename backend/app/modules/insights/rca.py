"""
Phase 3 -- deterministic root cause analysis and recommendations (sections 7 & 11).
This is the RCA path that runs for EVERY incident, with no AI involved -- rule-based,
evidence-attached, confidence-leveled. The AI provider (ai/ package, added next) is
an optional enrichment layer that can add a narrative summary on top of this, but
this module must produce a complete, correct, and honest RCA on its own so the
system works fully with AI disabled (section 2: "AI layer must be independent").
"""

from __future__ import annotations

from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.failure_classification import classify_failure
from app.modules.insights.models import ConfidenceLevel, FailureCategory

_RECOMMENDATIONS: dict[str, str] = {
    FailureCategory.DESTINATION_5XX.value: "Check the destination service's health and recent deployments -- the errors are coming from their side, not RelayHub.",
    FailureCategory.RATE_LIMITED.value: "Check the destination's rate limits and consider reducing delivery concurrency to this endpoint.",
    FailureCategory.AUTHENTICATION_FAILURE.value: "Verify the webhook authentication credentials (signing secret, API key, or auth headers) are still valid on the destination side.",
    FailureCategory.DESTINATION_4XX.value: "Review the request payload and headers against the destination's expected schema -- this looks like a client-side integration issue, not a RelayHub delivery problem.",
    FailureCategory.TIMEOUT.value: "Investigate destination latency before increasing timeout values -- a longer timeout treats the symptom, not the cause.",
    FailureCategory.NETWORK_FAILURE.value: "Check DNS resolution and network reachability to the destination host.",
    FailureCategory.WORKER_FAILURE.value: "RelayHub worker processes are reporting unhealthy -- check worker logs and Celery/Redis connectivity.",
    FailureCategory.QUEUE_FAILURE.value: "Delivery queue depth or processing is abnormal -- check Redis/Celery broker health.",
    FailureCategory.UNKNOWN.value: "No single dominant cause was identified from delivery evidence -- review the incident timeline and raw attempt logs manually.",
}

# proportion-of-sample -> confidence level. Confidence LEVEL is a discrete label;
# confidence_score (0-1) is the underlying number the level is derived from, so the
# API/UI can show both ("91% confident" + "HIGHLY_LIKELY").
_CONFIDENCE_LEVEL_THRESHOLDS = [
    (0.95, ConfidenceLevel.CONFIRMED),
    (0.80, ConfidenceLevel.HIGHLY_LIKELY),
    (0.55, ConfidenceLevel.LIKELY),
    (0.30, ConfidenceLevel.POSSIBLE),
]


def _confidence_level_for(score: float, sample_size: int, min_sample_size: int) -> ConfidenceLevel:
    # Never CONFIRMED off a thin sample, no matter how skewed the proportion --
    # "3 out of 3 requests failed" is not confirmation of anything. Cap just below
    # the HIGHLY_LIKELY threshold until the sample is comfortably past the minimum.
    if sample_size < min_sample_size * 2:
        score = min(score, _CONFIDENCE_LEVEL_THRESHOLDS[1][0] - 0.01)

    for threshold, level in _CONFIDENCE_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return ConfidenceLevel.POSSIBLE if score > 0 else ConfidenceLevel.UNKNOWN


def build_rca(*, metrics: WindowMetrics, min_sample_size: int) -> dict:
    """Returns a dict matching RootCauseAnalysis's fields (source='deterministic').
    Never presents speculation as fact (section 7): confidence_level/score are
    always derived directly from the evidence list, never asserted independently."""

    if not metrics.has_sufficient_data():
        return {
            "source": "deterministic",
            "likely_cause": "Insufficient delivery data in this window to determine a cause.",
            "confidence_level": ConfidenceLevel.UNKNOWN.value,
            "confidence_score": 0.0,
            "evidence": [{"label": "sample size", "value": metrics.sample_size}],
            "recommendations": ["Wait for more delivery attempts, or widen the time window, before requesting an RCA."],
        }

    category, proportion = classify_failure(metrics)
    level = _confidence_level_for(proportion, metrics.sample_size, min_sample_size)

    evidence = [
        {"label": "sample size", "value": metrics.sample_size},
        {"label": "classification support", "value": f"{proportion:.0%} of attempts consistent with {category}"},
    ]
    if metrics.http_5xx_rate:
        evidence.append({"label": "HTTP 5xx rate", "value": f"{metrics.http_5xx_rate:.0%}"})
    if metrics.http_4xx_rate:
        evidence.append({"label": "HTTP 4xx rate", "value": f"{metrics.http_4xx_rate:.0%}"})
    if metrics.timeout_rate:
        evidence.append({"label": "timeout rate", "value": f"{metrics.timeout_rate:.0%}"})
    if metrics.connection_error_count:
        evidence.append({"label": "connection errors", "value": metrics.connection_error_count})
    if metrics.latency_p95_ms is not None:
        evidence.append({"label": "p95 latency", "value": f"{metrics.latency_p95_ms:.0f}ms"})
    if metrics.worker_health_ratio is not None:
        evidence.append({"label": "healthy worker ratio", "value": f"{metrics.worker_health_ratio:.0%}"})
    if metrics.status_breakdown:
        top_statuses = sorted(metrics.status_breakdown.items(), key=lambda kv: -kv[1])[:3]
        evidence.append({"label": "top HTTP statuses", "value": ", ".join(f"{s}×{c}" for s, c in top_statuses)})

    likely_cause = _LIKELY_CAUSE_TEXT.get(category, "Cause could not be determined from available delivery evidence.")
    recommendations = [_RECOMMENDATIONS.get(category, _RECOMMENDATIONS[FailureCategory.UNKNOWN.value])]

    return {
        "source": "deterministic",
        "likely_cause": likely_cause,
        "confidence_level": level.value,
        "confidence_score": round(proportion, 4),
        "evidence": evidence,
        "recommendations": recommendations,
    }


_LIKELY_CAUSE_TEXT: dict[str, str] = {
    FailureCategory.DESTINATION_5XX.value: "Destination service is returning server errors (5xx) -- likely a destination-side outage or deployment issue.",
    FailureCategory.RATE_LIMITED.value: "Destination is rate-limiting RelayHub's delivery requests (HTTP 429).",
    FailureCategory.AUTHENTICATION_FAILURE.value: "Destination is rejecting requests as unauthenticated/unauthorized (401/403) -- credentials likely rotated or misconfigured.",
    FailureCategory.DESTINATION_4XX.value: "Destination is rejecting requests as malformed (4xx, excluding auth/rate-limit) -- likely a payload or schema mismatch.",
    FailureCategory.TIMEOUT.value: "Requests to the destination are timing out -- destination latency exceeds the configured timeout.",
    FailureCategory.NETWORK_FAILURE.value: "Requests are failing at the network/connection level before a response is received.",
    FailureCategory.WORKER_FAILURE.value: "RelayHub's own worker processes are unhealthy, reducing delivery capacity for this endpoint.",
    FailureCategory.QUEUE_FAILURE.value: "RelayHub's delivery queue is exhibiting abnormal depth or processing behaviour.",
    FailureCategory.UNKNOWN.value: "No single failure mode dominates the evidence -- likely a mix of causes.",
}
