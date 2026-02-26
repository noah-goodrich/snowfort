from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.domain.rules.ops import SLOThrottlerCheck


class TestOpsRules:
    @pytest.fixture
    def evaluator(self):
        return FinancialEvaluator(PricingConfig())

    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        return MagicMock()

    def test_slo_throttler_check(self, evaluator, mock_cursor):
        rule = SLOThrottlerCheck(evaluator, target_p95_ms=1000)  # Target 1s SLO

        # Mock Data: [WH_NAME, P95_DURATION_MS, WH_SIZE, QUERY_COUNT]
        # WH1: p95=100ms (10x faster than SLO). Size=LARGE. -> Downsize!
        # WH2: p95=900ms (Close to SLO). Size=SMALL. -> Keep.
        mock_cursor.fetchall.return_value = [("WH_FAST", 100, "LARGE", 5000), ("WH_OK", 900, "SMALL", 1000)]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "WH_FAST"
        assert "Downsize" in violations[0].message
        assert "p95 (100ms) << SLO (1000ms)" in violations[0].message
