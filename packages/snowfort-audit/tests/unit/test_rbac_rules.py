"""Unit tests for Directive C — RBAC Topology & Role Hierarchy rules.

Coverage targets:
  SEC_001a  AdminGrantCountCheck          ≥5 tests
  SEC_001b  DormantAdminAccountsCheck     ≥5 tests
  SEC_001c  AdminAsDefaultRoleCheck       ≥5 tests
  SEC_001d  LegacyIdentityDuplicationCheck ≥5 tests
  SEC_024   OrphanRoleRatioCheck          ≥5 tests
  SEC_025   GodRoleDetectionCheck         ≥5 tests
  SEC_026   PrivilegeConcentrationCheck   ≥5 tests
  SEC_027   RoleFlowValidationCheck       ≥5 tests
  SEC_028   UserRoleExplosionCheck        ≥5 tests
  SEC_029   IncompleteDepartmentRolesCheck ≥5 tests
  _grants   build_role_graph / role_privilege_counts helpers
  conventions  RbacThresholds
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.conventions import RbacThresholds, SnowfortConventions
from snowfort_audit.domain.rule_definitions import FindingCategory, Severity
from snowfort_audit.domain.rules._grants import (
    build_role_graph,
    role_privilege_counts,
)
from snowfort_audit.domain.rules.rbac import (
    AdminAsDefaultRoleCheck,
    AdminGrantCountCheck,
    DormantAdminAccountsCheck,
    GodRoleDetectionCheck,
    IncompleteDepartmentRolesCheck,
    LegacyIdentityDuplicationCheck,
    OrphanRoleRatioCheck,
    PrivilegeConcentrationCheck,
    RoleFlowValidationCheck,
    UserRoleExplosionCheck,
    _gini,
)
from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Tuple-building helpers (match _grants.py column order)
# ---------------------------------------------------------------------------


def _gtr_priv(role: str, name: str, granted_on: str, priv: str, catalog: str = "") -> tuple:
    """Build a non-ROLE privilege grant row: role → privilege on object."""
    return (role, name, granted_on, priv, catalog, "ROLE")


def _gtr_role_grant(parent: str, child: str) -> tuple:
    """Build a ROLE-to-ROLE grant row: parent inherits child."""
    return (parent, child, "ROLE", "USAGE", "", "ROLE")


def _gtu(user: str, role: str) -> tuple:
    return (user, role)


def _ctx(gtr: tuple = (), gtu: tuple = ()) -> ScanContext:
    """Build a ScanContext pre-seeded with grants."""
    ctx = ScanContext()
    ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: gtr)
    ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: gtu)
    return ctx


def _no_cursor() -> MagicMock:
    c = MagicMock()
    c.execute.side_effect = AssertionError("cursor must not be used when scan_context is set")
    return c


def _now_minus(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# ---------------------------------------------------------------------------
# Helpers: build_role_graph and role_privilege_counts
# ---------------------------------------------------------------------------


class TestBuildRoleGraph:
    def test_empty(self):
        assert build_role_graph(()) == {}

    def test_role_edges_only(self):
        rows = (_gtr_role_grant("A", "B"), _gtr_role_grant("A", "C"))
        g = build_role_graph(rows)
        assert sorted(g["A"]) == ["B", "C"]

    def test_non_role_rows_excluded(self):
        rows = (_gtr_priv("MYROLE", "MY_TABLE", "TABLE", "SELECT"),)
        assert build_role_graph(rows) == {}

    def test_mixed_rows(self):
        rows = (
            _gtr_role_grant("PARENT", "CHILD"),
            _gtr_priv("CHILD", "T", "TABLE", "SELECT"),
        )
        g = build_role_graph(rows)
        assert "PARENT" in g
        assert "CHILD" not in g  # CHILD is not a parent


class TestRolePrivilegeCounts:
    def test_empty(self):
        assert role_privilege_counts(()) == {}

    def test_counts_object_grants(self):
        rows = (
            _gtr_priv("ROLE_A", "T1", "TABLE", "SELECT"),
            _gtr_priv("ROLE_A", "T2", "TABLE", "INSERT"),
            _gtr_priv("ROLE_B", "T1", "TABLE", "SELECT"),
        )
        counts = role_privilege_counts(rows)
        assert counts["ROLE_A"] == 2
        assert counts["ROLE_B"] == 1

    def test_excludes_role_to_role(self):
        rows = (
            _gtr_role_grant("PARENT", "CHILD"),
            _gtr_priv("PARENT", "T1", "TABLE", "SELECT"),
        )
        counts = role_privilege_counts(rows)
        assert counts.get("PARENT") == 1  # only the TABLE grant


# ---------------------------------------------------------------------------
# _gini helper
# ---------------------------------------------------------------------------


def test_gini_empty():
    assert _gini([]) == 0.0


def test_gini_equal_distribution():
    assert _gini([1.0, 1.0, 1.0, 1.0]) == pytest.approx(0.0, abs=1e-6)


def test_gini_perfectly_concentrated():
    # One entity holds everything.
    g = _gini([0.0, 0.0, 0.0, 100.0])
    assert g > 0.7


def test_gini_all_zeros():
    assert _gini([0.0, 0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# RbacThresholds
# ---------------------------------------------------------------------------


class TestRbacThresholds:
    def test_defaults(self):
        t = RbacThresholds()
        assert t.max_account_admins == 3
        assert t.god_role_privilege_threshold == 50
        assert t.god_role_database_span == 3
        assert t.privilege_concentration_gini_threshold == 0.80
        assert t.max_direct_roles_per_user == 10
        assert t.orphan_role_percent_threshold == 20

    def test_frozen(self):
        t = RbacThresholds()
        with pytest.raises((AttributeError, TypeError)):
            t.max_account_admins = 99  # type: ignore[misc]

    def test_custom_values(self):
        t = RbacThresholds(max_account_admins=5, god_role_privilege_threshold=100)
        assert t.max_account_admins == 5
        assert t.god_role_privilege_threshold == 100

    def test_accessible_from_conventions(self):
        c = SnowfortConventions()
        assert isinstance(c.thresholds.rbac, RbacThresholds)
        assert c.thresholds.rbac.max_account_admins == 3


# ---------------------------------------------------------------------------
# SEC_001a — AdminGrantCountCheck
# ---------------------------------------------------------------------------


class TestAdminGrantCountCheck:
    def _make(self, **kw):
        c = RbacThresholds(**kw) if kw else RbacThresholds()
        conv = SnowfortConventions()
        conv = conv.__class__(thresholds=conv.thresholds.__class__(**{**conv.thresholds.__dict__, "rbac": c}))
        return AdminGrantCountCheck(conventions=conv)

    def test_no_violations_within_threshold(self):
        """2 ACCOUNTADMINs → no violation."""
        gtu = (_gtu("U1", "ACCOUNTADMIN"), _gtu("U2", "ACCOUNTADMIN"))
        ctx = _ctx(gtu=gtu)
        v = AdminGrantCountCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_too_many_account_admins_flagged(self):
        """4 ACCOUNTADMINs exceeds default threshold of 3."""
        gtu = tuple(_gtu(f"U{i}", "ACCOUNTADMIN") for i in range(4))
        ctx = _ctx(gtu=gtu)
        v = AdminGrantCountCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "4" in v[0].message
        assert v[0].severity == Severity.HIGH

    def test_zero_admins_flagged_medium(self):
        """Zero ACCOUNTADMINs → redundancy warning at MEDIUM."""
        ctx = _ctx(gtu=())
        v = AdminGrantCountCheck().check_online(_no_cursor(), scan_context=ctx)
        assert any(vio.severity == Severity.MEDIUM for vio in v)

    def test_one_admin_flagged_medium(self):
        """1 ACCOUNTADMIN → redundancy warning at MEDIUM."""
        gtu = (_gtu("ONLYADMIN", "ACCOUNTADMIN"),)
        ctx = _ctx(gtu=gtu)
        v = AdminGrantCountCheck().check_online(_no_cursor(), scan_context=ctx)
        assert any(vio.severity == Severity.MEDIUM for vio in v)

    def test_role_chain_traversal(self):
        """User reaching ACCOUNTADMIN via 2-hop chain should be counted (not zero)."""
        gtr = (_gtr_role_grant("ROLE_A", "ACCOUNTADMIN"),)
        gtu = (_gtu("ALICE", "ROLE_A"),)
        ctx = _ctx(gtr=gtr, gtu=gtu)
        v = AdminGrantCountCheck().check_online(_no_cursor(), scan_context=ctx)
        # 1 user found via chain → "too few ACCOUNTADMINs" MEDIUM warning (not HIGH/too-many).
        assert all(vio.severity == Severity.MEDIUM for vio in v)

    def test_no_scan_context_uses_cursor(self):
        """Without scan_context, cursor is called (fallback path)."""
        c = MagicMock()
        c.fetchall.return_value = []
        c.description = []
        v = AdminGrantCountCheck().check_online(c, scan_context=None)
        # With empty results → 0 admins → MEDIUM violation for redundancy.
        assert any(vio.severity == Severity.MEDIUM for vio in v)

    def test_allowlisted_error_returns_empty(self):
        """SF allowlisted errors return []."""
        ctx = MagicMock()
        err = Exception("test")
        err.errno = 2003  # allowlisted: object not found
        ctx.get_or_fetch.side_effect = err
        c = MagicMock()
        v = AdminGrantCountCheck().check_online(c, scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_001b — DormantAdminAccountsCheck
# ---------------------------------------------------------------------------


class TestDormantAdminAccountsCheck:
    def _users_ctx(self, users, gtu=(), gtr=()):
        ctx = _ctx(gtr=gtr, gtu=gtu)
        ctx.users = users
        ctx.users_cols = {"name": 0, "last_success_login": 1, "has_password": 2, "created_on": 3}
        return ctx

    def test_active_admin_no_violation(self):
        gtu = (_gtu("ALICE", "ACCOUNTADMIN"),)
        users = [("ALICE", _now_minus(5), "true", _now_minus(100))]
        ctx = self._users_ctx(users, gtu=gtu)
        v = DormantAdminAccountsCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_inactive_admin_flagged(self):
        gtu = (_gtu("BOB", "ACCOUNTADMIN"),)
        users = [("BOB", _now_minus(120), "false", _now_minus(200))]
        ctx = self._users_ctx(users, gtu=gtu)
        v = DormantAdminAccountsCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "BOB" in v[0].resource_name
        assert "120" in v[0].message

    def test_never_logged_in_admin_flagged(self):
        gtu = (_gtu("NEW_ADMIN", "ACCOUNTADMIN"),)
        users = [("NEW_ADMIN", None, "false", _now_minus(60))]
        ctx = self._users_ctx(users, gtu=gtu)
        v = DormantAdminAccountsCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "never logged in" in v[0].message.lower()

    def test_non_admin_not_flagged(self):
        gtu = (_gtu("NORMAL_USER", "ANALYST_ROLE"),)
        users = [("NORMAL_USER", _now_minus(200), "true", _now_minus(300))]
        ctx = self._users_ctx(users, gtu=gtu)
        v = DormantAdminAccountsCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_sso_enforced_password_admin_critical(self):
        """SSO enforced + admin + has_password → CRITICAL."""
        gtu = (_gtu("ADMIN_X", "ACCOUNTADMIN"),)
        users = [("ADMIN_X", _now_minus(120), "true", _now_minus(200))]
        ctx = self._users_ctx(users, gtu=gtu)
        ctx.sso_enforced = True
        v = DormantAdminAccountsCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v and v[0].severity == Severity.CRITICAL

    def test_no_scan_context_calls_cursor(self):
        c = MagicMock()
        c.execute.return_value = None
        c.fetchall.return_value = []
        c.description = [("name", None), ("last_success_login", None), ("has_password", None), ("created_on", None)]
        v = DormantAdminAccountsCheck().check_online(c, scan_context=None)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_001c — AdminAsDefaultRoleCheck
# ---------------------------------------------------------------------------


class TestAdminAsDefaultRoleCheck:
    def _users_ctx(self, users):
        ctx = ScanContext()
        ctx.users = users
        ctx.users_cols = {"name": 0, "default_role": 1}
        return ctx

    def test_accountadmin_default_flagged(self):
        ctx = self._users_ctx([("ALICE", "ACCOUNTADMIN")])
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "ACCOUNTADMIN" in v[0].message

    def test_securityadmin_default_flagged(self):
        ctx = self._users_ctx([("BOB", "SECURITYADMIN")])
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_functional_role_not_flagged(self):
        ctx = self._users_ctx([("CAROL", "ANALYST_ROLE")])
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_empty_default_role_not_flagged(self):
        ctx = self._users_ctx([("DAVE", None)])
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_multiple_admin_defaults_all_flagged(self):
        ctx = self._users_ctx(
            [
                ("U1", "ACCOUNTADMIN"),
                ("U2", "SYSADMIN"),
                ("U3", "ANALYST_ROLE"),
            ]
        )
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 2

    def test_missing_default_role_col_returns_empty(self):
        """When SHOW USERS doesn't have default_role column, rule returns []."""
        ctx = ScanContext()
        ctx.users = [("ALICE", "ACCOUNTADMIN")]
        ctx.users_cols = {"name": 0}  # no default_role key
        ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: ())
        ctx.get_or_fetch("GRANTS_TO_USERS", 0, lambda v, w: ())
        v = AdminAsDefaultRoleCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_001d — LegacyIdentityDuplicationCheck
