from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rules.type_advisor import Gen2UpgradeCheck, SnowparkOptimizationCheck


class TestTypeAdvisorRules:
    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        return MagicMock()

    def test_gen2_upgrade_check(self, mock_cursor):
        rule = Gen2UpgradeCheck()

        # Mock Data: WH_NAME, DML_CREDITS, TOTAL_CREDITS
        # WH1: 8 credits DML, 10 Total (80% DML) -> Flag
        # WH2: 1 credit DML, 10 Total (10% DML) -> Pass
        mock_cursor.fetchall.return_value = [("WH_ETL", 8.0, 10.0), ("WH_BI", 1.0, 10.0)]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "WH_ETL"
        assert "Upgrade to Gen 2" in violations[0].message

    def test_snowpark_optimization_check(self, mock_cursor):
        rule = SnowparkOptimizationCheck()
        # Same logic as specific workload check but at Warehouse level aggregator
        # Mock: WH_NAME, SPILL_QUERY_COUNT, TOTAL_QUERY_COUNT
        # WH1: 300 spilling queries out of 1000 (30%) -> Flag
        mock_cursor.fetchall.return_value = [("WH_ML_TRAIN", 300, 1000)]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Switch to SNOWPARK-OPTIMIZED" in violations[0].message
