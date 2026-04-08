"""Tests for OnlineScanUseCase."""

from unittest.mock import ANY, MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.domain.rules.governance import AccountBudgetEnforcement
from snowfort_audit.domain.rules.static import SelectStarCheck
from snowfort_audit.use_cases.online_scan import (
    OnlineScanUseCase,
    _check_online_uses_resource_name,
    _is_system_or_tool_violation,
)


@pytest.fixture
def telemetry():
    return MagicMock()


def test_online_scan_execute_collects_violations(telemetry):
    """execute() runs check_online for each rule and collects violations."""
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value = None
    mock_cursor.fetchall.return_value = []  # SHOW VIEWS returns empty

    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    mock_rule = MagicMock()
    mock_rule.check_online.return_value = [
        Violation("SEC_001", "Account", "Too many admins", Severity.MEDIUM),
    ]

    use_case = OnlineScanUseCase(mock_gateway, [mock_rule], telemetry)
    violations = use_case.execute()
    assert len(violations) == 1
    assert violations[0].rule_id == "SEC_001"
    mock_rule.check_online.assert_called()


def test_online_scan_execute_filters_system_violations(telemetry):
    """execute() filters out violations for SNOWFLAKE resources."""
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value = None
    mock_cursor.fetchall.return_value = [("created_on", "V1", "r", "VIEW", "USER_DB", "SCHEMA1")]
    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor
    mock_rule = MagicMock()
    mock_rule.check_online.return_value = [
        Violation("SEC_001", "SNOWFLAKE.ACCOUNT_USAGE.TABLES", "System", Severity.LOW),
        Violation("COST_001", "USER_DB.SCHEMA.WH", "User", Severity.MEDIUM),
    ]
    use_case = OnlineScanUseCase(mock_gateway, [mock_rule], telemetry)
    violations = use_case.execute()
    assert len(violations) == 1, violations
    assert violations[0].resource_name == "USER_DB.SCHEMA.WH"


def test_is_system_or_tool_violation():
    """_is_system_or_tool_violation marks SNOWFLAKE/SNOWFORT/SYSTEM$ as system."""
    v_snowflake = Violation("X", "SNOWFLAKE.ACCOUNT_USAGE.TABLES", "msg", Severity.LOW)
    v_snowfort = Violation("X", "SNOWFORT.SCHEMA.T", "msg", Severity.LOW)
    v_system = Violation("X", "SYSTEM$FOO", "msg", Severity.LOW)
    v_user = Violation("X", "USER_DB.SCHEMA.T", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v_snowflake, False) is True
    assert _is_system_or_tool_violation(v_snowfort, False) is True
    assert _is_system_or_tool_violation(v_snowfort, True) is False
    assert _is_system_or_tool_violation(v_system, False) is True
    assert _is_system_or_tool_violation(v_user, False) is False


def test_online_scan_execute_cursor_raises(telemetry):
    """execute() calls telemetry.error and re-raises when get_cursor fails."""
    mock_gateway = MagicMock()
    mock_gateway.get_cursor.side_effect = RuntimeError("Connection failed")

    use_case = OnlineScanUseCase(mock_gateway, [], telemetry)
    with pytest.raises(RuntimeError, match="Connection failed"):
        use_case.execute()
    telemetry.error.assert_called_once()


def test_online_scan_execute_show_views_raises(telemetry):
    """execute() handles view-fetch failure and still returns rule-level violations."""

    def execute_side_effect(arg):
        if "ACCOUNT_USAGE.VIEWS" in arg or "SHOW VIEWS" in arg:
            raise RuntimeError("Permission denied")

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = execute_side_effect

    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    # Need a view-scoped rule so the view phase actually runs and hits the failing queries
    validator = MagicMock()
    validator.validate.return_value = []
    rule = SelectStarCheck(validator=validator, telemetry=telemetry)

    use_case = OnlineScanUseCase(mock_gateway, [rule], telemetry)
    violations = use_case.execute()
    telemetry.error.assert_called()
    assert isinstance(violations, list)


def test_check_online_uses_resource_name_select_star_true(telemetry):
    """SelectStarCheck uses _resource_name in check_online body -> run per view."""
    validator = MagicMock()
    validator.validate.return_value = []
    rule = SelectStarCheck(validator=validator, telemetry=telemetry)
    assert _check_online_uses_resource_name(rule) is True


