"""Warehouse workload classification and savings-projection helpers (Directive B).

Shared primitives consumed by sizing-related rules (PERF_020-023, COST_034-036).

No SQL; no cursor access. Pure functions over aggregated metrics so they are
trivial to unit-test and reuse across rules.
"""

from __future__ import annotations

from enum import Enum

# Snowflake's published credit-per-hour by warehouse size.  Doubles each tier.
# Reference: https://docs.snowflake.com/en/user-guide/warehouses-overview
_CREDIT_PER_HOUR: dict[str, int] = {
    "X-SMALL": 1,
    "SMALL": 2,
    "MEDIUM": 4,
    "LARGE": 8,
    "X-LARGE": 16,
    "2X-LARGE": 32,
    "3X-LARGE": 64,
    "4X-LARGE": 128,
    "5X-LARGE": 256,
    "6X-LARGE": 512,
}


def size_credit_rate(size: str) -> int:
    """Credits per hour for a given warehouse size, or 1 for unknown sizes."""
    return _CREDIT_PER_HOUR.get(size.upper(), 1)


class WorkloadClass(Enum):
    """Coarse workload type used to drive sizing recommendations."""

    INTERACTIVE = "INTERACTIVE"  # short, high-concurrency — optimize for concurrency
    BATCH = "BATCH"  # long, low-concurrency — optimize for throughput
    ETL = "ETL"  # scheduled bursts — optimize auto-suspend
    MIXED = "MIXED"  # bimodal — recommend splitting
    DORMANT = "DORMANT"  # no activity — recommend removal


def classify_workload(
    *,
    query_count: int,
    p50_seconds: float,
    p95_seconds: float | None = None,
    active_hours: int | None = None,
    short_p50_seconds: float = 5.0,
    long_p50_seconds: float = 60.0,
) -> WorkloadClass:
    """Classify a warehouse's workload shape.

    Args:
        query_count: number of queries observed in the lookback window.
        p50_seconds: median query duration.
        p95_seconds: 95th-percentile query duration.  When supplied and much
            larger than p50, signals a bimodal distribution → MIXED.
        active_hours: number of distinct hours-of-day the warehouse ran.
            When small (<= 3), signals ETL-style scheduled bursts.
        short_p50_seconds: boundary below which queries are "short".
        long_p50_seconds: boundary above which queries are "long".

    Returns:
        A `WorkloadClass` appropriate for sizing decisions.
    """
    if query_count == 0:
        return WorkloadClass.DORMANT

    # Strong bimodality: p95/p50 >> 1 AND p50 is short. Indicates short
    # interactive traffic commingled with occasional long batch jobs.
    if p95_seconds is not None and p50_seconds > 0:
        if p95_seconds >= long_p50_seconds and p50_seconds < short_p50_seconds * 2:
            return WorkloadClass.MIXED

    if p50_seconds < short_p50_seconds:
        return WorkloadClass.INTERACTIVE

    if p50_seconds >= long_p50_seconds:
        # Long queries in a narrow active window → ETL; long queries running
        # all day → BATCH.
        if active_hours is not None and active_hours <= 3:
            return WorkloadClass.ETL
        return WorkloadClass.BATCH

    # Between thresholds: treat as INTERACTIVE by default.
    return WorkloadClass.INTERACTIVE


def project_annual_savings(
    *,
    current_size: str,
    recommended_size: str | None,
    monthly_hours: float,
    credit_price: float,
) -> float:
    """Annualized dollar savings from a sizing change, or zero when not favorable.

    `recommended_size=None` signals elimination (consolidation) — full current-size
    cost becomes the savings.
    """
    current_rate = size_credit_rate(current_size)
    recommended_rate = 0 if recommended_size is None else size_credit_rate(recommended_size)
    if recommended_rate >= current_rate:
        return 0.0
    credit_delta_per_hour = current_rate - recommended_rate
    annual_credits = credit_delta_per_hour * monthly_hours * 12
    return round(annual_credits * credit_price, 2)
