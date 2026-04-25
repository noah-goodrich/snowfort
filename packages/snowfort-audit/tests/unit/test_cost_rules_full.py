"""Tests for cost rules."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.conventions import SnowfortConventions, WarehouseConventions
from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cost import (
    AggressiveAutoSuspendCheck,
    AutomaticClusteringCostBenefitCheck,
    CloudServicesRatioCheck,
    DataTransferMonitoringCheck,
    HighChurnPermanentTableCheck,
    MultiClusterSafeguardCheck,
    PerWarehouseStatementTimeoutCheck,
    QASEligibilityRecommendationCheck,
    RunawayQueryCheck,
    SearchOptimizationCostBenefitCheck,
    StagingTableTypeOptimizationCheck,
    StaleTableDetectionCheck,
    UnderutilizedWarehouseCheck,
    UnusedMaterializedViewCheck,
    ZombieWarehouseCheck,
)


def test_auto_suspend_null_critical():
    r = AggressiveAutoSuspendCheck()
    v = r._check_warehouse_suspension(("MY_WH", "null"), {"name": 0, "auto_suspend": 1}, {})
    assert len(v) == 1 and v[0].severity.value == "CRITICAL"


def test_auto_suspend_exceeds():
    r = AggressiveAutoSuspendCheck()
    v = r._check_warehouse_suspension(("MY_WH", "600"), {"name": 0, "auto_suspend": 1}, {})
    assert len(v) == 1


def test_auto_suspend_ok():
    assert (
        AggressiveAutoSuspendCheck()._check_warehouse_suspension(("MY_WH", "1"), {"name": 0, "auto_suspend": 1}, {})
        == []
    )


def test_auto_suspend_conventions():
    conv = SnowfortConventions(warehouse=WarehouseConventions(auto_suspend_seconds=60))
    assert AggressiveAutoSuspendCheck(conventions=conv)._auto_suspend_limit() == 60


def test_auto_suspend_check_static():
    assert len(AggressiveAutoSuspendCheck().check({"type": "WAREHOUSE", "auto_suspend": "120"}, "WH")) == 1


def test_auto_suspend_check_static_ok():
    # Default threshold is now 30s; 1s is well within convention.
    assert AggressiveAutoSuspendCheck().check({"type": "WAREHOUSE", "auto_suspend": "1"}, "WH") == []


def test_aggressive_auto_suspend_too_high():
    """B2: auto_suspend > max_seconds (3600) → MEDIUM violation with dedicated message."""
    wh = ("BIG_WH", "7200")
    cols = {"name": 0, "auto_suspend": 1}
    violations = AggressiveAutoSuspendCheck()._check_warehouse_suspension(wh, cols, {})
    assert len(violations) == 1
    assert "7200" in violations[0].message
    assert "3600" in violations[0].message


def test_aggressive_auto_suspend_above_convention_below_max():
    """B2: auto_suspend > convention (30s) but ≤ max_seconds → convention violation."""
    wh = ("MED_WH", "600")
    cols = {"name": 0, "auto_suspend": 1}
    violations = AggressiveAutoSuspendCheck()._check_warehouse_suspension(wh, cols, {})
    assert len(violations) == 1
    assert "600" in violations[0].message


def test_aggressive_auto_suspend_within_convention():
    """B2: auto_suspend ≤ convention (30s) → no violation."""
    wh = ("FAST_WH", "30")
    cols = {"name": 0, "auto_suspend": 1}
    assert AggressiveAutoSuspendCheck()._check_warehouse_suspension(wh, cols, {}) == []


def test_auto_suspend_non_wh():
    assert AggressiveAutoSuspendCheck().check({"type": "DATABASE"}, "DB") == []


def test_zombie_wh():
    c = MagicMock()
    c.fetchall.side_effect = [[("ACTIVE",)], [("ACTIVE",), ("IDLE",)]]
    assert len(ZombieWarehouseCheck().check_online(c)) == 1


def test_zombie_wh_sql_uses_timestamp_column():
    """Regression: COST_002 must use TIMESTAMP (not START_TIME) for WAREHOUSE_EVENTS_HISTORY."""
    c = MagicMock()
    c.fetchall.side_effect = [[], []]
    ZombieWarehouseCheck().check_online(c)
    sql = c.execute.call_args_list[0][0][0]
    assert "WAREHOUSE_EVENTS_HISTORY" in sql
    assert "TIMESTAMP" in sql
    assert "START_TIME" not in sql


def test_zombie_wh_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ZombieWarehouseCheck().check_online(c)


def test_cloud_svc():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 15.5)]
    assert len(CloudServicesRatioCheck().check_online(c)) == 1


def test_cloud_svc_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        CloudServicesRatioCheck().check_online(c)


def test_runaway_high():
    c = MagicMock()
    c.fetchone.return_value = ("k", "172800")
    assert len(RunawayQueryCheck().check_online(c)) == 1


def test_runaway_ok():
    c = MagicMock()
    c.fetchone.return_value = ("k", "3600")
    assert RunawayQueryCheck().check_online(c) == []


def test_mcw():
    assert (
        len(
            MultiClusterSafeguardCheck().check(
                {"type": "WAREHOUSE", "max_cluster_count": "3", "scaling_policy": "STANDARD"}, "WH"
            )
        )
        == 1
    )


def test_mcw_economy():
    assert (
        MultiClusterSafeguardCheck().check(
            {"type": "WAREHOUSE", "max_cluster_count": "3", "scaling_policy": "ECONOMY"}, "WH"
        )
        == []
    )


def test_mcw_single():
    assert MultiClusterSafeguardCheck().check({"type": "WAREHOUSE", "max_cluster_count": "1"}, "WH") == []


def test_underutil():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 0.05)]
    assert len(UnderutilizedWarehouseCheck().check_online(c)) == 1


def test_underutil_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        UnderutilizedWarehouseCheck().check_online(c)


def test_high_churn():
    c = MagicMock()
    c.fetchall.return_value = [("DB.SCH.TBL", 100, 500)]
    assert len(HighChurnPermanentTableCheck().check_online(c)) == 1


def test_high_churn_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        HighChurnPermanentTableCheck().check_online(c)


def test_high_churn_exclusions():
    """B1: tables matching exclude_name_patterns are suppressed."""
    from snowfort_audit.domain.conventions import HighChurnThresholds, RuleThresholdConventions, SnowfortConventions

    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(
            high_churn=HighChurnThresholds(exclude_name_patterns=("*_CDC_*", "*_STAGING*"))
        )
    )
    c = MagicMock()
    # 3 rows: 2 should be excluded, 1 should remain
    c.fetchall.return_value = [
        ("DB.SCH.ORDERS_CDC_STREAM", 100, 500),
        ("DB.SCH.USERS_STAGING", 100, 400),
        ("DB.SCH.REAL_TABLE", 100, 350),
    ]
    rule = HighChurnPermanentTableCheck(conventions=conv)
    violations = rule.check_online(c)
    assert len(violations) == 1
    assert violations[0].resource_name == "DB.SCH.REAL_TABLE"


# ── AC-3: COST_012 CDC schema pattern → EXPECTED category + transient remediation ──


def test_high_churn_thresholds_cdc_default():
    """AC-3: HighChurnThresholds defaults cdc_schema_pattern to a broad CDC-tooling regex."""
    from snowfort_audit.domain.conventions import HighChurnThresholds

    h = HighChurnThresholds()
    assert h.cdc_schema_pattern  # non-empty default
    # Spot-check: should match typical CDC tooling schema names (case-insensitive)
    import re as _re

    pat = _re.compile(h.cdc_schema_pattern)
    for schema in ("STAGING", "staging", "RAW", "CDC", "FIVETRAN", "AIRBYTE", "STITCH", "HEVO"):
        assert pat.search(schema), f"Default pattern should match {schema!r}"


def test_high_churn_cdc_schema_expected_category():
    """AC-3: table in a CDC-pattern schema → category=EXPECTED + transient remediation."""
    from snowfort_audit.domain.rule_definitions import FindingCategory

    c = MagicMock()
    c.fetchall.return_value = [("RAW_CDC.PUBLIC.CUSTOMERS", 100, 500)]
    rule = HighChurnPermanentTableCheck()
    violations = rule.check_online(c)
    assert len(violations) == 1
    assert violations[0].category == FindingCategory.EXPECTED
    assert "transient" in (violations[0].remediation_instruction or "").lower()


def test_high_churn_non_cdc_actionable():
    """AC-3: table not matching CDC pattern → category=ACTIONABLE + default remediation."""
    from snowfort_audit.domain.rule_definitions import FindingCategory

    c = MagicMock()
    c.fetchall.return_value = [("ANALYTICS.PUBLIC.REVENUE", 100, 500)]
    rule = HighChurnPermanentTableCheck()
    violations = rule.check_online(c)
    assert len(violations) == 1
    assert violations[0].category == FindingCategory.ACTIONABLE


def test_high_churn_cdc_schema_custom_pattern():
    """AC-3: custom cdc_schema_pattern from conventions overrides default."""
    from snowfort_audit.domain.conventions import HighChurnThresholds, RuleThresholdConventions, SnowfortConventions
    from snowfort_audit.domain.rule_definitions import FindingCategory

    conv = SnowfortConventions(
        thresholds=RuleThresholdConventions(high_churn=HighChurnThresholds(cdc_schema_pattern=r"(?i)ingest"))
    )
    c = MagicMock()
    c.fetchall.return_value = [
        ("DB.INGEST.FOO", 100, 500),
        ("DB.RAW.BAR", 100, 500),  # no longer matches under custom pattern
    ]
    rule = HighChurnPermanentTableCheck(conventions=conv)
    violations = rule.check_online(c)
    assert len(violations) == 2
    cats = {v.resource_name: v.category for v in violations}
    assert cats["DB.INGEST.FOO"] == FindingCategory.EXPECTED
    assert cats["DB.RAW.BAR"] == FindingCategory.ACTIONABLE


def test_per_wh_timeout():
    c = MagicMock()
    c.fetchall.return_value = [("WH1",)]
    c.description = [("name",)]
    c.fetchone.return_value = ("k", "172800")
    assert len(PerWarehouseStatementTimeoutCheck().check_online(c)) == 1


def test_per_wh_timeout_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        PerWarehouseStatementTimeoutCheck().check_online(c)


def test_stale():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", 500000000)]
    assert len(StaleTableDetectionCheck().check_online(c)) == 1


def test_stale_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        StaleTableDetectionCheck().check_online(c)


def test_staging():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "STG_TBL", 10000, 5000)]
    assert len(StagingTableTypeOptimizationCheck().check_online(c)) == 1


def test_staging_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        StagingTableTypeOptimizationCheck().check_online(c)


def test_unused_mv():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "MV1")]
    assert len(UnusedMaterializedViewCheck().check_online(c)) == 1


def test_unused_mv_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        UnusedMaterializedViewCheck().check_online(c)


def test_data_transfer_high():
    c = MagicMock()
    c.fetchone.return_value = (200 * 1024**3, 50)
    assert len(DataTransferMonitoringCheck().check_online(c)) == 1


def test_data_transfer_low():
    c = MagicMock()
    c.fetchone.return_value = (1000, 2)
    assert DataTransferMonitoringCheck().check_online(c) == []


def test_data_transfer_none():
    c = MagicMock()
    c.fetchone.return_value = (None, 0)
    assert DataTransferMonitoringCheck().check_online(c) == []


def test_data_transfer_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        DataTransferMonitoringCheck().check_online(c)


def test_qas():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 600.0, 10)]
    assert len(QASEligibilityRecommendationCheck().check_online(c)) == 1


def test_qas_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        QASEligibilityRecommendationCheck().check_online(c)


def test_auto_clustering():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", "TBL", 5.0)]
    assert len(AutomaticClusteringCostBenefitCheck().check_online(c)) == 1


def test_auto_clustering_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        AutomaticClusteringCostBenefitCheck().check_online(c)


def test_search_opt():
    c = MagicMock()
    c.fetchall.return_value = [("DB", "SCH", 3.5, 100)]
    assert len(SearchOptimizationCostBenefitCheck().check_online(c)) == 1


def test_search_opt_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        SearchOptimizationCostBenefitCheck().check_online(c)
