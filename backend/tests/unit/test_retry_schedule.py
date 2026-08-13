import random

import pytest

from app.modules.retry.schedule import DEFAULT_MAX_ATTEMPTS, DEFAULT_RETRY_DELAYS_SECONDS, compute_next_retry_delay


def test_default_max_attempts_matches_spec():
    # spec: immediate + 10s,30s,1m,5m = 5 total attempts before dead-lettering
    assert DEFAULT_MAX_ATTEMPTS == 5
    assert DEFAULT_RETRY_DELAYS_SECONDS == [10, 30, 60, 300]


@pytest.mark.parametrize(
    "attempt_number,expected_base_delay",
    [(1, 10), (2, 30), (3, 60), (4, 300)],
)
def test_delay_follows_spec_schedule_within_jitter_bounds(attempt_number, expected_base_delay):
    rng = random.Random(42)
    delay = compute_next_retry_delay(attempt_number=attempt_number, rng=rng)
    assert delay is not None
    seconds = delay.total_seconds()
    assert expected_base_delay * 0.8 <= seconds <= expected_base_delay * 1.2


def test_no_more_retries_after_max_attempts():
    delay = compute_next_retry_delay(attempt_number=5)  # 5th attempt just failed, max is 5
    assert delay is None


def test_endpoint_override_smaller_than_default_exhausts_sooner():
    # override says only 3 attempts total
    assert compute_next_retry_delay(attempt_number=2, max_attempts=3) is not None
    assert compute_next_retry_delay(attempt_number=3, max_attempts=3) is None


def test_endpoint_override_zero_means_no_retries():
    assert compute_next_retry_delay(attempt_number=1, max_attempts=0) is None


def test_endpoint_override_larger_than_schedule_reuses_longest_interval():
    rng = random.Random(7)
    delay = compute_next_retry_delay(attempt_number=10, max_attempts=15, rng=rng)
    assert delay is not None
    seconds = delay.total_seconds()
    assert 300 * 0.8 <= seconds <= 300 * 1.2


def test_jitter_produces_variation_across_calls():
    delays = {compute_next_retry_delay(attempt_number=1, rng=random.Random(seed)).total_seconds() for seed in range(20)}
    assert len(delays) > 1, "Expected jitter to produce varying delays across different random seeds"
