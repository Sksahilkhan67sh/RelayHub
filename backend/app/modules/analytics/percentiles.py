"""
Percentile computation for latency metrics (p50/p95/p99).

Postgres has percentile_cont/percentile_disc as ordered-set aggregates, but this
codebase's test suite runs against SQLite, which doesn't. Rather than write
Postgres-only SQL that silently can't be tested, percentiles are computed in Python
over the queried duration_ms values using the standard nearest-rank method.

This is exact and fine at current scale (a single analytics query pulling attempt
durations for one org over a bounded date range). At millions of attempts, this
should move to either a pre-aggregated rollup table (computed by a periodic job,
similar to retention.py's cleanup task) or an approximate streaming algorithm
(t-digest / HdrHistogram) -- noted here rather than silently degrading later.
"""

from __future__ import annotations

import math


def compute_percentiles(values: list[int], percentiles: list[int]) -> dict[int, float | None]:
    if not values:
        return dict.fromkeys(percentiles)

    sorted_values = sorted(values)
    n = len(sorted_values)
    result: dict[int, float | None] = {}
    for p in percentiles:
        if n == 1:
            result[p] = float(sorted_values[0])
            continue
        rank = math.ceil((p / 100) * n)
        index = min(max(rank - 1, 0), n - 1)
        result[p] = float(sorted_values[index])
    return result
