"""SEC_008 regression test: ZombieRoleCheck must use ACCOUNT_USAGE batch queries,
not per-role SHOW GRANTS (which broke on unquoted role names like OPERATIONS in v0.1.0).
"""

import inspect
from unittest.mock import MagicMock

from snowfort_audit.domain.rules.security import ZombieRoleCheck
from snowfort_audit.domain.scan_context import ScanContext


def test_zombie_role_no_show_grants_of_role():
    """Regression: v0.1.0 used 'SHOW GRANTS OF ROLE {role}' without quoting,
    which caused SQL compilation errors for roles named after reserved words
    (e.g. OPERATIONS). The v0.2.0 refactor replaced this with batch
    ACCOUNT_USAGE queries. Verify no SHOW GRANTS OF ROLE pattern exists."""
    source = inspect.getsource(ZombieRoleCheck.check_online)
    assert "SHOW GRANTS OF ROLE" not in source, (
        "ZombieRoleCheck.check_online must not use 'SHOW GRANTS OF ROLE' — "
        "use ACCOUNT_USAGE batch queries instead (v0.1.0 regression)"
    )
    assert "SHOW GRANTS TO ROLE" not in source, (
        "ZombieRoleCheck.check_online must not use 'SHOW GRANTS TO ROLE' — "
        "use ACCOUNT_USAGE batch queries instead (v0.1.0 regression)"
    )


def test_zombie_role_uses_account_usage():
    """Verify ZombieRoleCheck queries ACCOUNT_USAGE for batch role analysis."""
    source = inspect.getsource(ZombieRoleCheck.check_online)
    assert "ACCOUNT_USAGE.GRANTS_TO_ROLES" in source
    assert "ACCOUNT_USAGE.GRANTS_TO_USERS" in source


def test_zombie_role_detects_orphan():
    """ZombieRoleCheck flags roles not granted to any user or role."""
    rule = ZombieRoleCheck()
    cursor = MagicMock()

    ctx = ScanContext()
    object.__setattr__(ctx, "roles", (("id", "ORPHAN_ROLE", "owner"),))
    object.__setattr__(ctx, "roles_cols", {"name": 1})

    # GRANTS_TO_ROLES: no role named ORPHAN_ROLE is granted
    cursor.fetchall.side_effect = [
        [],  # granted_to_role (no roles granted as roles)
        [],  # granted_to_user (no roles granted to users)
        [],  # roles_with_grants (no roles have grants)
    ]

    violations = rule.check_online(cursor, scan_context=ctx)
    assert len(violations) >= 1
    assert any("Orphan" in v.message for v in violations)


def test_worker_error_surfaces_via_telemetry():
    """Worker errors from _run_rules_chunk are returned (not swallowed)."""
    from snowfort_audit.use_cases.online_scan import _run_rules_chunk

    mock_gateway = MagicMock()
    mock_cursor = MagicMock()
    mock_gateway.get_cursor_for_worker.return_value = mock_cursor

    # Create a rule that raises
    failing_rule = MagicMock()
    failing_rule.id = "FAIL_001"
    failing_rule.name = "Failing Rule"
    failing_rule.check_online.side_effect = RuntimeError("boom")

    # Create a rule that succeeds
    ok_rule = MagicMock()
    ok_rule.id = "OK_001"
    ok_rule.name = "OK Rule"
    ok_rule.check_online.return_value = []

    rules_chunk = [(0, failing_rule), (1, ok_rule)]
    violations, timings, errors = _run_rules_chunk(mock_gateway, rules_chunk, 0)

    # Failing rule produced an error
    assert len(errors) == 1
    assert errors[0][0] == "FAIL_001"
    assert "boom" in errors[0][1]

    # OK rule still ran
    ok_rule.check_online.assert_called_once()
