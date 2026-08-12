from app.modules.analytics.percentiles import compute_percentiles


def test_empty_list_returns_none_for_all_percentiles():
    result = compute_percentiles([], [50, 95, 99])
    assert result == {50: None, 95: None, 99: None}


def test_single_value_returns_that_value_for_all_percentiles():
    result = compute_percentiles([42], [50, 95, 99])
    assert result == {50: 42.0, 95: 42.0, 99: 42.0}


def test_known_distribution_p50():
    # 1..100 -- p50 (median) should be 50 under nearest-rank
    values = list(range(1, 101))
    result = compute_percentiles(values, [50])
    assert result[50] == 50.0


def test_known_distribution_p99_is_near_the_top():
    values = list(range(1, 101))
    result = compute_percentiles(values, [99])
    assert result[99] == 99.0


def test_percentiles_are_monotonically_nondecreasing():
    values = [5, 1, 9, 3, 7, 100, 2, 8, 4, 6]
    result = compute_percentiles(values, [50, 95, 99])
    assert result[50] <= result[95] <= result[99]


def test_unsorted_input_does_not_affect_result():
    sorted_result = compute_percentiles([1, 2, 3, 4, 5], [50])
    shuffled_result = compute_percentiles([3, 1, 5, 2, 4], [50])
    assert sorted_result == shuffled_result
