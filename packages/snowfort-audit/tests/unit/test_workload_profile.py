"""Tests for domain.workload_profile: classification + savings projection (Directive B)."""

from snowfort_audit.domain.workload_profile import (
    WorkloadClass,
    classify_workload,
    project_annual_savings,
    size_credit_rate,
)

# ── size_credit_rate ─────────────────────────────────────────────────────────


def test_credit_rate_xsmall_is_1():
    assert size_credit_rate("X-SMALL") == 1


def test_credit_rate_xl_is_16():
    assert size_credit_rate("X-LARGE") == 16


def test_credit_rate_6xl_is_512():
    assert size_credit_rate("6X-LARGE") == 512


def test_credit_rate_unknown_defaults_to_1():
    assert size_credit_rate("WHAT") == 1


# ── classify_workload ────────────────────────────────────────────────────────


def test_classify_dormant_zero_queries():
    assert classify_workload(query_count=0, p50_seconds=0.0) == WorkloadClass.DORMANT


def test_classify_interactive_short_p50():
    assert classify_workload(query_count=100, p50_seconds=2.0) == WorkloadClass.INTERACTIVE


def test_classify_batch_long_p50():
    assert classify_workload(query_count=50, p50_seconds=120.0) == WorkloadClass.BATCH


def test_classify_mixed_when_short_and_long_coexist():
    # Bimodal: 60% short, 40% long, high variance → MIXED
    assert classify_workload(query_count=100, p50_seconds=3.0, p95_seconds=180.0) == WorkloadClass.MIXED


def test_classify_etl_scheduled_burst():
    # Long queries but low variance (unimodal batch) + concentrated in short windows
    assert (
        classify_workload(
            query_count=20,
            p50_seconds=300.0,
            p95_seconds=360.0,
            active_hours=2,
        )
        == WorkloadClass.ETL
    )


def test_classify_thresholds_are_tunable():
    # Custom short/long split: P50=6s counts as interactive when threshold bumps to 10s
    assert classify_workload(query_count=100, p50_seconds=6.0, short_p50_seconds=10.0) == WorkloadClass.INTERACTIVE


# ── project_annual_savings ───────────────────────────────────────────────────


def test_savings_downsize_large_to_medium():
    # LARGE = 8 credits/hr, MEDIUM = 4 credits/hr. 100 hrs/month → 1200 hrs/yr.
    # Delta = (8-4) * 1200 = 4800 credits/yr * $3 = $14,400
    savings = project_annual_savings(
        current_size="LARGE",
        recommended_size="MEDIUM",
        monthly_hours=100,
        credit_price=3.0,
    )
    assert savings == 14_400.0


def test_savings_consolidation_merges_two_warehouses():
    # Two mediums running separately → one medium merged. One warehouse worth of hours saved.
    savings = project_annual_savings(
        current_size="MEDIUM",
        recommended_size=None,  # elimination
        monthly_hours=50,
        credit_price=3.0,
    )
    # 4 credits/hr × 50 × 12 = 2400 credits → $7200
    assert savings == 7_200.0


def test_savings_upsize_returns_zero_or_negative():
    # If "recommended" is larger than current, we don't claim savings.
    savings = project_annual_savings(
        current_size="SMALL",
        recommended_size="LARGE",
        monthly_hours=100,
        credit_price=3.0,
    )
    assert savings == 0.0  # no claimed savings when upsizing


def test_savings_identical_sizes_is_zero():
    assert (
        project_annual_savings(
            current_size="MEDIUM",
            recommended_size="MEDIUM",
            monthly_hours=100,
            credit_price=3.0,
        )
        == 0.0
    )
