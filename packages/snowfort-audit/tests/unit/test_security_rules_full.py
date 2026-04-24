"""Tests for security rules."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules._grants import admin_role_user_counts
from snowfort_audit.domain.rules.security import (
    AdminExposureCheck,
    CISBenchmarkScannerCheck,
    DataExfiltrationPreventionCheck,
    DataMaskingPolicyCoverageCheck,
    FederatedAuthenticationCheck,
    MFAAccountEnforcementCheck,
    MFAEnforcementCheck,
    NetworkPerimeterCheck,
    PasswordPolicyCheck,
    PrivateConnectivityCheck,
    PublicGrantsCheck,
    RowAccessPolicyCoverageCheck,
    ServiceUserSecurityCheck,
    SSOCoverageCheck,
    UserOwnershipCheck,
    ZombieRoleCheck,
    ZombieUserCheck,
)
from snowfort_audit.domain.rules.security_advanced import (
    ReadOnlyRoleIntegrityCheck,
    ReadOnlyUserIntegrityCheck,
    ServiceRoleScopeCheck,
    ServiceUserScopeCheck,
)


def test_admin_too_many():
    assert len(AdminExposureCheck()._check_account_admin(5)) == 1


def test_admin_too_few():
    assert len(AdminExposureCheck()._check_account_admin(1)) == 1


def test_admin_ok():
    assert AdminExposureCheck()._check_account_admin(2) == []


def test_admin_generic():
    assert len(AdminExposureCheck()._check_generic_admin("SEC", 6)) == 1
    assert AdminExposureCheck()._check_generic_admin("SYS", 3) == []


def test_mfa_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        MFAEnforcementCheck().check_online(c)


def test_network_no_policy():
    c = MagicMock()
    c.fetchone.return_value = ("NP", "")
    assert len(NetworkPerimeterCheck()._check_account(c)) == 1


def test_network_open_ip():
    c = MagicMock()
    c.fetchone.side_effect = [("NP", "pol"), None]
    c.fetchall.return_value = [("ALLOWED_IP_LIST", "0.0.0.0/0")]
    assert len(NetworkPerimeterCheck()._check_account(c)) == 1


def test_network_exc():
    # AC-1: non-allowlisted errors raise RuleExecutionError (no silent swallow).
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        NetworkPerimeterCheck()._check_account(c)


def test_network_perimeter_sso_downgrade():
    """B3: severity is LOW when sso_enforced=True, CRITICAL when sso_enforced=False/None."""
    from snowfort_audit.domain.rule_definitions import Severity
    from snowfort_audit.domain.scan_context import ScanContext

    ctx_sso = ScanContext()
    object.__setattr__(ctx_sso, "sso_enforced", True)

    ctx_no_sso = ScanContext()
    object.__setattr__(ctx_no_sso, "sso_enforced", False)

    def make_cursor():
        c = MagicMock()
        c.fetchone.return_value = ("NP", "")  # no network policy set
        return c

    v_sso = NetworkPerimeterCheck().check_online(make_cursor(), scan_context=ctx_sso)
    v_no_sso = NetworkPerimeterCheck().check_online(make_cursor(), scan_context=ctx_no_sso)

    assert len(v_sso) == 1
    assert v_sso[0].severity == Severity.LOW, f"Expected LOW, got {v_sso[0].severity}"

    assert len(v_no_sso) == 1
    assert v_no_sso[0].severity == Severity.CRITICAL, f"Expected CRITICAL, got {v_no_sso[0].severity}"


def test_public_grants():
    c = MagicMock()
    c.fetchall.return_value = [("cr", "SELECT", "TABLE", "MY.PUB.T")]
    assert len(PublicGrantsCheck().check_online(c)) == 1


def test_public_grants_system():
    c = MagicMock()
    c.fetchall.return_value = [("cr", "SELECT", "TABLE", "SNOWFLAKE.AU.T")]
    assert PublicGrantsCheck().check_online(c) == []


def test_user_ownership():
    c = MagicMock()
    c.description = [("name",), ("owner",)]
    c.fetchall.side_effect = [[("DB", "JOHN")], [], []]
    assert len(UserOwnershipCheck().check_online(c)) == 1


def test_user_ownership_role():
    c = MagicMock()
    c.description = [("name",), ("owner",)]
    c.fetchall.side_effect = [[("DB", "SYSADMIN")], [], []]
    assert UserOwnershipCheck().check_online(c) == []


def test_svc_pwd():
    c = MagicMock()
    c.description = [("name",), ("type",), ("has_password",), ("has_rsa_public_key",)]
    c.fetchall.return_value = [("SVC", "SERVICE", "true", "true")]
    assert len(ServiceUserSecurityCheck().check_online(c)) == 1


def test_svc_no_key():
    c = MagicMock()
    c.description = [("name",), ("type",), ("has_password",), ("has_rsa_public_key",)]
    c.fetchall.return_value = [("SVC", "SERVICE", "false", "false")]
    assert len(ServiceUserSecurityCheck().check_online(c)) == 1


def test_svc_no_type():
    c = MagicMock()
    c.description = [("name",), ("has_password",)]
    assert ServiceUserSecurityCheck().check_online(c) == []


def test_zombie_user():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [
        ("U", datetime.now(timezone.utc) - timedelta(days=120), datetime.now(timezone.utc) - timedelta(days=200))
    ]
    assert len(ZombieUserCheck().check_online(c)) == 1


def test_zombie_user_never():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [("U", None, datetime.now(timezone.utc) - timedelta(days=60))]
    assert len(ZombieUserCheck().check_online(c)) == 1


def test_zombie_user_sso_downgrade():
    """B5: severity is LOW when sso_enforced=True."""
    from snowfort_audit.domain.rule_definitions import Severity
    from snowfort_audit.domain.scan_context import ScanContext

    ctx = ScanContext()
    object.__setattr__(ctx, "sso_enforced", True)

    users = (
        (
            "INACTIVE_U",
            datetime.now(timezone.utc) - timedelta(days=120),
            datetime.now(timezone.utc) - timedelta(days=200),
        ),
    )
    object.__setattr__(ctx, "users", users)
    object.__setattr__(ctx, "users_cols", {"name": 0, "last_success_login": 1, "created_on": 2})

    c = MagicMock()
    violations = ZombieUserCheck().check_online(c, scan_context=ctx)
    assert len(violations) == 1
    assert violations[0].severity == Severity.LOW


def test_zombie_user_ok():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [("U", None, datetime.now(timezone.utc) - timedelta(days=5))]
    assert ZombieUserCheck().check_online(c) == []


# ── AC-2: SEC_007 auth-type bucketing when sso_enforced=True ──────────────────


def _zombie_scan_context(user_row, admin_users=frozenset()):
    """Build a ScanContext with sso_enforced=True and a single user row."""
    from snowfort_audit.domain.scan_context import ScanContext

    ctx = ScanContext()
    object.__setattr__(ctx, "sso_enforced", True)
    object.__setattr__(ctx, "users", (user_row,))
    object.__setattr__(
        ctx,
        "users_cols",
        {
            "name": 0,
            "last_success_login": 1,
            "created_on": 2,
            "has_password": 3,
            "has_rsa_public_key": 4,
            "ext_authn_uid": 5,
            "type": 6,
        },
    )
    object.__setattr__(ctx, "_admin_users_precomputed", frozenset(admin_users))
    return ctx


def test_zombie_password_admin_sso_critical(monkeypatch):
    """AC-2: zombie with password + admin role → CRITICAL + ACTIONABLE when SSO enforced."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity

    monkeypatch.setattr(ZombieUserCheck, "_admin_users", lambda self, cur, sc: {"ADM"})
    user = (
        "ADM",
        datetime.now(timezone.utc) - timedelta(days=120),
        datetime.now(timezone.utc) - timedelta(days=200),
        "true",  # has_password
        "false",  # has_rsa_public_key
        "",  # ext_authn_uid
        "PERSON",
    )
    ctx = _zombie_scan_context(user, admin_users={"ADM"})
    v = ZombieUserCheck().check_online(MagicMock(), scan_context=ctx)
    assert len(v) == 1
    assert v[0].severity == Severity.CRITICAL
    assert v[0].category == FindingCategory.ACTIONABLE