def test_check_online_uses_resource_name_account_budget_false(telemetry):
    """AccountBudgetEnforcement does not use _resource_name in check_online -> account-only."""
    rule = AccountBudgetEnforcement(telemetry=telemetry)
    assert _check_online_uses_resource_name(rule) is False


def test_online_scan_execute_view_phase_batch_ddl(telemetry):
    """execute() uses ACCOUNT_USAGE.VIEWS batch DDL and calls check_static per view."""
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value = None
    # ACCOUNT_USAGE.VIEWS format: (TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, VIEW_DEFINITION)
    mock_cursor.fetchall.return_value = [
        ("DB1", "SCHEMA1", "V1", "SELECT col FROM t1"),
        ("DB2", "SCHEMA2", "V2", "SELECT col FROM t2"),
    ]
    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    validator = MagicMock()
    validator.validate.return_value = []
    rule = SelectStarCheck(validator=validator, telemetry=telemetry)
    rule.check_static = MagicMock(return_value=[])

    use_case = OnlineScanUseCase(mock_gateway, [rule], telemetry)
    use_case.execute()

    # check_static called once per view in batch path
    assert rule.check_static.call_count == 2
    rule.check_static.assert_any_call("SELECT col FROM t1", "DB1.SCHEMA1.V1")
    rule.check_static.assert_any_call("SELECT col FROM t2", "DB2.SCHEMA2.V2")


def test_online_scan_execute_view_fallback_uses_check_online(telemetry):
    """When ACCOUNT_USAGE.VIEWS fails, falls back to SHOW VIEWS + check_online per view."""
    call_num = [0]

    def execute_side_effect(arg):
        call_num[0] += 1
        if "ACCOUNT_USAGE.VIEWS" in arg:
            raise RuntimeError("Insufficient privileges")

    # SHOW VIEWS columns: created_on(0), name(1), reserved(2), kind(3), database_name(4), schema_name(5)
    show_views_rows = [
        ("created_on", "V1", "r", "VIEW", "DB1", "SCHEMA1"),
        ("created_on", "V2", "r", "VIEW", "DB2", "SCHEMA2"),
    ]
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = execute_side_effect
    mock_cursor.fetchall.return_value = show_views_rows
    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = mock_cursor

    validator = MagicMock()
    validator.validate.return_value = []
    rule = SelectStarCheck(validator=validator, telemetry=telemetry)
    rule.check_online = MagicMock(return_value=[])

    use_case = OnlineScanUseCase(mock_gateway, [rule], telemetry)
    use_case.execute()

    # 1 call in account phase (with scan_context) + 2 calls in view phase (one per view, no scan_context)
    assert rule.check_online.call_count == 3
    rule.check_online.assert_any_call(mock_cursor, scan_context=ANY)
    rule.check_online.assert_any_call(mock_cursor, "DB1.SCHEMA1.V1")
    rule.check_online.assert_any_call(mock_cursor, "DB2.SCHEMA2.V2")


def test_online_scan_execute_parallel_uses_worker_cursors(telemetry):
    """execute(workers=2) uses get_cursor_for_worker when gateway supports it."""
    cursor0 = MagicMock()
    cursor0.execute.return_value = None
    cursor0.fetchall.return_value = []
    cursor1 = MagicMock()
    cursor1.execute.return_value = None
    cursor1.fetchall.return_value = []

    mock_gateway = MagicMock()
    mock_gateway.get_cursor.return_value = cursor0
    mock_gateway.get_cursor_for_worker.side_effect = [cursor0, cursor1]

    mock_rule1 = MagicMock()
    mock_rule1.id = "R1"
    mock_rule1.name = "Rule1"
    mock_rule1.check_online.return_value = []
    mock_rule2 = MagicMock()
    mock_rule2.id = "R2"
    mock_rule2.name = "Rule2"
    mock_rule2.check_online.return_value = []

    use_case = OnlineScanUseCase(mock_gateway, [mock_rule1, mock_rule2], telemetry)
    violations = use_case.execute(workers=2)

    assert mock_gateway.get_cursor_for_worker.called
    assert isinstance(violations, list)
