"""Tests for use_cases/online_scan.py."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation
from snowfort_audit.use_cases.online_scan import (
    OnlineScanUseCase,
    _check_online_uses_resource_name,
    _derive_sso_and_zombies,
    _is_system_or_tool_violation,
)


def test_is_system_snowflake():
    v = Violation("X", "SNOWFLAKE.ACCOUNT_USAGE.T", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=False) is True


def test_is_system_snowfort_excluded():
    v = Violation("X", "SNOWFORT.SCH.T", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=False) is True


def test_is_system_snowfort_included():
    v = Violation("X", "SNOWFORT.SCH.T", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=True) is False


def test_is_system_user_db():
    v = Violation("X", "MY_DB.SCHEMA.T", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=False) is False


def test_is_system_system_dollar():
    v = Violation("X", "SYSTEM$FOO", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=False) is True


def test_is_system_empty_resource():
    v = Violation("X", "", "msg", Severity.LOW)
    assert _is_system_or_tool_violation(v, include_snowfort_db=False) is False


def test_check_online_uses_resource_name_base_rule():
    r = Rule("X", "X", Severity.LOW)
    assert _check_online_uses_resource_name(r) is False


class _ViewRule(Rule):
    def check_online(self, cursor, _resource_name=None):
        if _resource_name:
            return [Violation(self.id, _resource_name, "v", Severity.LOW)]
        return []


def test_check_online_uses_resource_name_true():
    r = _ViewRule("V1", "ViewRule", Severity.LOW)
    assert _check_online_uses_resource_name(r) is True


# ── AC-2: _derive_sso_and_zombies accepts configurable threshold ──────────────

_USER_COLS = {
    "name": 0,
    "type": 1,
    "ext_authn_uid": 2,
    "last_success_login": 3,
    "created_on": 4,
    "has_password": 5,
    "has_rsa_public_key": 6,
}


def _user(name: str, utype: str = "", sso_uid: str = "") -> tuple:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return (name, utype, sso_uid, now, now, True, False)


def test_derive_sso_default_threshold_half_sso():
    """5 of 10 humans have SSO → exactly at default 0.5 threshold → enforced."""
    users = tuple(_user(f"U{i}", "", "uid" if i < 5 else "") for i in range(10))
    sso, _ = _derive_sso_and_zombies(users, _USER_COLS)
    assert sso is True


def test_derive_sso_custom_threshold_above():
    """5 of 10 humans have SSO, threshold 0.8 → NOT enforced."""
    users = tuple(_user(f"U{i}", "", "uid" if i < 5 else "") for i in range(10))
    sso, _ = _derive_sso_and_zombies(users, _USER_COLS, sso_threshold=0.8)
    assert sso is False


def test_derive_sso_custom_threshold_met():
    """8 of 10 humans have SSO, threshold 0.8 → enforced."""
    users = tuple(_user(f"U{i}", "", "uid" if i < 8 else "") for i in range(10))
    sso, _ = _derive_sso_and_zombies(users, _USER_COLS, sso_threshold=0.8)
    assert sso is True


def test_online_scan_sequential_no_views():
    gw = MagicMock()
    cursor = MagicMock()
    gw.get_cursor.return_value = cursor

    call_count = [0]

    def fetchall_side_effect():
        call_count[0] += 1
        if call_count[0] == 1:
            return []
        return []

    cursor.fetchall.side_effect = fetchall_side_effect

    mock_rule = MagicMock(spec=Rule)
    mock_rule.id = "R1"
    mock_rule.name = "TestRule"
    mock_rule.check_online.return_value = [Violation("R1", "MY_DB.T", "bad", Severity.HIGH)]

    tel = MagicMock()
    uc = OnlineScanUseCase(gw, [mock_rule], tel)
    violations = uc.execute(workers=1)
    assert len(violations) == 1
    assert violations[0].resource_name == "MY_DB.T"


def test_online_scan_connection_failure():
    gw = MagicMock()
    gw.get_cursor.side_effect = RuntimeError("no conn")
    tel = MagicMock()
    uc = OnlineScanUseCase(gw, [], tel)
    with pytest.raises(RuntimeError):
        uc.execute()


def test_online_scan_filters_system():
    gw = MagicMock()
    cursor = MagicMock()
    gw.get_cursor.return_value = cursor

    # SHOW VIEWS returns one dummy view row so code doesn't early-return before filter
    view_row = ("created", "MY_VIEW", None, None, "MY_DB", "PUBLIC")
    call_count = [0]

    def fetchall_side_effect():
        call_count[0] += 1
        if call_count[0] == 1:
            return [view_row]
        return []

    cursor.fetchall.side_effect = fetchall_side_effect

    mock_rule = MagicMock(spec=Rule)
    mock_rule.id = "R1"
    mock_rule.name = "TestRule"
    mock_rule.check_online.return_value = [
        Violation("R1", "SNOWFLAKE.AU.T", "sys", Severity.LOW),
        Violation("R1", "MY_DB.T", "user", Severity.HIGH),
    ]

    tel = MagicMock()
    uc = OnlineScanUseCase(gw, [mock_rule], tel)
    violations = uc.execute(workers=1)
    assert len(violations) == 1
    assert violations[0].resource_name == "MY_DB.T"
