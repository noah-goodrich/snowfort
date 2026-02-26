from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rules.strategy import IsolationPivotCheck


class TestStrategyRules:
    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        return MagicMock()

    def test_isolation_pivot_check(self, mock_cursor):
        rule = IsolationPivotCheck()

        # Mock Data:
        # [WH_NAME, QUERY_ID, BYTES_SCANNED, WH_AVG_BYTES, WH_QUERY_COUNT]
        # Query 1: Scans 500GB. Average query on this WH scans 0.1GB. -> ISOLATE
        # Query 2: Scans 0.2GB. Average query scans 0.1GB. -> OK
        mock_cursor.fetchall.return_value = [
            ("WH_GENERAL", "q_elephant", 500 * 1024**3, 0.1 * 1024**3, 5000),
            ("WH_GENERAL", "q_mouse", 0.2 * 1024**3, 0.1 * 1024**3, 5000),
        ]

        violations = rule.check_online(mock_cursor)

        assert len(violations) == 1
        assert violations[0].resource_name == "q_elephant"
        assert "Isolation Pivot" in violations[0].message
        assert "Move this query" in violations[0].message
