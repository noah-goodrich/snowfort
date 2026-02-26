from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity
from snowfort_audit.domain.rules.security_advanced import (
    ReadOnlyRoleIntegrityCheck,
    ReadOnlyUserIntegrityCheck,
    ServiceRoleScopeCheck,
    ServiceUserScopeCheck,
)


class TestAdvancedSecurityRules:
    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        cursor = MagicMock()
        return cursor

    def test_service_role_scope_check_pass(self, mock_cursor):
        rule = ServiceRoleScopeCheck()
        # Mock returns empty list (SQL HAVING clause filters out compliant roles)
        mock_cursor.fetchall.return_value = []
        assert len(rule.check_online(mock_cursor)) == 0

    def test_service_role_scope_check_fail(self, mock_cursor):
        rule = ServiceRoleScopeCheck()
        # Mock returns a violator (SVC_ETL accesses 2 DBs)
        mock_cursor.fetchall.return_value = [("SVC_ETL_ROLE", 2)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "SVC_ETL_ROLE"
        assert "access to 2 DBs" in violations[0].message

    def test_readonly_integrity_fail(self, mock_cursor):
        rule = ReadOnlyRoleIntegrityCheck()
        # Mock returns a grant of INSERT to a RO role
        mock_cursor.fetchall.return_value = [("ANALYTICS_RO", "INSERT", "TABLE", "SALES_DATA")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "ANALYTICS_RO"
        assert violations[0].severity == Severity.CRITICAL

    def test_service_user_scope_check_fail(self, mock_cursor):
        rule = ServiceUserScopeCheck()
        mock_cursor.fetchall.return_value = [("SVC_BI_USER", 2)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "SVC_BI_USER"
        assert "2 DBs" in violations[0].message

    def test_readonly_user_integrity_fail(self, mock_cursor):
        rule = ReadOnlyUserIntegrityCheck()
        mock_cursor.fetchall.return_value = [("READER_RO", "UPDATE", "TABLE", "T1")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "READER_RO"
        assert violations[0].severity == Severity.CRITICAL
