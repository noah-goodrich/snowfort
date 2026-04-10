"""Tests for remaining rule modules: extensions, strategy, type_advisor, workload, ops."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cost_extensions import WorkloadHeterogeneityCheck
from snowfort_audit.domain.rules.ops_extensions import ResizeChurnCheck
from snowfort_audit.domain.rules.perf_extensions import CacheContentionCheck
from snowfort_audit.domain.rules.strategy import IsolationPivotCheck
from snowfort_audit.domain.rules.type_advisor import Gen2UpgradeCheck, SnowparkOptimizationCheck


def test_workload_heterogeneity():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 5000.0, 100.0, 2000.0, 500.0, 2000)]
    v = WorkloadHeterogeneityCheck().check_online(c)
    assert len(v) == 1
    assert "Jack" in v[0].message


def test_workload_heterogeneity_ok():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 50.0, 100.0, 50.0, 100.0, 2000)]
    assert WorkloadHeterogeneityCheck().check_online(c) == []


def test_workload_heterogeneity_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        WorkloadHeterogeneityCheck().check_online(c)


def test_resize_churn():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 10)]
    v = ResizeChurnCheck().check_online(c)
    assert len(v) == 1
    assert "10" in v[0].message


def test_resize_churn_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert ResizeChurnCheck().check_online(c) == []


def test_resize_churn_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert ResizeChurnCheck().check_online(c) == []


def test_cache_contention():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 500, 0.05, 200, 50 * 1024**3)]
    v = CacheContentionCheck().check_online(c)
    assert len(v) == 1


def test_cache_contention_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert CacheContentionCheck().check_online(c) == []


def test_cache_contention_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        CacheContentionCheck().check_online(c)


def test_isolation_pivot():
    c = MagicMock()
    c.fetchall.return_value = [("WH", "Q123", 500 * 1024**3, 1 * 1024**3, 5000)]
    v = IsolationPivotCheck().check_online(c)
    assert len(v) == 1
    assert "Q123" in v[0].resource_name


def test_isolation_pivot_below_threshold():
    c = MagicMock()
    c.fetchall.return_value = [("WH", "Q1", 10, 100, 500)]
    assert IsolationPivotCheck().check_online(c) == []


def test_isolation_pivot_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        IsolationPivotCheck().check_online(c)


def test_gen2_upgrade():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 80, 100)]
    v = Gen2UpgradeCheck().check_online(c)
    assert len(v) == 1
    assert "Gen 2" in v[0].message


def test_gen2_upgrade_low_dml():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 10, 100)]
    assert Gen2UpgradeCheck().check_online(c) == []


def test_gen2_upgrade_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert Gen2UpgradeCheck().check_online(c) == []


def test_snowpark_optimization():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 50, 200)]
    v = SnowparkOptimizationCheck().check_online(c)
    assert len(v) == 1


def test_snowpark_optimization_low_spill():
    c = MagicMock()
    c.fetchall.return_value = [("WH", 5, 200)]
    assert SnowparkOptimizationCheck().check_online(c) == []


def test_snowpark_optimization_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert SnowparkOptimizationCheck().check_online(c) == []
