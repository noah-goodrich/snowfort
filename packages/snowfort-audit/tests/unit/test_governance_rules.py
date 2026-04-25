from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity
from snowfort_audit.domain.rules.governance import (
    AccountBudgetEnforcement,
    FutureGrantsAntiPatternCheck,
    InboundShareRiskCheck,
    ObjectDocumentationCheck,
    OutboundShareRiskCheck,
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
        err1 = Exception("BUDGETS missing")
        err1.errno = 2003
        err2 = Exception("BC_USAGE unavailable")
        err2.errno = 2003
        mock_cursor.execute.side_effect = [err1, err2]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "not found or not accessible" in violations[0].message


# ---------------------------------------------------------------------------
# Regression: GOV_006 / GOV_007 column names
# ---------------------------------------------------------------------------


def test_gov006_sql_uses_type_imported_database():
    """GOV_006 must query DATABASES with TYPE='IMPORTED DATABASE', not SHARE_NAME."""
    rule = InboundShareRiskCheck()
    c = MagicMock()
    c.fetchall.return_value = []
    rule.check_online(c)
    sql = c.execute.call_args[0][0]
    assert "IMPORTED DATABASE" in sql
    assert "DATABASE_OWNER" in sql
    assert "SHARE_NAME" not in sql


def test_gov007_sql_uses_name_not_share_name():
    """GOV_007 must query SHARES with NAME, not SHARE_NAME; no SHARE_KIND."""
    rule = OutboundShareRiskCheck()
    c = MagicMock()
    c.fetchall.return_value = []
    rule.check_online(c)
    sql = c.execute.call_args[0][0]
    assert "SELECT NAME" in sql
    assert "SHARE_NAME" not in sql
    assert "SHARE_KIND" not in sql
    assert "DELETED_ON" in sql
