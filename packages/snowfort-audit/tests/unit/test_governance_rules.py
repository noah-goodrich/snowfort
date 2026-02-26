from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity
from snowfort_audit.domain.rules.governance import (
    AccountBudgetEnforcement,
    FutureGrantsAntiPatternCheck,
    ObjectDocumentationCheck,
)


class TestGovernanceRules:
    EXPECTED_MISSING_COMMENTS_COUNT = 2

    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        return cursor

    def test_future_grants_check(self, mock_cursor):
        rule = FutureGrantsAntiPatternCheck()

        # Scenario: No future grants (Clean)
        mock_cursor.fetchall.return_value = []
        assert len(rule.check_online(mock_cursor)) == 0

        # Scenario: Future grant found
        mock_cursor.fetchall.return_value = [("ROLE_A", "FUTURE_TABLE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "ROLE_A"
        assert "Uses Future Grants" in violations[0].message

    def test_object_documentation_check(self, mock_cursor):
        rule = ObjectDocumentationCheck()

        # Scenario: All tables commented (Clean)
        mock_cursor.fetchall.return_value = []
        assert len(rule.check_online(mock_cursor)) == 0

        # Scenario: Missing comments
        mock_cursor.fetchall.return_value = [("RAW_PROD", "CUSTOMERS"), ("ANALYTICS_PROD", "KPI_VIEW")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == self.EXPECTED_MISSING_COMMENTS_COUNT
        assert violations[0].resource_name == "RAW_PROD.CUSTOMERS"
        assert violations[0].severity == Severity.LOW

    def test_account_budget_enforcement_no_budgets(self):
        rule = AccountBudgetEnforcement()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [0]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "No active Snowflake Budgets" in violations[0].message

    def test_account_budget_enforcement_budgets_unavailable(self):
        rule = AccountBudgetEnforcement()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [Exception("BUDGETS missing"), Exception("BC_USAGE unavailable")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "not found or not accessible" in violations[0].message
