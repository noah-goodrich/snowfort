"""Tests for Session 6 Q1 2026 feature gap rules (SEC_018 – SEC_023, GOV_009)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.governance import IcebergTableGovernanceCheck
from snowfort_audit.domain.rules.security_advanced import (
    AIRedactPolicyCoverageCheck,
    AuthorizationPolicyCheck,
    PrivateLinkOnlyEnforcementCheck,
    ProgrammaticAccessTokenCheck,
    SnowparkContainerServicesSecurityCheck,
    TrustCenterExtensionsCheck,
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
# SEC_018 ProgrammaticAccessTokenCheck
# ---------------------------------------------------------------------------


class TestProgrammaticAccessTokenCheck:
    rule = ProgrammaticAccessTokenCheck()

    def test_no_violations(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_token_without_expiry(self):
        cur = _cursor([("MY_TOKEN", "USER1", None)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "no expiration" in violations[0].message

    def test_token_with_long_expiry(self):
        cur = _cursor([("LONG_TOKEN", "USER2", "2030-01-01")])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "90 days" in violations[0].message

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("boom")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_018"


# ---------------------------------------------------------------------------
# SEC_019 AIRedactPolicyCoverageCheck
# ---------------------------------------------------------------------------


class TestAIRedactPolicyCoverageCheck:
    rule = AIRedactPolicyCoverageCheck()

    def test_no_violations(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_sensitive_col_without_policy(self):
        cur = _cursor([("DB1", "SCH1", "TBL1", "EMAIL")])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "EMAIL" in violations[0].resource_name
        assert "AI_REDACT" in violations[0].message

    def test_multiple_cols(self):
        cur = _cursor(
            [
                ("DB1", "SCH1", "TBL1", "EMAIL"),
                ("DB1", "SCH1", "TBL1", "SSN"),
            ]
        )
        violations = self.rule.check_online(cur)
        assert len(violations) == 2

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(Exception("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_019"


# ---------------------------------------------------------------------------
# SEC_020 AuthorizationPolicyCheck
# ---------------------------------------------------------------------------


class TestAuthorizationPolicyCheck:
    rule = AuthorizationPolicyCheck()

    def test_no_violations(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_warehouse_without_policy(self):
        cur = _cursor([("PROD_WH",)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "PROD_WH" in violations[0].resource_name

    def test_multiple_warehouses(self):
        cur = _cursor([("WH1",), ("WH2",)])
        assert len(self.rule.check_online(cur)) == 2

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("boom")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_020"


# ---------------------------------------------------------------------------
# SEC_021 TrustCenterExtensionsCheck
# ---------------------------------------------------------------------------


class TestTrustCenterExtensionsCheck:
    rule = TrustCenterExtensionsCheck()

    def test_no_findings(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_high_finding(self):
        cur = _cursor([("CIS_BENCHMARK", "HIGH", 3)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "3" in violations[0].message
        assert "HIGH" in violations[0].message

    def test_critical_finding(self):
        cur = _cursor([("THREAT_INTELLIGENCE", "CRITICAL", 1)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(Exception("no view")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_021"


# ---------------------------------------------------------------------------
# SEC_022 PrivateLinkOnlyEnforcementCheck
# ---------------------------------------------------------------------------


class TestPrivateLinkOnlyEnforcementCheck:
    rule = PrivateLinkOnlyEnforcementCheck()

    def test_no_privatelink_configured(self):
        cur = MagicMock()
        cur.fetchall.return_value = [("",)]
        assert self.rule.check_online(cur) == []

    def test_privatelink_enforced(self):
        cur = MagicMock()
        # First call: SYSTEM$ALLOWLIST_PRIVATELINK → configured
        # Second call: SHOW PARAMETERS → TRUE
        cur.fetchall.side_effect = [
            [("privatelink.endpoint",)],
            [("ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS", "TRUE", "FALSE", "desc")],
        ]
        assert self.rule.check_online(cur) == []

    def test_privatelink_not_enforced(self):
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [("privatelink.endpoint",)],
            [("ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS", "FALSE", "FALSE", "desc")],
        ]
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "ENFORCE_PRIVATE_LINK" in violations[0].message

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(Exception("err")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_022"


# ---------------------------------------------------------------------------
# SEC_023 SnowparkContainerServicesSecurityCheck
# ---------------------------------------------------------------------------

_SPCS_DESCRIPTION = [("NAME",), ("STATUS",), ("COMMENT",)]


class TestSnowparkContainerServicesSecurityCheck:
    rule = SnowparkContainerServicesSecurityCheck()

    def test_no_services(self):
        cur = _cursor([], description=_SPCS_DESCRIPTION)
        assert self.rule.check_online(cur) == []

    def test_service_without_comment(self):
        cur = _cursor([("MY_SERVICE", "RUNNING", "")], description=_SPCS_DESCRIPTION)
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "MY_SERVICE" in violations[0].resource_name

    def test_service_with_comment(self):
        cur = _cursor(
            [("DOCUMENTED_SVC", "RUNNING", "Owner: data-team. ML inference service.")],
            description=_SPCS_DESCRIPTION,
        )
        assert self.rule.check_online(cur) == []

    def test_service_with_null_comment(self):
        cur = _cursor([("NULL_SVC", "RUNNING", None)], description=_SPCS_DESCRIPTION)
        violations = self.rule.check_online(cur)
        assert len(violations) == 1

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(RuntimeError("boom")))

    def test_rule_id(self):
        assert self.rule.id == "SEC_023"


# ---------------------------------------------------------------------------
# GOV_009 IcebergTableGovernanceCheck
# ---------------------------------------------------------------------------


class TestIcebergTableGovernanceCheck:
    rule = IcebergTableGovernanceCheck()

    def test_no_iceberg_tables(self):
        assert self.rule.check_online(_cursor([])) == []

    def test_table_with_no_catalog_and_zero_retention(self):
        cur = _cursor([("DB1", "SCH1", "ICEBERG_TBL", None, 0)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "no catalog integration" in violations[0].message
        assert "retention=0" in violations[0].message

    def test_table_with_catalog_and_retention(self):
        cur = _cursor([("DB1", "SCH1", "ICEBERG_TBL", "GLUE_CATALOG", 7)])
        assert self.rule.check_online(cur) == []

    def test_table_with_only_retention_missing(self):
        cur = _cursor([("DB1", "SCH1", "ICEBERG_TBL", "GLUE_CATALOG", 0)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "retention=0" in violations[0].message

    def test_table_with_only_catalog_missing(self):
        cur = _cursor([("DB1", "SCH1", "ICEBERG_TBL", None, 14)])
        violations = self.rule.check_online(cur)
        assert len(violations) == 1
        assert "no catalog integration" in violations[0].message

    def test_error_returns_empty(self):
        with pytest.raises(RuleExecutionError):
            self.rule.check_online(_cursor_raising(Exception("err")))

    def test_rule_id(self):
        assert self.rule.id == "GOV_009"
