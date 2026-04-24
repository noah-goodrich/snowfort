"""Tests for Directive B pilot sizing rules (PERF_020, COST_036, COST_037)."""

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
    DormantWarehouseCheck,
    ExcessiveTimeTravelRetentionCheck,
    ThreeLayerUtilizationCheck,
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
