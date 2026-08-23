"""
Phase 3 -- anomaly detection (section 4). Compares a current WindowMetrics against
a baseline computed from the preceding N windows for the same endpoint. Pure
functions over already-aggregated data -- aggregation.py owns all DB access.

False-positive avoidance (explicitly required by section 4): an anomaly is only
raised when BOTH the current window and the baseline have enough samples to trust
the comparison. A quiet endpoint with 3 requests going to 3 failures is a 100%
failure rate on paper but not statistically meaningful -- INSIGHTS_MIN_SAMPLE_SIZE
gates that out at both ends of the comparison.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.core.config import settings
from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.models import AnomalyDirection, AnomalyMetric

# (metric, WindowMetrics rate attribute, human label)
_RATE_METRICS = [
    (AnomalyMetric.FAILURE_RATE, "failure_rate", "failure rate"),
    (AnomalyMetric.RETRY_RATE, "retry_rate", "retry rate"),
    (AnomalyMetric.DLQ_RATE, "dlq_rate", "DLQ rate"),
    (AnomalyMetric.TIMEOUT_RATE, "timeout_rate", "timeout rate"),
]


def _confidence_for(current: WindowMetrics, baseline: WindowMetrics, delta_magnitude: float, min_delta: float) -> float:
    """Heuristic, not a statistical p-value: grows with sample size on both sides
    and with how far past the minimum-detectable-delta the observed delta is.
    Deliberately conservative -- caps below 0.99, and a delta right at the
    threshold gets a low-but-nonzero confidence rather than a hard cliff."""
    sample_factor = min(1.0, (min(current.sample_size, baseline.sample_size) / (settings.INSIGHTS_MIN_SAMPLE_SIZE * 4)))
    magnitude_factor = min(1.0, delta_magnitude / (min_delta * 3))
    return round(min(0.97, 0.3 + 0.4 * sample_factor + 0.3 * magnitude_factor), 3)


def detect_rate_anomalies(
    *, endpoint_id: uuid.UUID | None, organization_id: uuid.UUID, current: WindowMetrics, baseline: WindowMetrics, observed_at: datetime
) -> list[dict]:
    """Returns a list of anomaly dicts (not persisted -- caller maps these to
    Anomaly ORM rows) for rate-based metrics (failure/retry/dlq/timeout)."""

    if not current.has_sufficient_data() or not baseline.has_sufficient_data():
        return []

    anomalies: list[dict] = []
    min_delta = settings.INSIGHTS_ANOMALY_MIN_RATE_DELTA

    for metric, attr, label in _RATE_METRICS:
        observed = getattr(current, attr)
        base = getattr(baseline, attr)
        if observed is None or base is None:
            continue

        delta = observed - base
        if abs(delta) < min_delta:
            continue

        direction = AnomalyDirection.SPIKE if delta > 0 else AnomalyDirection.DROP
        confidence = _confidence_for(current, baseline, abs(delta), min_delta)

        anomalies.append(
            {
                "organization_id": organization_id,
                "endpoint_id": endpoint_id,
                "metric": metric.value,
                "direction": direction.value,
                "observed_value": round(observed, 4),
                "baseline_value": round(base, 4),
                "delta": round(delta, 4),
                "observed_at": observed_at,
                "confidence": confidence,
                "sample_size": current.sample_size,
                "evidence": [
                    {"label": f"current {label}", "value": f"{observed:.1%}"},
                    {"label": f"baseline {label}", "value": f"{base:.1%}"},
                    {"label": "current window sample size", "value": current.sample_size},
                    {"label": "baseline sample size", "value": baseline.sample_size},
                ],
            }
        )

    return anomalies


def detect_latency_anomaly(
    *, endpoint_id: uuid.UUID | None, organization_id: uuid.UUID, current: WindowMetrics, baseline: WindowMetrics, observed_at: datetime
) -> dict | None:
    if not current.has_sufficient_data() or not baseline.has_sufficient_data():
        return None
    if current.latency_p95_ms is None or baseline.latency_p95_ms is None or baseline.latency_p95_ms <= 0:
        return None

    ratio_delta = (current.latency_p95_ms - baseline.latency_p95_ms) / baseline.latency_p95_ms
    if abs(ratio_delta) < settings.INSIGHTS_ANOMALY_MIN_LATENCY_DELTA_RATIO:
        return None

    direction = AnomalyDirection.SPIKE if ratio_delta > 0 else AnomalyDirection.DROP
    confidence = _confidence_for(current, baseline, abs(ratio_delta), settings.INSIGHTS_ANOMALY_MIN_LATENCY_DELTA_RATIO)

    return {
        "organization_id": organization_id,
        "endpoint_id": endpoint_id,
        "metric": AnomalyMetric.LATENCY.value,
        "direction": direction.value,
        "observed_value": current.latency_p95_ms,
        "baseline_value": baseline.latency_p95_ms,
        "delta": round(current.latency_p95_ms - baseline.latency_p95_ms, 2),
        "observed_at": observed_at,
        "confidence": confidence,
        "sample_size": current.sample_size,
        "evidence": [
            {"label": "current p95 latency", "value": f"{current.latency_p95_ms:.0f}ms"},
            {"label": "baseline p95 latency", "value": f"{baseline.latency_p95_ms:.0f}ms"},
            {"label": "relative change", "value": f"{ratio_delta:+.0%}"},
        ],
    }


def detect_status_distribution_anomaly(
    *, endpoint_id: uuid.UUID | None, organization_id: uuid.UUID, current: WindowMetrics, baseline: WindowMetrics, observed_at: datetime
) -> dict | None:
    """Flags a shift in which HTTP status dominates failures -- e.g. baseline was
    mostly 500s, current window is mostly 429s. Distinct from the plain failure-rate
    anomaly because the failure RATE might be flat while the CAUSE has changed."""

    if not current.has_sufficient_data() or not baseline.has_sufficient_data():
        return None
    if not current.status_breakdown:
        return None

    def dominant(breakdown: dict) -> tuple[str, float] | None:
        total = sum(breakdown.values())
        if not total:
            return None
        status, count = max(breakdown.items(), key=lambda kv: kv[1])
        return status, count / total

    current_dom = dominant(current.status_breakdown)
    baseline_dom = dominant(baseline.status_breakdown)
    if not current_dom or not baseline_dom:
        return None
    if current_dom[0] == baseline_dom[0]:
        return None
    if current_dom[1] < 0.4:  # not actually dominant, don't flag noise
        return None

    return {
        "organization_id": organization_id,
        "endpoint_id": endpoint_id,
        "metric": AnomalyMetric.STATUS_DISTRIBUTION.value,
        "direction": AnomalyDirection.REGRESSION.value,
        "observed_value": current_dom[1],
        "baseline_value": baseline_dom[1],
        "delta": round(current_dom[1] - baseline_dom[1], 4),
        "observed_at": observed_at,
        "confidence": _confidence_for(current, baseline, current_dom[1], 0.4),
        "sample_size": current.sample_size,
        "evidence": [
            {"label": "current dominant status", "value": f"HTTP {current_dom[0]} ({current_dom[1]:.0%} of attempts)"},
            {"label": "baseline dominant status", "value": f"HTTP {baseline_dom[0]} ({baseline_dom[1]:.0%} of attempts)"},
        ],
    }


def detect_anomalies(
    *, endpoint_id: uuid.UUID | None, organization_id: uuid.UUID, current: WindowMetrics, baseline: WindowMetrics, observed_at: datetime
) -> list[dict]:
    """Entry point: runs every detector and returns the combined anomaly list."""
    anomalies = detect_rate_anomalies(
        endpoint_id=endpoint_id, organization_id=organization_id, current=current, baseline=baseline, observed_at=observed_at
    )
    latency_anomaly = detect_latency_anomaly(
        endpoint_id=endpoint_id, organization_id=organization_id, current=current, baseline=baseline, observed_at=observed_at
    )
    if latency_anomaly:
        anomalies.append(latency_anomaly)
    status_anomaly = detect_status_distribution_anomaly(
        endpoint_id=endpoint_id, organization_id=organization_id, current=current, baseline=baseline, observed_at=observed_at
    )
    if status_anomaly:
        anomalies.append(status_anomaly)
    return anomalies
