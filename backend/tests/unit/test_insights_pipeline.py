import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.anomaly_detection import detect_anomalies
from app.modules.insights.failure_classification import classify_failure
from app.modules.insights.health_analysis import compute_health
from app.modules.insights.models import ConfidenceLevel, FailureCategory, HealthStatus
from app.modules.insights.rca import build_rca

ORG_ID = uuid.uuid4()
ENDPOINT_ID = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _metrics(**overrides) -> WindowMetrics:
    base = dict(
        organization_id=ORG_ID,
        endpoint_id=ENDPOINT_ID,
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        sample_size=0,
        success_count=0,
        failure_count=0,
        http_4xx_count=0,
        http_5xx_count=0,
        timeout_count=0,
        connection_error_count=0,
        auth_failure_count=0,
        rate_limited_count=0,
        retry_count=0,
        dlq_count=0,
        latency_p50_ms=None,
        latency_p95_ms=None,
        workers_total=0,
        workers_healthy=0,
        status_breakdown={},
    )
    base.update(overrides)
    return WindowMetrics(**base)


# ---------------------------------------------------------------------------
# Health analysis (section 3)
# ---------------------------------------------------------------------------


def test_health_reports_unknown_below_min_sample_size():
    metrics = _metrics(sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE - 1, success_count=1, failure_count=0)
    result = compute_health(metrics)
    assert result["status"] == HealthStatus.UNKNOWN.value
    assert result["health_score"] is None


def test_health_reports_healthy_for_all_success():
    n = 100
    metrics = _metrics(sample_size=n, success_count=n, failure_count=0, status_breakdown={"200": n})
    result = compute_health(metrics)
    assert result["status"] == HealthStatus.HEALTHY.value
    assert result["health_score"] == 100.0


def test_health_degrades_as_failure_rate_rises():
    n = 100
    healthy = compute_health(_metrics(sample_size=n, success_count=100, failure_count=0))
    degraded = compute_health(_metrics(sample_size=n, success_count=85, failure_count=15, http_5xx_count=15))
    critical = compute_health(_metrics(sample_size=n, success_count=10, failure_count=90, http_5xx_count=90))

    assert healthy["health_score"] > degraded["health_score"] > critical["health_score"]
    assert critical["status"] == HealthStatus.CRITICAL.value


def test_health_confidence_increases_with_sample_size():
    small = compute_health(_metrics(sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE, success_count=20))
    large = compute_health(_metrics(sample_size=10_000, success_count=10_000))
    assert large["confidence"] > small["confidence"]
    assert large["confidence"] < 1.0  # never claims certainty


# ---------------------------------------------------------------------------
# Anomaly detection (section 4) -- avoiding false positives from tiny samples
# ---------------------------------------------------------------------------


def test_no_anomalies_when_current_sample_too_small():
    current = _metrics(sample_size=3, success_count=0, failure_count=3)  # 100% failure, but n=3
    baseline = _metrics(sample_size=200, success_count=195, failure_count=5)
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)
    assert anomalies == []


def test_no_anomalies_when_baseline_too_small():
    current = _metrics(sample_size=200, success_count=100, failure_count=100)
    baseline = _metrics(sample_size=2, success_count=2, failure_count=0)
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)
    assert anomalies == []


def test_failure_rate_spike_detected_with_evidence():
    current = _metrics(sample_size=200, success_count=100, failure_count=100, http_5xx_count=100, status_breakdown={"503": 100, "200": 100})
    baseline = _metrics(sample_size=200, success_count=195, failure_count=5, http_5xx_count=5, status_breakdown={"200": 195, "503": 5})
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)

    failure_anomalies = [a for a in anomalies if a["metric"] == "failure_rate"]
    assert len(failure_anomalies) == 1
    anomaly = failure_anomalies[0]
    assert anomaly["direction"] == "spike"
    assert anomaly["observed_value"] > anomaly["baseline_value"]
    assert anomaly["confidence"] > 0
    assert len(anomaly["evidence"]) >= 2


def test_no_anomaly_when_delta_below_threshold():
    # 5pp movement, threshold is 15pp -- should not fire.
    current = _metrics(sample_size=200, success_count=185, failure_count=15)
    baseline = _metrics(sample_size=200, success_count=195, failure_count=5)
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)
    assert [a for a in anomalies if a["metric"] == "failure_rate"] == []


def test_status_distribution_anomaly_fires_when_dominant_status_changes():
    current = _metrics(
        sample_size=200, success_count=80, failure_count=120, http_5xx_count=120,
        status_breakdown={"503": 120, "200": 80},
    )
    baseline = _metrics(
        sample_size=200, success_count=195, failure_count=5, http_5xx_count=5,
        status_breakdown={"503": 5, "200": 195},
    )
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)
    status_anomalies = [a for a in anomalies if a["metric"] == "status_distribution"]
    # Dominant status flips from 200 (baseline) to 503 (current) -- different
    # identity, current share (60%) clears the 40% dominance floor, so this fires.
    assert len(status_anomalies) == 1
    assert "503" in status_anomalies[0]["evidence"][0]["value"]


