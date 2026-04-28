"""Tests for Directive B sizing rules (PERF_020–023, COST_034–037)."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.conventions import (
    RuleThresholdConventions,
    SnowfortConventions,
    StorageThresholds,
    WarehouseSizingThresholds,
)
from snowfort_audit.domain.rule_definitions import FindingCategory, RuleExecutionError, Severity
from snowfort_audit.domain.rules.sizing import (
    AutoSuspendOptimizationCheck,
    CloneSprawlCheck,
    ColdStorageMigrationCheck,
    ConsolidationCandidatesCheck,
    DormantWarehouseCheck,
    ExcessiveTimeTravelRetentionCheck,
    QueryDurationAnomalyCheck,
    SavingsProjectionCheck,
    StaleTableStorageImpactCheck,
    ThreeLayerUtilizationCheck,
    WorkloadIsolationCheck,
)

# ── PERF_020: Three-Layer Utilization Profile ────────────────────────────────


def test_perf020_flags_underutilized_warehouse():
    c = MagicMock()
    # (WAREHOUSE_NAME, p50_running, p50_queued, p95_peak)
    c.fetchall.return_value = [("DEV_WH", 0.05, 0.01, 0.5)]
    violations = ThreeLayerUtilizationCheck().check_online(c)
    assert len(violations) == 1
    assert "underutilized" in violations[0].message.lower()
    assert violations[0].severity == Severity.MEDIUM
    assert violations[0].category == FindingCategory.ACTIONABLE


def test_perf020_flags_overloaded_warehouse():
    c = MagicMock()
    c.fetchall.return_value = [("PROD_WH", 0.8, 0.4, 2.0)]
    violations = ThreeLayerUtilizationCheck().check_online(c)
    assert len(violations) == 1
    assert "overloaded" in violations[0].message.lower()


def test_perf020_healthy_warehouse_no_violation():
    c = MagicMock()
    c.fetchall.return_value = [("HEALTHY_WH", 0.5, 0.05, 1.2)]
    assert ThreeLayerUtilizationCheck().check_online(c) == []


def test_perf020_threshold_override():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(warehouse_sizing=WarehouseSizingThresholds(utilization_underused_p50=0.02))
    )
    c = MagicMock()
    # P50 = 0.05 — now above the tightened underused threshold (0.02) and below default (0.10)
    c.fetchall.return_value = [("DEV_WH", 0.05, 0.01, 0.5)]
    assert ThreeLayerUtilizationCheck(conventions=conv).check_online(c) == []


def test_perf020_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("boom")
    with pytest.raises(RuleExecutionError):
        ThreeLayerUtilizationCheck().check_online(c)


# ── COST_036: Dormant Warehouse ──────────────────────────────────────────────


def test_cost036_flags_dormant_warehouse_not_suspended():
    c = MagicMock()
    # (WAREHOUSE_NAME, STATE, DAYS_IDLE)
    c.fetchall.return_value = [("OLD_WH", "STARTED", 45)]
    violations = DormantWarehouseCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.HIGH
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "45" in violations[0].message


def test_cost036_skips_suspended_warehouse():
    c = MagicMock()
    c.fetchall.return_value = [("SUSPENDED_WH", "SUSPENDED", 60)]
    assert DormantWarehouseCheck().check_online(c) == []


def test_cost036_skips_active_warehouse_under_threshold():
    c = MagicMock()
    c.fetchall.return_value = [("ACTIVE_WH", "STARTED", 5)]
    assert DormantWarehouseCheck().check_online(c) == []


def test_cost036_threshold_override():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(warehouse_sizing=WarehouseSizingThresholds(dormant_days=7))
    )
    c = MagicMock()
    c.fetchall.return_value = [("WH", "STARTED", 10)]
    # Default threshold 30 → no violation; override to 7 → violation.
    assert len(DormantWarehouseCheck(conventions=conv).check_online(c)) == 1


# ── COST_037: Excessive Time Travel Retention ────────────────────────────────


def test_cost037_flags_excessive_retention():
    c = MagicMock()
    # (qualified_name, active_bytes, retention_days, query_count_30d)
    c.fetchall.return_value = [("DB.SCH.BIG_TABLE", 2 * 1024**4, 30, 5)]
    violations = ExcessiveTimeTravelRetentionCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.MEDIUM


def test_cost037_skips_small_tables():
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.SMALL", 100 * 1024**3, 30, 0)]  # 100GB < 1TB default
    assert ExcessiveTimeTravelRetentionCheck().check_online(c) == []


def test_cost037_skips_frequently_queried_tables():
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.HOT", 2 * 1024**4, 30, 500)]  # 500 queries/month → hot
    assert ExcessiveTimeTravelRetentionCheck().check_online(c) == []


def test_cost037_retention_at_default_boundary():
    # retention == excessive_retention_min_days (7) → NOT flagged (strictly greater).
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.T", 2 * 1024**4, 7, 0)]
    assert ExcessiveTimeTravelRetentionCheck().check_online(c) == []


def test_cost037_convention_overrides():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(
            storage=StorageThresholds(excessive_retention_min_bytes=50 * 1024**3)  # 50 GB
        )
    )
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.MED", 100 * 1024**3, 30, 0)]  # 100GB > 50GB override
    assert len(ExcessiveTimeTravelRetentionCheck(conventions=conv).check_online(c)) == 1


# ── PERF_021: Query Duration Anomaly ─────────────────────────────────────────


def test_perf021_flags_anomalous_warehouse():
    c = MagicMock()
    # (WAREHOUSE_NAME, p50_seconds, p95_seconds, query_count)
    # ratio = 120 / 2 = 60 — exceeds default 10x threshold
    c.fetchall.return_value = [("PROD_WH", 2.0, 120.0, 500)]
    violations = QueryDurationAnomalyCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.LOW
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "PROD_WH" in violations[0].message
    assert "60.0" in violations[0].message or "60x" in violations[0].message.lower()


def test_perf021_skips_normal_ratio():
    c = MagicMock()
    # ratio = 15 / 5 = 3 — below default 10x threshold
    c.fetchall.return_value = [("DEV_WH", 5.0, 15.0, 200)]
    assert QueryDurationAnomalyCheck().check_online(c) == []


def test_perf021_skips_zero_p50():
    c = MagicMock()
    # p50 = 0 → division guard
    c.fetchall.return_value = [("BAD_WH", 0.0, 100.0, 50)]
    assert QueryDurationAnomalyCheck().check_online(c) == []


def test_perf021_threshold_override():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(warehouse_sizing=WarehouseSizingThresholds(duration_anomaly_ratio=3.0))
    )
    c = MagicMock()
    # ratio = 15 / 4 = 3.75 — above overridden threshold of 3x
    c.fetchall.return_value = [("WH", 4.0, 15.0, 100)]
    assert len(QueryDurationAnomalyCheck(conventions=conv).check_online(c)) == 1


def test_perf021_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("boom")
    with pytest.raises(RuleExecutionError):
        QueryDurationAnomalyCheck().check_online(c)


# ── PERF_022: Workload Isolation ──────────────────────────────────────────────


def test_perf022_flags_mixed_workload():
    c = MagicMock()
    # (WAREHOUSE_NAME, short_hours, long_hours, total_hours)
    # short_hours=8, long_hours=4 → mixed
    c.fetchall.return_value = [("MIXED_WH", 8, 4, 24)]
    violations = WorkloadIsolationCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.MEDIUM
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "MIXED_WH" in violations[0].message


def test_perf022_skips_short_only_workload():
    c = MagicMock()
    # No long hours → uniform interactive workload
    c.fetchall.return_value = [("INTERACTIVE_WH", 20, 0, 24)]
    assert WorkloadIsolationCheck().check_online(c) == []


def test_perf022_skips_long_only_workload():
    c = MagicMock()
    # No short hours → pure batch
    c.fetchall.return_value = [("BATCH_WH", 0, 12, 24)]
    assert WorkloadIsolationCheck().check_online(c) == []


def test_perf022_threshold_override():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(
            warehouse_sizing=WarehouseSizingThresholds(
                workload_split_short_p50_seconds=2.0,
                workload_split_long_p50_seconds=120.0,
            )
        )
    )
    c = MagicMock()
    # With tighter thresholds, short_hours=3, long_hours=3 still flags
    c.fetchall.return_value = [("WH", 3, 3, 24)]
    assert len(WorkloadIsolationCheck(conventions=conv).check_online(c)) == 1


def test_perf022_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("network error")
    with pytest.raises(RuleExecutionError):
        WorkloadIsolationCheck().check_online(c)


# ── PERF_023: Auto-Suspend Optimization ──────────────────────────────────────


def test_perf023_flags_tighten_recommendation():
    c = MagicMock()
    # (WAREHOUSE_NAME, p75_gap_seconds, auto_suspend_seconds)
    # P75 gap = 45s, auto_suspend = 300s → tighten
    c.fetchall.return_value = [("IDLE_WH", 45.0, 300)]
    violations = AutoSuspendOptimizationCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.LOW
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "tighten" in violations[0].message.lower() or "reduce" in violations[0].message.lower()


def test_perf023_flags_already_aggressive():
    c = MagicMock()
    # P75 gap = 3600s, auto_suspend = 30s → 3600 > 10*30 = 300 → already aggressive
    c.fetchall.return_value = [("BURSTY_WH", 3600.0, 30)]
    violations = AutoSuspendOptimizationCheck().check_online(c)
    assert len(violations) == 1
    assert "aggressive" in violations[0].message.lower() or "frequent" in violations[0].message.lower()


def test_perf023_skips_well_configured():
    c = MagicMock()
    # P75 gap = 120s, auto_suspend = 300s, ratio = 300/120 = 2.5 (between 1x and 10x)
    # gap >= auto_suspend (120 < 300 → should flag tighten... let me reconsider)
    # To skip: gap should be >= auto_suspend and < 10*auto_suspend
    # P75 gap = 400s, auto_suspend = 300s → gap >= auto_suspend and gap < 10*300=3000 → skip
    c.fetchall.return_value = [("GOOD_WH", 400.0, 300)]
    assert AutoSuspendOptimizationCheck().check_online(c) == []


def test_perf023_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("timeout")
    with pytest.raises(RuleExecutionError):
        AutoSuspendOptimizationCheck().check_online(c)


# ── COST_034: Consolidation Candidates ───────────────────────────────────────


def test_cost034_flags_consolidation_pair():
    c = MagicMock()
    # (WAREHOUSE_NAME, p50_utilization)
    # 0.15 + 0.20 = 0.35 < 0.60 threshold → flag pair
    c.fetchall.return_value = [("WH_A", 0.15), ("WH_B", 0.20)]
    violations = ConsolidationCandidatesCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.MEDIUM
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "WH_A" in violations[0].message and "WH_B" in violations[0].message


def test_cost034_skips_when_combined_too_high():
    c = MagicMock()
    # 0.40 + 0.35 = 0.75 > 0.60 threshold → no flag
    c.fetchall.return_value = [("WH_A", 0.40), ("WH_B", 0.35)]
    assert ConsolidationCandidatesCheck().check_online(c) == []


def test_cost034_skips_single_warehouse():
    c = MagicMock()
    c.fetchall.return_value = [("LONE_WH", 0.10)]
    assert ConsolidationCandidatesCheck().check_online(c) == []


def test_cost034_threshold_override():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(
            warehouse_sizing=WarehouseSizingThresholds(consolidation_combined_p50_max=0.30)
        )
    )
    c = MagicMock()
    # 0.15 + 0.20 = 0.35 > 0.30 tightened threshold → no flag
    c.fetchall.return_value = [("WH_A", 0.15), ("WH_B", 0.20)]
    assert ConsolidationCandidatesCheck(conventions=conv).check_online(c) == []


def test_cost034_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("access denied")
    with pytest.raises(RuleExecutionError):
        ConsolidationCandidatesCheck().check_online(c)


# ── COST_035: Savings Projection ─────────────────────────────────────────────


def test_cost035_flags_savings_opportunity():
    c = MagicMock()
    # (WAREHOUSE_NAME, WAREHOUSE_SIZE, total_credits_lookback, p50_running)
    # LARGE at 20% utilization → recommend MEDIUM, project savings
    c.fetchall.return_value = [("BIG_WH", "LARGE", 240.0, 0.07)]
    violations = SavingsProjectionCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.LOW
    assert violations[0].category == FindingCategory.INFORMATIONAL
    assert "BIG_WH" in violations[0].message


def test_cost035_includes_dollar_amount():
    c = MagicMock()
    # LARGE (8 credits/hr), 240 credits → 30 hrs/month, downsize to MEDIUM (4), save 120/mo
    # annual = 120 * 12 = 1440 credits × $3 = $4320
    c.fetchall.return_value = [("BIG_WH", "LARGE", 240.0, 0.07)]
    violations = SavingsProjectionCheck().check_online(c)
    assert len(violations) == 1
    assert "$" in violations[0].message


def test_cost035_skips_xsmall_no_downsize():
    c = MagicMock()
    # X-SMALL can't be downsized further
    c.fetchall.return_value = [("TINY_WH", "X-SMALL", 30.0, 0.05)]
    assert SavingsProjectionCheck().check_online(c) == []


def test_cost035_threshold_override_credit_price():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(warehouse_sizing=WarehouseSizingThresholds(credit_price_per_hour=4.0))
    )
    c = MagicMock()
    c.fetchall.return_value = [("WH", "LARGE", 240.0, 0.07)]
    violations = SavingsProjectionCheck(conventions=conv).check_online(c)
    assert len(violations) == 1
    # Higher credit price → larger dollar savings in the message
    assert "$" in violations[0].message


def test_cost035_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("metering unavailable")
    with pytest.raises(RuleExecutionError):
        SavingsProjectionCheck().check_online(c)


# ── COST_038: Clone Sprawl ────────────────────────────────────────────────────


def test_cost038_flags_schema_with_too_many_clones():
    c = MagicMock()
    # (TABLE_CATALOG, TABLE_SCHEMA, clone_count, oldest_clone_age_days)
    c.fetchall.return_value = [("DB", "PUBLIC", 8, 30)]
    violations = CloneSprawlCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.LOW
    assert violations[0].category == FindingCategory.ACTIONABLE
    assert "8" in violations[0].message


def test_cost038_flags_stale_clone():
    c = MagicMock()
    # Only 2 clones but oldest is 120 days (> 90 default)
    c.fetchall.return_value = [("DB", "STAGING", 2, 120)]
    violations = CloneSprawlCheck().check_online(c)
    assert len(violations) == 1
    assert "120" in violations[0].message


def test_cost038_skips_healthy_schema():
    c = MagicMock()
    # 3 clones, oldest is 30 days — both below thresholds
    c.fetchall.return_value = [("DB", "PUBLIC", 3, 30)]
    assert CloneSprawlCheck().check_online(c) == []


def test_cost038_convention_overrides():
    conv = SnowfortConventions(thresholds=RuleThresholdConventions(storage=StorageThresholds(clone_max_per_schema=2)))
    c = MagicMock()
    # 3 clones — below default (5) but above override (2)
    c.fetchall.return_value = [("DB", "PUBLIC", 3, 10)]
    assert len(CloneSprawlCheck(conventions=conv).check_online(c)) == 1


def test_cost038_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("access denied")
    with pytest.raises(RuleExecutionError):
        CloneSprawlCheck().check_online(c)


# ── COST_039: Cold Storage Migration ──────────────────────────────────────────


def test_cost039_flags_cold_large_table():
    c = MagicMock()
    # (qualified_name, active_bytes, query_count_7d, clustering_key)
    c.fetchall.return_value = [("DB.SCH.HUGE", 200 * 1024**3, 0, None)]
    violations = ColdStorageMigrationCheck().check_online(c)
    assert len(violations) == 1
    assert violations[0].severity == Severity.MEDIUM
    assert violations[0].category == FindingCategory.INFORMATIONAL
    assert "HUGE" in violations[0].message


def test_cost039_skips_small_table():
    c = MagicMock()
    # 50 GB — below default 100 GB threshold
    c.fetchall.return_value = [("DB.SCH.SMALL", 50 * 1024**3, 0, None)]
    assert ColdStorageMigrationCheck().check_online(c) == []


def test_cost039_skips_actively_queried_table():
    c = MagicMock()
    # 200 GB but 5 queries/week — above threshold
    c.fetchall.return_value = [("DB.SCH.HOT", 200 * 1024**3, 5, None)]
    assert ColdStorageMigrationCheck().check_online(c) == []


def test_cost039_skips_clustered_table():
    c = MagicMock()
    # 200 GB, 0 queries, but has a clustering key
    c.fetchall.return_value = [("DB.SCH.CLUSTERED", 200 * 1024**3, 0, "LINEAR(col1)")]
    assert ColdStorageMigrationCheck().check_online(c) == []


def test_cost039_convention_overrides():
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(
            storage=StorageThresholds(cold_table_min_bytes=50 * 1024**3)  # 50 GB
        )
    )
    c = MagicMock()
    # 80 GB — above overridden threshold (50 GB), below default (100 GB)
    c.fetchall.return_value = [("DB.SCH.MED", 80 * 1024**3, 0, None)]
    assert len(ColdStorageMigrationCheck(conventions=conv).check_online(c)) == 1


def test_cost039_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("boom")
    with pytest.raises(RuleExecutionError):
        ColdStorageMigrationCheck().check_online(c)


# ── COST_040: Stale Table Storage Impact ──────────────────────────────────────


def test_cost040_ranks_stale_tables_by_impact():
    c = MagicMock()
    # (qualified_name, active_bytes, days_idle, impact_score)
    c.fetchall.return_value = [
        ("DB.SCH.BIG_OLD", 500 * 1024**3, 180, 500 * 1024**3 * 180),
        ("DB.SCH.SMALL_OLD", 10 * 1024**3, 365, 10 * 1024**3 * 365),
    ]
    violations = StaleTableStorageImpactCheck().check_online(c)
    assert len(violations) == 2
    assert violations[0].severity == Severity.LOW
    assert violations[0].category == FindingCategory.INFORMATIONAL
    assert "BIG_OLD" in violations[0].message


def test_cost040_no_stale_tables():
    c = MagicMock()
    c.fetchall.return_value = []
    assert StaleTableStorageImpactCheck().check_online(c) == []


def test_cost040_skips_recently_accessed():
    c = MagicMock()
    # days_idle = 0 → recently accessed, impact score = 0
    c.fetchall.return_value = [("DB.SCH.FRESH", 100 * 1024**3, 0, 0)]
    violations = StaleTableStorageImpactCheck().check_online(c)
    # days_idle=0 means no staleness to report
    assert violations == []


def test_cost040_convention_overrides():
    # StaleTableStorageImpactCheck doesn't have a direct threshold but uses
    # StorageThresholds — verify it can be constructed with custom conventions.
    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(storage=StorageThresholds(cold_table_min_bytes=50 * 1024**3))
    )
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.T", 200 * 1024**3, 90, 200 * 1024**3 * 90)]
    assert len(StaleTableStorageImpactCheck(conventions=conv).check_online(c)) == 1


def test_cost040_error_raises_rule_execution_error():
    c = MagicMock()
    c.execute.side_effect = RuntimeError("timeout")
    with pytest.raises(RuleExecutionError):
        StaleTableStorageImpactCheck().check_online(c)