def test_zombie_password_nonadmin_sso_high(monkeypatch):
    """AC-2: zombie with password but no admin role → HIGH + ACTIONABLE when SSO enforced."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity

    monkeypatch.setattr(ZombieUserCheck, "_admin_users", lambda self, cur, sc: set())
    user = (
        "DEV",
        datetime.now(timezone.utc) - timedelta(days=120),
        datetime.now(timezone.utc) - timedelta(days=200),
        "true",
        "false",
        "",
        "PERSON",
    )
    ctx = _zombie_scan_context(user)
    v = ZombieUserCheck().check_online(MagicMock(), scan_context=ctx)
    assert len(v) == 1
    assert v[0].severity == Severity.HIGH
    assert v[0].category == FindingCategory.ACTIONABLE


def test_zombie_sso_only_informational(monkeypatch):
    """AC-2: zombie with SSO only (no password, no key) → LOW + INFORMATIONAL when SSO enforced."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity

    monkeypatch.setattr(ZombieUserCheck, "_admin_users", lambda self, cur, sc: set())
    user = (
        "HUMAN",
        datetime.now(timezone.utc) - timedelta(days=120),
        datetime.now(timezone.utc) - timedelta(days=200),
        "false",
        "false",
        "sso-uid-123",
        "PERSON",
    )
    ctx = _zombie_scan_context(user)
    v = ZombieUserCheck().check_online(MagicMock(), scan_context=ctx)
    assert len(v) == 1
    assert v[0].severity == Severity.LOW
    assert v[0].category == FindingCategory.INFORMATIONAL