def test_status_distribution_anomaly_does_not_fire_when_dominant_status_unchanged():
    current = _metrics(
        sample_size=200, success_count=100, failure_count=100, rate_limited_count=90, http_4xx_count=90,
        status_breakdown={"429": 90, "200": 110},
    )
    baseline = _metrics(
        sample_size=200, success_count=195, failure_count=5, http_5xx_count=5,
        status_breakdown={"503": 5, "200": 195},
    )
    anomalies = detect_anomalies(endpoint_id=ENDPOINT_ID, organization_id=ORG_ID, current=current, baseline=baseline, observed_at=NOW)
    status_anomalies = [a for a in anomalies if a["metric"] == "status_distribution"]
    # Dominant status in both current (200, 55%) and baseline (200, 97.5%) is the
    # same status -- verifies we compare dominant identity, not just rate movement.
    assert status_anomalies == []


# ---------------------------------------------------------------------------
# Failure classification (section 6) -- never blames RelayHub for destination issues
# ---------------------------------------------------------------------------


def test_classifies_5xx_dominant_as_destination_5xx():
    metrics = _metrics(sample_size=100, success_count=10, failure_count=90, http_5xx_count=90, status_breakdown={"503": 90, "200": 10})
    category, proportion = classify_failure(metrics)
    assert category == FailureCategory.DESTINATION_5XX.value
    assert proportion == 0.9


def test_classifies_429_dominant_as_rate_limited_not_generic_4xx():
    metrics = _metrics(sample_size=100, success_count=10, failure_count=90, http_4xx_count=90, rate_limited_count=90, status_breakdown={"429": 90, "200": 10})
    category, _ = classify_failure(metrics)
    assert category == FailureCategory.RATE_LIMITED.value


def test_classifies_auth_failures_distinct_from_generic_4xx():
    metrics = _metrics(sample_size=100, success_count=20, failure_count=80, http_4xx_count=80, auth_failure_count=80, status_breakdown={"401": 80, "200": 20})
    category, _ = classify_failure(metrics)
    assert category == FailureCategory.AUTHENTICATION_FAILURE.value


def test_worker_failure_takes_priority_over_destination_status():
    # Even though 5xx dominates the raw counts, unhealthy workers explain it and
    # take priority -- RelayHub's own infra, not the destination, is the story.
    metrics = _metrics(
        sample_size=100, success_count=10, failure_count=90, http_5xx_count=90,
        workers_total=10, workers_healthy=2, status_breakdown={"503": 90, "200": 10},
    )
    category, _ = classify_failure(metrics)
    assert category == FailureCategory.WORKER_FAILURE.value


def test_classification_falls_back_to_unknown_without_dominant_cause():
    # Failures split roughly evenly across categories -- nothing dominates.
    metrics = _metrics(
        sample_size=100, success_count=40, failure_count=60,
        http_5xx_count=20, http_4xx_count=20, timeout_count=10, connection_error_count=10,
        status_breakdown={"200": 40, "503": 20, "400": 20},
    )
    category, _ = classify_failure(metrics)
    assert category == FailureCategory.UNKNOWN.value


# ---------------------------------------------------------------------------
# RCA (section 7) -- confidence levels, evidence, never CONFIRMED off thin samples
# ---------------------------------------------------------------------------


def test_rca_unknown_for_insufficient_data():
    metrics = _metrics(sample_size=2, success_count=0, failure_count=2)
    rca = build_rca(metrics=metrics, min_sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE)
    assert rca["confidence_level"] == ConfidenceLevel.UNKNOWN.value
    assert rca["confidence_score"] == 0.0


def test_rca_never_confirmed_on_thin_sample_even_at_100_percent():
    # Exactly at the minimum sample size, 100% one cause -- should be capped below
    # CONFIRMED/HIGHLY_LIKELY, matching "never CONFIRMED off a thin sample".
    n = settings.INSIGHTS_MIN_SAMPLE_SIZE
    metrics = _metrics(sample_size=n, success_count=0, failure_count=n, http_5xx_count=n, status_breakdown={"503": n})
    rca = build_rca(metrics=metrics, min_sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE)
    assert rca["confidence_level"] != ConfidenceLevel.CONFIRMED.value


def test_rca_reaches_confirmed_with_large_sample_and_dominant_cause():
    n = 2000
    metrics = _metrics(sample_size=n, success_count=int(n * 0.02), failure_count=int(n * 0.98), http_5xx_count=int(n * 0.98), status_breakdown={"503": int(n * 0.98)})
    rca = build_rca(metrics=metrics, min_sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE)
    assert rca["confidence_level"] == ConfidenceLevel.CONFIRMED.value
    assert "destination" in rca["likely_cause"].lower() or "outage" in rca["likely_cause"].lower()
    assert rca["recommendations"]
    assert all(isinstance(e, dict) and "label" in e and "value" in e for e in rca["evidence"])


def test_rca_recommendation_matches_failure_category():
    n = 2000
    metrics = _metrics(sample_size=n, success_count=int(n * 0.1), failure_count=int(n * 0.9), rate_limited_count=int(n * 0.9), http_4xx_count=int(n * 0.9), status_breakdown={"429": int(n * 0.9)})
    rca = build_rca(metrics=metrics, min_sample_size=settings.INSIGHTS_MIN_SAMPLE_SIZE)
    assert "rate limit" in rca["recommendations"][0].lower()
