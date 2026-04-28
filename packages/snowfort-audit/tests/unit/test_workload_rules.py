from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.workload import SpillingMemoryCheck, WorkloadEfficiencyCheck


class TestWorkloadRules:
    @pytest.fixture
    def evaluator(self):
        return FinancialEvaluator(PricingConfig())

    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        cursor = MagicMock()
        return cursor

    def test_workload_efficiency_check(self, evaluator, mock_cursor):
        rule = WorkloadEfficiencyCheck(evaluator)

        # Mock Data: [WH_NAME, PARTITIONS, BYTES, QUERY_ID, WH_SIZE]
        # Row 1: Warehouse=LARGE (8 nodes), Partitions=10, Bytes=500MB (Oversized!)
        # Row 2: Warehouse=SMALL (2 nodes), Partitions=80, Bytes=5GB (Good)
        mock_cursor.fetchall.return_value = [
            ("WH_LARGE", 10, 500 * 1024 * 1024, "query_1", "LARGE"),
            ("WH_SMALL", 80, 5 * 1024 * 1024 * 1024, "query_2", "SMALL"),
        ]

        violations = rule.check_online(mock_cursor)

        # Should flag Query 1
        assert len(violations) == 1
        assert violations[0].resource_name == "query_1"
        assert "Oversized" in violations[0].message
        assert "Projected Savings" in violations[0].message

    def test_spilling_memory_check_standard_upsize(self, evaluator, mock_cursor):
        rule = SpillingMemoryCheck(evaluator)

        # Spilled Remote = 20GB. Scanned=200GB. Ratio = 0.1 (< 0.2)
        mock_cursor.fetchall.return_value = [
            ("WH_MED", "STANDARD", 20 * 1024**3, 200 * 1024**3, 0.8, "query_spill", "MEDIUM")
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Undersized" in violations[0].message
        assert "Projected Cost" in violations[0].message
        assert "Upgrade to LARGE" in violations[0].message

    def test_spilling_memory_check_snowpark_pivot(self, evaluator, mock_cursor):
        rule = SpillingMemoryCheck(evaluator)

        # Mock Columns: [WH_NAME, WH_TYPE, SPILL_REMOTE, BYTES_SCANNED, AVG_CPU, QUERY_ID, WH_SIZE]
        # Scenario: 50GB Spill, 100GB Scanned (50%). -> Candidate for Snowpark!
        mock_cursor.fetchall.return_value = [
            ("WH_LG", "STANDARD", 50 * 1024**3, 100 * 1024**3, 0.1, "query_mem_bound", "LARGE")
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "SNOWPARK-OPTIMIZED" in violations[0].message


# ---------------------------------------------------------------------------
# AC-1: SpillingMemoryCheck must raise RuleExecutionError, not swallow
# ---------------------------------------------------------------------------


class TestSpillingMemoryCheckErrorPropagation:
    def test_unexpected_error_raises_rule_execution_error(self):
        """Non-SF error in check_online must raise RuleExecutionError."""
        evaluator = FinancialEvaluator(PricingConfig())
        rule = SpillingMemoryCheck(evaluator)
        c = MagicMock()
        c.execute.side_effect = RuntimeError("unexpected query failure")
        with pytest.raises(RuleExecutionError):
            rule.check_online(c)

    def test_allowlisted_error_returns_empty(self):
        """Allowlisted SF error (errno 2003) → []."""
        evaluator = FinancialEvaluator(PricingConfig())
        rule = SpillingMemoryCheck(evaluator)
        c = MagicMock()
        err = Exception("Object not found")
        err.errno = 2003
        c.execute.side_effect = err
        assert rule.check_online(c) == []