# ---------------------------------------------------------------------------


class TestLegacyIdentityDuplicationCheck:
    def _ctx_with_users(self, users, gtu=()):
        ctx = _ctx(gtu=gtu)
        ctx.users = users
        ctx.users_cols = {"name": 0, "login_name": 1}
        return ctx

    def test_duplicate_detected(self):
        """ALICE (bare) + ALICE@CORP.COM (email) both with ACCOUNTADMIN → violation."""
        gtu = (_gtu("ALICE", "ACCOUNTADMIN"), _gtu("ALICE@CORP.COM", "ACCOUNTADMIN"))
        users = [("ALICE", "ALICE"), ("ALICE@CORP.COM", "ALICE@CORP.COM")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "ALICE" in v[0].resource_name

    def test_no_email_counterpart_no_violation(self):
        """Bare-name admin with no email counterpart → no violation."""
        gtu = (_gtu("ADMIN1", "ACCOUNTADMIN"),)
        users = [("ADMIN1", "ADMIN1")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_non_admin_duplicate_not_flagged(self):
        """Duplicate identities for non-admin users → no violation."""
        gtu = (_gtu("ALICE", "ANALYST_ROLE"), _gtu("ALICE@CORP.COM", "ANALYST_ROLE"))
        users = [("ALICE", "ALICE"), ("ALICE@CORP.COM", "ALICE@CORP.COM")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_only_email_admin_no_violation(self):
        """Email-format admin with no bare-name counterpart → no violation."""
        gtu = (_gtu("BOB@CORP.COM", "ACCOUNTADMIN"),)
        users = [("BOB@CORP.COM", "BOB@CORP.COM")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_violation_severity_is_critical(self):
        gtu = (_gtu("CAROL", "ACCOUNTADMIN"), _gtu("CAROL@CORP.COM", "ACCOUNTADMIN"))
        users = [("CAROL", "CAROL"), ("CAROL@CORP.COM", "CAROL@CORP.COM")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v and v[0].severity == Severity.CRITICAL

    def test_case_insensitive_stem_matching(self):
        """Stem comparison should be case-insensitive."""
        gtu = (_gtu("dave", "ACCOUNTADMIN"), _gtu("DAVE@corp.com", "ACCOUNTADMIN"))
        users = [("dave", "dave"), ("DAVE@corp.com", "DAVE@corp.com")]
        ctx = self._ctx_with_users(users, gtu=gtu)
        v = LegacyIdentityDuplicationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1


# ---------------------------------------------------------------------------
# SEC_024 — OrphanRoleRatioCheck
# ---------------------------------------------------------------------------


def _ctx_with_roles(gtr=(), gtu=(), role_names=()) -> ScanContext:
    """Build a ScanContext pre-seeded with grants and a full role catalog."""
    ctx = _ctx(gtr=gtr, gtu=gtu)
    ctx.roles = tuple(("", name) for name in role_names)
    ctx.roles_cols = {"name": 1}
    return ctx


class TestOrphanRoleRatioCheck:
    def test_no_data_returns_empty(self):
        """Empty role catalog → nothing to check."""
        ctx = _ctx_with_roles()
        v = OrphanRoleRatioCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_below_threshold_no_violation(self):
        """1/10 custom roles orphaned (10%) → below 20% threshold."""
        active_roles = [f"ROLE_{i}" for i in range(9)]
        gtr = tuple(_gtr_priv(r, f"T{i}", "TABLE", "SELECT") for i, r in enumerate(active_roles))
        gtu = tuple(_gtu(f"U{i}", r) for i, r in enumerate(active_roles))
        all_roles = active_roles + ["ORPHAN_ROLE"]
        ctx = _ctx_with_roles(gtr=gtr, gtu=gtu, role_names=all_roles)
        v = OrphanRoleRatioCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_above_threshold_flagged(self):
        """8/10 custom roles orphaned (80%) → exceeds 20% threshold."""
        active_roles = ["ROLE_A", "ROLE_B"]
        gtr = (_gtr_priv("ROLE_A", "T1", "TABLE", "SELECT"),)
        gtu = (_gtu("U1", "ROLE_B"),)
        orphan_roles = [f"ORPHAN_{i}" for i in range(8)]
        all_roles = active_roles + orphan_roles
        ctx = _ctx_with_roles(gtr=gtr, gtu=gtu, role_names=all_roles)
        v = OrphanRoleRatioCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "80%" in v[0].message or "8/10" in v[0].message

    def test_informational_category(self):
        """Orphan ratio violations are INFORMATIONAL."""
        gtr = (_gtr_priv("ACTIVE_ROLE", "T1", "TABLE", "SELECT"),)
        orphan_roles = [f"ORPHAN_{i}" for i in range(9)]
        ctx = _ctx_with_roles(gtr=gtr, role_names=["ACTIVE_ROLE"] + orphan_roles)
        v = OrphanRoleRatioCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert v[0].category == FindingCategory.INFORMATIONAL

    def test_system_roles_excluded(self):
        """ACCOUNTADMIN/SYSADMIN/PUBLIC in the catalog don't count as custom roles."""
        ctx = _ctx_with_roles(role_names=["ACCOUNTADMIN", "SYSADMIN", "PUBLIC"])
        v = OrphanRoleRatioCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_no_cursor_called_with_scan_context(self):
        """When scan_context has roles populated, cursor must not be called."""
        ctx = _ctx_with_roles()
        c = _no_cursor()
        try:
            OrphanRoleRatioCheck().check_online(c, scan_context=ctx)
        except AssertionError:
            pytest.fail("cursor must not be called when scan_context has roles")


# ---------------------------------------------------------------------------
# SEC_025 — GodRoleDetectionCheck
# ---------------------------------------------------------------------------


class TestGodRoleDetectionCheck:
    def test_no_violation_small_role(self):
        """A role with 10 privs on 1 DB → not a god role."""
        gtr = tuple(_gtr_priv("SMALL_ROLE", f"T{i}", "TABLE", "SELECT", "DB1") for i in range(10))
        ctx = _ctx(gtr=gtr)
        v = GodRoleDetectionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_god_role_flagged_by_count_and_span(self):
        """51 privs on 4 DBs exceeds both thresholds → flagged."""
        gtr = tuple(_gtr_priv("GOD_ROLE", f"T{i}", "TABLE", "SELECT", f"DB{i % 5}") for i in range(51))
        ctx = _ctx(gtr=gtr)
        v = GodRoleDetectionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert any("GOD_ROLE" in vio.resource_name for vio in v)

    def test_manage_grants_always_flagged(self):
        """MANAGE GRANTS → CRITICAL regardless of count."""
        gtr = (_gtr_priv("SNEAKY", "ACCOUNT", "ACCOUNT", "MANAGE GRANTS"),)
        ctx = _ctx(gtr=gtr)
        v = GodRoleDetectionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert v[0].severity == Severity.CRITICAL
        assert "MANAGE GRANTS" in v[0].message

    def test_admin_roles_excluded(self):
        """Built-in ACCOUNTADMIN not flagged even with many privs."""
        gtr = tuple(_gtr_priv("ACCOUNTADMIN", f"T{i}", "TABLE", "SELECT", f"DB{i % 5}") for i in range(100))
        ctx = _ctx(gtr=gtr)
        v = GodRoleDetectionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert all("ACCOUNTADMIN" not in vio.resource_name for vio in v)

    def test_custom_thresholds_respected(self):
        """Lower thresholds → same role flagged at lower count."""
        from snowfort_audit.domain.conventions import RuleThresholdConventions

        thresholds = RuleThresholdConventions(
            rbac=RbacThresholds(god_role_privilege_threshold=5, god_role_database_span=2)
        )
        conv = SnowfortConventions(thresholds=thresholds)
        gtr = tuple(_gtr_priv("MEDIUM_ROLE", f"T{i}", "TABLE", "SELECT", f"DB{i % 3}") for i in range(6))
        ctx = _ctx(gtr=gtr)
        v = GodRoleDetectionCheck(conventions=conv).check_online(_no_cursor(), scan_context=ctx)
        assert any("MEDIUM_ROLE" in vio.resource_name for vio in v)

    def test_no_data_returns_empty(self):
        ctx = _ctx()
        v = GodRoleDetectionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_026 — PrivilegeConcentrationCheck
# ---------------------------------------------------------------------------


class TestPrivilegeConcentrationCheck:
    def test_fewer_than_10_roles_skipped(self):
        """< 10 custom roles → skip (too few for meaningful Gini)."""
        gtr = tuple(_gtr_priv(f"ROLE_{i}", f"T{i}", "TABLE", "SELECT") for i in range(5))
        ctx = _ctx(gtr=gtr)
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_equal_distribution_no_violation(self):
        """Even distribution (Gini ≈ 0) → no violation."""
        gtr = tuple(_gtr_priv(f"ROLE_{i}", f"T{i}", "TABLE", "SELECT") for i in range(15))
        ctx = _ctx(gtr=gtr)
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_concentrated_distribution_flagged(self):
        """One role holds almost all privileges (high Gini) → flagged."""
        gtr = (
            # GOD_ROLE has 500 privs
            *(_gtr_priv("GOD_ROLE", f"T{i}", "TABLE", "SELECT", f"DB{i % 10}") for i in range(500)),
            # 14 other roles each have 1 priv
            *(_gtr_priv(f"ROLE_{i}", f"T_other_{i}", "TABLE", "SELECT", "DB0") for i in range(14)),
        )
        ctx = _ctx(gtr=gtr)
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "Gini" in v[0].message

    def test_violation_is_informational(self):
        gtr = (
            *(_gtr_priv("DOMINANT", f"T{i}", "TABLE", "SELECT", "DB1") for i in range(500)),
            *(_gtr_priv(f"R{i}", "T_s", "TABLE", "SELECT", "DB0") for i in range(14)),
        )
        ctx = _ctx(gtr=gtr)
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        for vio in v:
            assert vio.category == FindingCategory.INFORMATIONAL

    def test_admin_roles_excluded_from_gini(self):
        """ACCOUNTADMIN should not inflate the Gini metric."""
        gtr = (
            *(_gtr_priv("ACCOUNTADMIN", f"T{i}", "TABLE", "SELECT", "DB1") for i in range(500)),
            *(_gtr_priv(f"CUSTOM_{i}", f"T_c{i}", "TABLE", "SELECT", "DB0") for i in range(15)),
        )
        ctx = _ctx(gtr=gtr)
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        # With even custom roles, no violation expected.
        assert v == []

    def test_no_data_returns_empty(self):
        ctx = _ctx()
        v = PrivilegeConcentrationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_027 — RoleFlowValidationCheck
# ---------------------------------------------------------------------------


class TestRoleFlowValidationCheck:
    def test_dbo_role_directly_granted_flagged(self):
        """User directly granted a DBO-suffix role → violation."""
        gtu = (_gtu("ALICE", "ORDERS_DBO"),)
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "ALICE" in v[0].resource_name

    def test_ddl_suffix_flagged(self):
        gtu = (_gtu("BOB", "WAREHOUSE_DDL"),)
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_owner_suffix_flagged(self):
        gtu = (_gtu("CAROL", "SALES_OWNER"),)
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_functional_role_not_flagged(self):
        gtu = (_gtu("DAVE", "SALES_READ"),)
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_business_role_not_flagged(self):
        gtu = (_gtu("EVE", "SALES_TEAM"),)
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_custom_pattern_via_conventions(self):
        from snowfort_audit.domain.conventions import RuleThresholdConventions

        thresholds = RuleThresholdConventions(rbac=RbacThresholds(dbo_role_pattern=r"(?i).*_OWNER$"))
        conv = SnowfortConventions(thresholds=thresholds)
        gtu = (_gtu("X", "SOME_OWNER"), _gtu("Y", "SOME_DBO"))
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck(conventions=conv).check_online(_no_cursor(), scan_context=ctx)
        # Only SOME_OWNER matches custom pattern
        assert len(v) == 1
        assert "SOME_OWNER" in v[0].message

    def test_no_dbo_roles_no_violation(self):
        gtu = (_gtu("U1", "ANALYST"), _gtu("U2", "READER"))
        ctx = _ctx(gtu=gtu)
        v = RoleFlowValidationCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_028 — UserRoleExplosionCheck
# ---------------------------------------------------------------------------


class TestUserRoleExplosionCheck:
    def test_within_threshold_no_violation(self):
        gtu = tuple(_gtu("ALICE", f"ROLE_{i}") for i in range(10))
        ctx = _ctx(gtu=gtu)
        v = UserRoleExplosionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_exceeds_threshold_flagged(self):
        """11 direct roles exceeds default threshold of 10."""
        gtu = tuple(_gtu("BOB", f"ROLE_{i}") for i in range(11))
        ctx = _ctx(gtu=gtu)
        v = UserRoleExplosionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "BOB" in v[0].resource_name
        assert "11" in v[0].message

    def test_violation_is_informational(self):
        gtu = tuple(_gtu("CAROL", f"ROLE_{i}") for i in range(15))
        ctx = _ctx(gtu=gtu)
        v = UserRoleExplosionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v and v[0].category == FindingCategory.INFORMATIONAL

    def test_custom_threshold_respected(self):
        from snowfort_audit.domain.conventions import RuleThresholdConventions

        thresholds = RuleThresholdConventions(rbac=RbacThresholds(max_direct_roles_per_user=3))
        conv = SnowfortConventions(thresholds=thresholds)
        gtu = tuple(_gtu("DAVE", f"ROLE_{i}") for i in range(4))
        ctx = _ctx(gtu=gtu)
        v = UserRoleExplosionCheck(conventions=conv).check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_multiple_users_independently_checked(self):
        """Two users: one above threshold, one below."""
        gtu = (
            *(_gtu("U_MANY", f"ROLE_{i}") for i in range(15)),
            *(_gtu("U_FEW", f"OTHER_{i}") for i in range(5)),
        )
        ctx = _ctx(gtu=gtu)
        v = UserRoleExplosionCheck().check_online(_no_cursor(), scan_context=ctx)
        names = [vio.resource_name for vio in v]
        assert "U_MANY" in names
        assert "U_FEW" not in names

    def test_no_data_returns_empty(self):
        ctx = _ctx()
        v = UserRoleExplosionCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []


# ---------------------------------------------------------------------------
# SEC_029 — IncompleteDepartmentRolesCheck
# ---------------------------------------------------------------------------


class TestIncompleteDepartmentRolesCheck:
    def test_functional_role_with_biz_parent_no_violation(self):
        """SALES_READ (functional) → SALES_TEAM (business): correctly wired."""
        gtr = (_gtr_role_grant("SALES_TEAM", "SALES_READ"),)
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_orphaned_functional_role_flagged(self):
        """ANALYTICS_ANALYST has no business-layer parent → flagged."""
        gtr = (_gtr_priv("ANALYTICS_ANALYST", "T1", "TABLE", "SELECT"),)
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        assert any("ANALYTICS_ANALYST" in vio.resource_name for vio in v)

    def test_violation_is_informational(self):
        gtr = (_gtr_priv("ORPHAN_WRITE", "T1", "TABLE", "INSERT"),)
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        for vio in v:
            assert vio.category == FindingCategory.INFORMATIONAL

    def test_no_functional_roles_no_violation(self):
        """No roles match the functional pattern → no violation."""
        gtr = (_gtr_priv("MYROLE", "T1", "TABLE", "SELECT"),)
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_custom_patterns_respected(self):
        """Custom patterns: flag ETL-suffix lacking DEPT-suffix parent."""
        from snowfort_audit.domain.conventions import RuleThresholdConventions

        thresholds = RuleThresholdConventions(
            rbac=RbacThresholds(
                functional_role_pattern=r"(?i).*_ETL$",
                business_role_pattern=r"(?i).*_DEPT$",
            )
        )
        conv = SnowfortConventions(thresholds=thresholds)
        gtr = (_gtr_priv("ORDERS_ETL", "T1", "TABLE", "INSERT"),)
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck(conventions=conv).check_online(_no_cursor(), scan_context=ctx)
        assert any("ORDERS_ETL" in vio.resource_name for vio in v)

    def test_multiple_functional_roles_some_wired(self):
        """Mix: one functional role wired to business, one orphaned."""
        gtr = (
            _gtr_role_grant("SALES_TEAM", "SALES_READ"),
            _gtr_priv("FINANCE_ANALYST", "T1", "TABLE", "SELECT"),
        )
        ctx = _ctx(gtr=gtr)
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        names = [vio.resource_name for vio in v]
        assert not any("SALES_READ" in n for n in names)
        assert any("FINANCE_ANALYST" in n for n in names)

    def test_no_data_returns_empty(self):
        ctx = _ctx()
        v = IncompleteDepartmentRolesCheck().check_online(_no_cursor(), scan_context=ctx)
        assert v == []
