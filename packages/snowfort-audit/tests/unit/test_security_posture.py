"""Tests for Directive G security posture rules (SEC_030–036, COST_047)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cost import InactiveUserLicenseImpactCheck
from snowfort_audit.domain.rules.security_posture import (
    BruteForceDetectionCheck,
    LargeExportVolumeCheck,
    PeriodicRekeyingCheck,
    PrivateLinkRatioCheck,
    SessionPolicyCheck,
    ThreatIntelligenceFindingsCheck,
    TrustCenterScannerStatusCheck,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cursor(rows=(), description=None):
    """Cursor that returns a fixed set of rows."""
    cur = MagicMock()
    cur.fetchall.return_value = list(rows)
    cur.fetchone.return_value = rows[0] if rows else None
    cur.description = description
    return cur


def _cursor_raising(exc):
    cur = MagicMock()
    cur.execute.side_effect = exc
    return cur


def _not_found_error():
    err = Exception("Object not found")
    err.errno = 2003
    return err


# ---------------------------------------------------------------------------
# SEC_030 TrustCenterScannerStatusCheck
# ---------------------------------------------------------------------------


class TestTrustCenterScannerStatusCheck:
    rule = TrustCenterScannerStatusCheck()

    def test_all_scanners_enabled(self):
        # All rows have TRUE/ENABLED — no violations
        cur = _cursor(
            [
                ("SECURITY_ESSENTIALS", "TRUE", "ENABLED"),
                ("CIS_BENCHMARKS", "TRUE", "ENABLED"),
                ("THREAT_INTELLIGENCE", "TRUE", "ENABLED"),
            ]
        )
        assert self.rule.check_online(cur) == []

    def test_scanner_disabled(self):
        cur = _cursor(
            [
                ("SECURITY_ESSENTIALS", "TRUE", "ENABLED"),
                ("CIS_BENCHMARKS", "FALSE", "DISABLED"),
            ]
        )
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "CIS_BENCHMARKS" in violations[0].resource_name

    def test_no_scanners_found(self):
        cur = _cursor([])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "No Trust Center scanner packages found" in violations[0].message

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("boom")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_030"


# ---------------------------------------------------------------------------
# SEC_031 SessionPolicyCheck
# ---------------------------------------------------------------------------


class TestSessionPolicyCheck:
    rule = SessionPolicyCheck()

    def test_policy_exists(self):
        cur = _cursor([("MY_SESSION_POLICY", "30", "240")])
        assert self.rule.check_online(cur) == []

    def test_no_policy(self):
        cur = _cursor([])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "No session policy" in violations[0].message

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("crash")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_031"


# ---------------------------------------------------------------------------
# SEC_032 BruteForceDetectionCheck
# ---------------------------------------------------------------------------


class TestBruteForceDetectionCheck:
    rule = BruteForceDetectionCheck()

    def test_no_violations(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_brute_force_detected(self):
        cur = _cursor([("attacker_user", 15)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "attacker_user" in violations[0].message
        assert "15" in violations[0].message

    def test_multiple_users(self):
        cur = _cursor([("user1", 10), ("user2", 7)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 2

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_032"


# ---------------------------------------------------------------------------
# SEC_033 PrivateLinkRatioCheck
# ---------------------------------------------------------------------------


class TestPrivateLinkRatioCheck:
    rule = PrivateLinkRatioCheck()

    def test_high_ratio_pass(self):
        # 90% private — above 80% threshold
        cur = MagicMock()
        cur.fetchone.return_value = (90, 100)
        assert self.rule.check_online(cur) == []

    def test_low_ratio_fail(self):
        # 50% private — below 80% threshold
        cur = MagicMock()
        cur.fetchone.return_value = (50, 100)
        cur.fetchall.return_value = []
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "50.0%" in violations[0].message

    def test_no_private_logins_no_flag(self):
        # 0 private logins out of 100 — don't flag (no private link configured)
        cur = MagicMock()
        cur.fetchone.return_value = (0, 100)
        assert self.rule.check_online(cur) == []

    def test_no_logins(self):
        cur = MagicMock()
        cur.fetchone.return_value = (0, 0)
        assert self.rule.check_online(cur) == []

    def test_null_result(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        assert self.rule.check_online(cur) == []

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_033"


# ---------------------------------------------------------------------------
# SEC_034 LargeExportVolumeCheck
# ---------------------------------------------------------------------------


class TestLargeExportVolumeCheck:
    rule = LargeExportVolumeCheck()

    def test_no_violations(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_large_export_flagged(self):
        cur = _cursor([("export_2024.csv", "CUSTOMERS", 5_000_000)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "5,000,000" in violations[0].message
        assert "CUSTOMERS" in violations[0].resource_name

    def test_multiple_exports(self):
        cur = _cursor(
            [
                ("file1.csv", "T1", 2_000_000),
                ("file2.csv", "T2", 3_000_000),
            ]
        )
        violations = self.rule.check_online(cur)
        assert len(violations) == 2

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_034"


# ---------------------------------------------------------------------------
# SEC_035 PeriodicRekeyingCheck
# ---------------------------------------------------------------------------


class TestPeriodicRekeyingCheck:
    rule = PeriodicRekeyingCheck()

    def test_rekeying_enabled(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("PERIODIC_DATA_REKEYING", "TRUE", "FALSE", "desc")
        assert self.rule.check_online(cur) == []

    def test_rekeying_disabled(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("PERIODIC_DATA_REKEYING", "FALSE", "FALSE", "desc")
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "not enabled" in violations[0].message

    def test_parameter_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "not found" in violations[0].message

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_035"


# ---------------------------------------------------------------------------
# SEC_036 ThreatIntelligenceFindingsCheck
# ---------------------------------------------------------------------------


class TestThreatIntelligenceFindingsCheck:
    rule = ThreatIntelligenceFindingsCheck()

    def test_no_findings(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_critical_findings(self):
        cur = _cursor([("CRITICAL", 2)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "2" in violations[0].message
        assert "CRITICAL" in violations[0].message

    def test_multiple_severities(self):
        cur = _cursor([("HIGH", 3), ("CRITICAL", 1)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 2

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_036"


# ---------------------------------------------------------------------------
# COST_047 InactiveUserLicenseImpactCheck
# ---------------------------------------------------------------------------


class TestInactiveUserLicenseImpactCheck:
    rule = InactiveUserLicenseImpactCheck()

    def test_no_inactive_users(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_inactive_user_with_grants(self):
        cur = _cursor([("OLD_USER", "2023-01-01", 5)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "OLD_USER" in violations[0].message
        assert "5" in violations[0].message

    def test_multiple_inactive_users(self):
        cur = _cursor(
            [
                ("USER_A", None, 3),
                ("USER_B", "2022-06-01", 2),
            ]
        )
        violations = self.rule.check_online(cur)
        assert len(violations) == 2

    def test_errno_2003_graceful(self):
        assert self.rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_non_allowlisted_error(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("err")))

    def test_rule_id(self):
        assert self.rule.id == "COST_047"