def test_zombie_keypair_only_informational(monkeypatch):
    """AC-2: zombie with key-pair only → LOW + INFORMATIONAL when SSO enforced."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity

    monkeypatch.setattr(ZombieUserCheck, "_admin_users", lambda self, cur, sc: set())
    user = (
        "SVC",
        datetime.now(timezone.utc) - timedelta(days=120),
        datetime.now(timezone.utc) - timedelta(days=200),
        "false",
        "true",
        "",
        "SERVICE",
    )
    ctx = _zombie_scan_context(user)
    v = ZombieUserCheck().check_online(MagicMock(), scan_context=ctx)
    assert len(v) == 1
    assert v[0].severity == Severity.LOW
    assert v[0].category == FindingCategory.INFORMATIONAL


def test_zombie_role():
    c = MagicMock()
    # SHOW ROLES -> CUSTOM; GRANTS_TO_ROLES(granted_on='ROLE') -> []; GRANTS_TO_USERS -> [];
    # GRANTS_TO_ROLES(grantee) -> [] => CUSTOM is Orphan + Empty = 2 violations
    c.fetchall.side_effect = [[("cr", "CUSTOM")], [], [], []]
    assert len(ZombieRoleCheck().check_online(c)) == 2


def test_zombie_role_sql_parses():
    """AC-2: SEC_008 SQL queries must parse cleanly in Snowflake dialect (regression)."""
    import sqlfluff

    sec_008_queries = [
        (
            "SELECT DISTINCT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES "
            "WHERE GRANTED_ON = 'ROLE' AND DELETED_ON IS NULL"
        ),
        "SELECT DISTINCT ROLE FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS WHERE DELETED_ON IS NULL",
        "SELECT DISTINCT GRANTEE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES WHERE DELETED_ON IS NULL",
    ]
    for sql in sec_008_queries:
        results = sqlfluff.lint(sql, dialect="snowflake")
        parse_errors = [r for r in results if r.get("code", "").startswith("PRS")]
        assert not parse_errors, f"Parse error in SEC_008 SQL:\n{sql}\n{parse_errors}"


def test_zombie_role_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        ZombieRoleCheck().check_online(c)


def test_federated_excludes_zombies_and_service():
    """B6: zombie users and SERVICE users are excluded from FederatedAuthenticationCheck."""
    from snowfort_audit.domain.scan_context import ScanContext

    ctx = ScanContext()
    object.__setattr__(ctx, "zombie_user_logins", frozenset({"zombie_user"}))

    # cols: name=0, has_password=1, has_mfa=2, ext_authn_duo=3, has_rsa_public_key=4, ext_authn_uid=5, type=6
    users = (
        ("ZOMBIE_USER", "true", "false", "false", "false", "", "PERSON"),  # zombie → excluded
        ("SVC_BOT", "true", "false", "false", "false", "", "SERVICE"),  # service → excluded
        ("HUMAN_USER", "true", "false", "false", "false", "", "PERSON"),  # should be flagged
    )
    object.__setattr__(ctx, "users", users)
    object.__setattr__(
        ctx,
        "users_cols",
        {
            "name": 0,
            "has_password": 1,
            "has_mfa": 2,
            "ext_authn_duo": 3,
            "has_rsa_public_key": 4,
            "ext_authn_uid": 5,
            "type": 6,
        },
    )

    c = MagicMock()
    violations = FederatedAuthenticationCheck().check_online(c, scan_context=ctx)
    assert len(violations) == 1
    assert "HUMAN_USER" in violations[0].message


def test_federated_pwd():
    c = MagicMock()
    c.description = [
        ("name",),
        ("has_password",),
        ("has_mfa",),
        ("ext_authn_duo",),
        ("has_rsa_public_key",),
        ("ext_authn_uid",),
        ("type",),
    ]
    c.fetchall.return_value = [("U", "true", "false", "false", "false", "", "PERSON")]
    assert len(FederatedAuthenticationCheck().check_online(c)) == 1


def test_federated_svc():
    c = MagicMock()
    c.description = [
        ("name",),
        ("has_password",),
        ("has_mfa",),
        ("ext_authn_duo",),
        ("has_rsa_public_key",),
        ("ext_authn_uid",),
        ("type",),
    ]
    c.fetchall.return_value = [("SVC", "true", "false", "false", "false", "", "SERVICE")]
    assert FederatedAuthenticationCheck().check_online(c) == []


def test_mfa_acct_none():
    c = MagicMock()
    c.fetchone.return_value = None
    assert len(MFAAccountEnforcementCheck().check_online(c)) == 1


def test_mfa_acct_false():
    c = MagicMock()
    c.fetchone.return_value = ("k", "FALSE")
    assert len(MFAAccountEnforcementCheck().check_online(c)) == 1


def test_mfa_acct_true():
    c = MagicMock()
    c.fetchone.return_value = ("k", "TRUE")
    assert MFAAccountEnforcementCheck().check_online(c) == []


def test_mfa_acct_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    with pytest.raises(RuleExecutionError):
        MFAAccountEnforcementCheck().check_online(c)


# ── AC-2: SEC_002 / SEC_011 / SEC_016 SSO-aware severity downgrade ────────────


def _user_row(name="U", has_mfa="false", has_pwd="true", ext_uid="", utype="PERSON"):
    return (name, has_pwd, has_mfa, "false", "false", ext_uid, utype)


def _user_desc_for_federated():
    return [
        ("name",),
        ("has_password",),
        ("has_mfa",),
        ("ext_authn_duo",),
        ("has_rsa_public_key",),
        ("ext_authn_uid",),
        ("type",),
    ]


def test_federated_sso_downgrade():
    """AC-2: SEC_011 severity is LOW + EXPECTED when sso_enforced=True, MEDIUM otherwise."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity
    from snowfort_audit.domain.scan_context import ScanContext

    def make_cursor():
        c = MagicMock()
        c.description = _user_desc_for_federated()
        c.fetchall.return_value = [_user_row()]
        return c

    ctx_sso = ScanContext()
    object.__setattr__(ctx_sso, "sso_enforced", True)
    ctx_no_sso = ScanContext()
    object.__setattr__(ctx_no_sso, "sso_enforced", False)

    v_sso = FederatedAuthenticationCheck().check_online(make_cursor(), scan_context=ctx_sso)
    v_no_sso = FederatedAuthenticationCheck().check_online(make_cursor(), scan_context=ctx_no_sso)

    assert len(v_sso) == 1
    assert v_sso[0].severity == Severity.LOW
    assert v_sso[0].category == FindingCategory.EXPECTED
    assert len(v_no_sso) == 1
    assert v_no_sso[0].severity == Severity.MEDIUM


