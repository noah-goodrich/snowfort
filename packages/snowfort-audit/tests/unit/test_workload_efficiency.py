from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.workload import WorkloadEfficiencyCheck
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError


@pytest.fixture(name="rule")
def fixture_rule():
    evaluator = FinancialEvaluator(PricingConfig())
    return WorkloadEfficiencyCheck(evaluator)


def test_perf_006_oversized_query(rule):
    mock_cursor = MagicMock()

    # Mock row: WAREHOUSE_NAME, PARTITIONS_SCANNED, BYTES_SCANNED, QUERY_ID, WAREHOUSE_SIZE
    # LARGE (8 nodes) has parallelism capacity = 8 * 40 = 320.
    # 32 partitions / 320 = 0.1 ratio (Lower than 0.2)
    # 5GB scanned / 100GB tier = 0.05 (Tier not satisfied)
    mock_row = ["MY_WH", 32, 5 * 1024**3, "query_123", "LARGE"]
    mock_cursor.fetchall.return_value = [mock_row]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "PERF_006"
    assert v.resource_name == "query_123"
    assert "Oversized" in v.message
    # Note: Case sensitivity check. Implementation uses "Small".
    assert "Move to Small" in v.message or "Move to X-Small" in v.message


def test_perf_006_under_limit_but_tier_satisfied(rule):
    mock_cursor = MagicMock()
    # LARGE with 32 partitions (0.1 ratio) but scanning 200GB (Tier satisfied)
    mock_row = ["MY_WH", 32, 200 * 1024**3, "query_456", "LARGE"]
    mock_cursor.fetchall.return_value = [mock_row]

    violations = rule.check_online(mock_cursor)

    # Should NOT be a violation because tier is satisfied
    assert len(violations) == 0


def test_perf_006_well_saturated_parallelism(rule):
    mock_cursor = MagicMock()
    # LARGE with 100 partitions (0.31 ratio > 0.2)
    mock_row = ["MY_WH", 100, 50 * 1024**3, "query_789", "LARGE"]
    mock_cursor.fetchall.return_value = [mock_row]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == 0


def test_perf_006_empty_history(rule):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []

    violations = rule.check_online(mock_cursor)
    assert len(violations) == 0


def test_perf_006_exception_handling(rule):
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = SnowflakeConnectorError("DB Fail")

    with pytest.raises(RuleExecutionError):
        rule.check_online(mock_cursor)