def test_mfa_acct_sso_downgrade():
    """AC-2: SEC_016 severity is LOW + EXPECTED when sso_enforced=True, CRITICAL otherwise."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity
    from snowfort_audit.domain.scan_context import ScanContext

    def make_cursor():
        c = MagicMock()
        c.fetchone.return_value = ("k", "FALSE")
        return c

    ctx_sso = ScanContext()
    object.__setattr__(ctx_sso, "sso_enforced", True)
    ctx_no_sso = ScanContext()
    object.__setattr__(ctx_no_sso, "sso_enforced", False)

    v_sso = MFAAccountEnforcementCheck().check_online(make_cursor(), scan_context=ctx_sso)
    v_no_sso = MFAAccountEnforcementCheck().check_online(make_cursor(), scan_context=ctx_no_sso)

    assert len(v_sso) == 1
    assert v_sso[0].severity == Severity.LOW
    assert v_sso[0].category == FindingCategory.EXPECTED
    assert len(v_no_sso) == 1
    assert v_no_sso[0].severity == Severity.CRITICAL


def test_mfa_per_user_sso_downgrade(monkeypatch):
    """AC-2: SEC_002 severity is LOW + EXPECTED when sso_enforced=True, CRITICAL otherwise."""
    from snowfort_audit.domain.rule_definitions import FindingCategory, Severity
    from snowfort_audit.domain.scan_context import ScanContext

    # Patch admin detection to isolate SSO-downgrade behavior from RBAC resolution.
    monkeypatch.setattr(MFAEnforcementCheck, "_get_admin_users", lambda self, cur, sc=None: {"ADM"})

    def make_cursor():
        c = MagicMock()
        c.description = [
            ("name",),
            ("type",),
            ("has_mfa",),
            ("ext_authn_duo",),
            ("mins_to_bypass_mfa",),
        ]
        c.fetchall.return_value = [("ADM", "PERSON", "false", "false", None)]
        return c

    ctx_sso = ScanContext()
    object.__setattr__(ctx_sso, "sso_enforced", True)
    ctx_no_sso = ScanContext()
    object.__setattr__(ctx_no_sso, "sso_enforced", False)

    v_sso = MFAEnforcementCheck().check_online(make_cursor(), scan_context=ctx_sso)
    v_no_sso = MFAEnforcementCheck().check_online(make_cursor(), scan_context=ctx_no_sso)

    assert len(v_sso) == 1, f"Expected 1 violation, got {v_sso}"
    assert v_sso[0].severity == Severity.LOW
    assert v_sso[0].category == FindingCategory.EXPECTED
    assert len(v_no_sso) == 1
    assert v_no_sso[0].severity == Severity.CRITICAL


def test_cis_found():
    c = MagicMock()
    c.fetchall.return_value = [("CIS Snowflake Benchmark", "ENABLED")]
    assert CISBenchmarkScannerCheck().check_online(c) == []


def test_cis_not_found():
    c = MagicMock()
    c.fetchall.return_value = [("Other", "X")]
    assert len(CISBenchmarkScannerCheck().check_online(c)) == 1


def test_pwd_policy_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert len(PasswordPolicyCheck().check_online(c)) == 1


def test_pwd_policy_ok():
    c = MagicMock()
    c.fetchall.return_value = [("p",)]
    assert PasswordPolicyCheck().check_online(c) == []


def test_exfil_not_set():
    c = MagicMock()
    c.fetchone.side_effect = [("k", "FALSE"), ("k", "FALSE")]
    assert len(DataExfiltrationPreventionCheck().check_online(c)) == 2


def test_exfil_ok():
    c = MagicMock()
    c.fetchone.side_effect = [("k", "TRUE"), ("k", "TRUE")]
    assert DataExfiltrationPreventionCheck().check_online(c) == []


def test_priv_conn_no():
    c = MagicMock()
    c.fetchone.return_value = ("k", "4")
    c.fetchall.return_value = []
    assert len(PrivateConnectivityCheck().check_online(c)) == 1


def test_priv_conn_ok():
    c = MagicMock()
    c.fetchone.return_value = ("k", "4")
    c.fetchall.return_value = [("p",)]
    assert PrivateConnectivityCheck().check_online(c) == []


def test_masking():
    c = MagicMock()
    c.fetchall.return_value = [("DB.S.T", "EMAIL", "PII")]
    assert len(DataMaskingPolicyCoverageCheck().check_online(c)) == 1


def test_rap():
    c = MagicMock()
    c.fetchall.return_value = [("DB.S.T",)]
    assert len(RowAccessPolicyCoverageCheck().check_online(c)) == 1


def test_sso():
    c = MagicMock()
    c.fetchall.return_value = [("S1", "s", "ext"), ("S2", "s", "ext"), ("N", "n", "")]
    assert len(SSOCoverageCheck().check_online(c)) == 1


def test_sso_empty():
    c = MagicMock()
    c.fetchall.return_value = []
    assert SSOCoverageCheck().check_online(c) == []


def test_adv_svc_role():
    c = MagicMock()
    c.fetchall.return_value = [("SVC_M", 3)]
    assert len(ServiceRoleScopeCheck().check_online(c)) == 1


def test_adv_svc_user():
    c = MagicMock()
    c.fetchall.return_value = [("SVC_M", 2)]
    assert len(ServiceUserScopeCheck().check_online(c)) == 1


def test_adv_ro_role():
    c = MagicMock()
    c.fetchall.return_value = [("A_RO", "INSERT", "TABLE", "T")]
    assert len(ReadOnlyRoleIntegrityCheck().check_online(c)) == 1


def test_adv_ro_user():
    c = MagicMock()
    c.fetchall.return_value = [("R_READER", "DELETE", "TABLE", "T")]
    assert len(ReadOnlyUserIntegrityCheck().check_online(c)) == 1


# ── A1: grant-graph reachability regression tests ────────────────────────────
# GTR row layout: (GRANTEE_NAME, NAME, GRANTED_ON, PRIVILEGE, TABLE_CATALOG, GRANTED_TO)
# GTU row layout: (GRANTEE_NAME, ROLE)


def _make_gtr_role_grant(parent_role: str, child_role: str) -> tuple:
    """GRANTED_ON='ROLE' row: child_role is granted to parent_role."""
    return (parent_role, child_role, "ROLE", "USAGE", "", "ROLE")


def _make_gtu_row(user: str, role: str) -> tuple:
    return (user, role)


def test_admin_role_user_counts_direct_grant():
    """User with a direct ACCOUNTADMIN assignment is counted."""
    gtu = (_make_gtu_row("USER_A", "ACCOUNTADMIN"),)
    result = admin_role_user_counts((), gtu)
    assert "USER_A" in result["ACCOUNTADMIN"]


def test_admin_role_user_counts_three_level_chain():
    """A1 regression: user reachable via 3-level role chain is detected.

    Chain: USER_B → ROLE_R1 → ROLE_R2 → ACCOUNTADMIN
    Old SHOW GRANTS OF ROLE only returned 1-hop direct grantees and would miss USER_B.
    """
    gtr = (
        _make_gtr_role_grant("ROLE_R1", "ROLE_R2"),  # R1 contains R2
        _make_gtr_role_grant("ROLE_R2", "ACCOUNTADMIN"),  # R2 contains ACCOUNTADMIN
    )
    gtu = (_make_gtu_row("USER_B", "ROLE_R1"),)
    result = admin_role_user_counts(gtr, gtu)
    assert "USER_B" in result["ACCOUNTADMIN"], "3-level chain not traversed"


def test_admin_role_user_counts_all_three_users():
    """A1 regression: 3 distinct users via 3 different paths are all detected.

    - USER_A: direct ACCOUNTADMIN grant (GRANTS_TO_USERS)
    - USER_B: role chain R1 → R2 → ACCOUNTADMIN
    - USER_C: single-hop role R3 → ACCOUNTADMIN
    Expected: all 3 found, not 1.
    """
    gtr = (
        _make_gtr_role_grant("ROLE_R1", "ROLE_R2"),
        _make_gtr_role_grant("ROLE_R2", "ACCOUNTADMIN"),
        _make_gtr_role_grant("ROLE_R3", "ACCOUNTADMIN"),
    )
    gtu = (
        _make_gtu_row("USER_A", "ACCOUNTADMIN"),
        _make_gtu_row("USER_B", "ROLE_R1"),
        _make_gtu_row("USER_C", "ROLE_R3"),
    )
    result = admin_role_user_counts(gtr, gtu)
    assert result["ACCOUNTADMIN"] == {"USER_A", "USER_B", "USER_C"}, f"Expected 3 users, got: {result['ACCOUNTADMIN']}"


def test_admin_exposure_check_online_with_scan_context():
    """AdminExposureCheck via scan_context uses BFS and detects all 3 users."""
    from snowfort_audit.domain.scan_context import ScanContext

    gtr = (
        _make_gtr_role_grant("ROLE_R1", "ROLE_R2"),
        _make_gtr_role_grant("ROLE_R2", "ACCOUNTADMIN"),
        _make_gtr_role_grant("ROLE_R3", "ACCOUNTADMIN"),
    )
    gtu = (
        _make_gtu_row("USER_A", "ACCOUNTADMIN"),
        _make_gtu_row("USER_B", "ROLE_R1"),
        _make_gtu_row("USER_C", "ROLE_R3"),
    )

    ctx = ScanContext()
    ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: gtr)
    ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: gtu)

    c = MagicMock()
    # cursor should NOT be called — all data is in cache
    c.execute.side_effect = AssertionError("cursor must not be called when scan_context is set")

    rule = AdminExposureCheck()
    violations = rule.check_online(c, scan_context=ctx)
    # 3 ACCOUNTADMINs → _check_account_admin(3) → [] (OK: within 2-3 range)
    assert violations == [], f"Expected no violations for count=3, got: {violations}"


def test_admin_exposure_check_online_scan_context_too_many():
    """AdminExposureCheck via scan_context flags > MAX_ACCOUNT_ADMINS (4 users)."""
    from snowfort_audit.domain.scan_context import ScanContext

    gtu = (
        _make_gtu_row("U1", "ACCOUNTADMIN"),
        _make_gtu_row("U2", "ACCOUNTADMIN"),
        _make_gtu_row("U3", "ACCOUNTADMIN"),
        _make_gtu_row("U4", "ACCOUNTADMIN"),
    )
    ctx = ScanContext()
    ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
    ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: gtu)

    c = MagicMock()
    c.execute.side_effect = AssertionError("cursor must not be called when scan_context is set")

    violations = AdminExposureCheck().check_online(c, scan_context=ctx)
    assert len(violations) == 1
    assert "4" in violations[0].message


# ---------------------------------------------------------------------------
# AC-1: NetworkPerimeterCheck bare handlers must raise RuleExecutionError
# ---------------------------------------------------------------------------


class TestNetworkPerimeterCheckErrorPropagation:
    """_check_account and _describe_and_check_policy must not silently
    return [] for non-allowlisted errors."""

    def test_check_account_unexpected_error_raises(self):
        """Non-SF error in _check_account must raise RuleExecutionError."""
        rule = NetworkPerimeterCheck()
        c = MagicMock()
        c.execute.side_effect = RuntimeError("unexpected DB failure")
        with pytest.raises(RuleExecutionError):
            rule._check_account(c)

    def test_check_account_allowlisted_error_returns_empty(self):
        """Allowlisted SF error (errno 2003) in _check_account → []."""
        rule = NetworkPerimeterCheck()
        c = MagicMock()
        err = Exception("Object not found")
        err.errno = 2003
        c.execute.side_effect = err
        assert rule._check_account(c) == []

    def test_describe_policy_unexpected_error_raises(self):
        """Non-SF error in _describe_and_check_policy must raise RuleExecutionError."""
        rule = NetworkPerimeterCheck()
        c = MagicMock()
        c.execute.side_effect = RuntimeError("policy describe failed")
        with pytest.raises(RuleExecutionError):
            rule._describe_and_check_policy(c, "Account", "MY_POLICY")

    def test_describe_policy_allowlisted_error_returns_empty(self):
        """Allowlisted SF error in _describe_and_check_policy → []."""
        rule = NetworkPerimeterCheck()
        c = MagicMock()
        err = Exception("Object not found")
        err.errno = 2003
        c.execute.side_effect = err
        assert rule._describe_and_check_policy(c, "Account", "MY_POLICY") == []
