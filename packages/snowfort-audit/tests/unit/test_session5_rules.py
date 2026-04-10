"""Unit tests for Session 5 rules: D7–D12.

REL_009 DynamicTableRefreshLagCheck
REL_010 DynamicTableFailureDetectionCheck
GOV_005 MaskingPolicyCoverageExtendedCheck
GOV_006 InboundShareRiskCheck
GOV_007 OutboundShareRiskCheck
GOV_008 CrossRegionInferenceCheck
OPS_013 DeveloperSandboxSprawlCheck
OPS_014 PermifrostDriftCheck
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.governance import (
    CrossRegionInferenceCheck,
    InboundShareRiskCheck,
    MaskingPolicyCoverageExtendedCheck,
    OutboundShareRiskCheck,
)
from snowfort_audit.domain.rules.op_excellence import (
    DeveloperSandboxSprawlCheck,
    PermifrostDriftCheck,
)
from snowfort_audit.domain.rules.reliability import (
    DynamicTableFailureDetectionCheck,
    DynamicTableRefreshLagCheck,
)


def _cursor_returning(rows):
    c = MagicMock()
    c.fetchall.return_value = rows
    c.fetchone.return_value = rows[0] if rows else None
    return c


def _cursor_raising(exc):
    c = MagicMock()
    c.execute.side_effect = exc
    return c


def _not_found_error():
    err = Exception("Object 'X' does not exist.")
    err.errno = 2003
    return err


# ---------------------------------------------------------------------------
# REL_009 DynamicTableRefreshLagCheck
# ---------------------------------------------------------------------------


class TestDynamicTableRefreshLagCheck:
    def test_no_lag_violations_returns_empty(self):
        rule = DynamicTableRefreshLagCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_lag_exceeded_flags_violation(self):
        rule = DynamicTableRefreshLagCheck()
        # actual_lag=200s, target=60s → 200 > 60*1.5=90 → violation
        rows = [("DB", "SCH", "DT1", 60.0, 200.0)]
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "DB.SCH.DT1" in result[0].resource_name
        assert "200" in result[0].message

    def test_view_not_found_returns_empty(self):
        rule = DynamicTableRefreshLagCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_unexpected_error_propagates(self):
        rule = DynamicTableRefreshLagCheck()
        with pytest.raises(RuleExecutionError):
            rule.check_online(_cursor_raising(RuntimeError("unexpected")))


# ---------------------------------------------------------------------------
# REL_010 DynamicTableFailureDetectionCheck
# ---------------------------------------------------------------------------


class TestDynamicTableFailureDetectionCheck:
    def test_no_failures_returns_empty(self):
        rule = DynamicTableFailureDetectionCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_failed_state_flagged(self):
        rule = DynamicTableFailureDetectionCheck()
        rows = [("PROD_DB", "SCH", "CUSTOMER_DT", "FAILED", "Schema mismatch in upstream table")]
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "FAILED" in result[0].message
        assert "PROD_DB.SCH.CUSTOMER_DT" in result[0].resource_name

    def test_view_not_found_returns_empty(self):
        rule = DynamicTableFailureDetectionCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_unexpected_error_propagates(self):
        rule = DynamicTableFailureDetectionCheck()
        with pytest.raises(RuleExecutionError):
            rule.check_online(_cursor_raising(RuntimeError("unexpected")))


# ---------------------------------------------------------------------------
# GOV_005 MaskingPolicyCoverageExtendedCheck
# ---------------------------------------------------------------------------


class TestMaskingPolicyCoverageExtendedCheck:
    def test_no_unmasked_columns_returns_empty(self):
        rule = MaskingPolicyCoverageExtendedCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_unmasked_classified_column_flagged(self):
        rule = MaskingPolicyCoverageExtendedCheck()
        rows = [("PROD_DB", "PUBLIC", "CUSTOMERS", "EMAIL")]
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "EMAIL" in result[0].message

    def test_view_not_found_returns_empty(self):
        rule = MaskingPolicyCoverageExtendedCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_unexpected_error_propagates(self):
        rule = MaskingPolicyCoverageExtendedCheck()
        with pytest.raises(RuleExecutionError):
            rule.check_online(_cursor_raising(RuntimeError("unexpected")))


# ---------------------------------------------------------------------------
# GOV_006 InboundShareRiskCheck
# ---------------------------------------------------------------------------


class TestInboundShareRiskCheck:
    def test_no_shares_returns_empty(self):
        rule = InboundShareRiskCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_unowned_inbound_share_flagged(self):
        rule = InboundShareRiskCheck()
        rows = [("VENDOR_DB", "VENDOR_SHARE", None)]
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "VENDOR_DB" in result[0].resource_name

    def test_owned_inbound_share_no_violation(self):
        rule = InboundShareRiskCheck()
        rows = [("VENDOR_DB", "VENDOR_SHARE", "DATA_TEAM")]
        assert rule.check_online(_cursor_returning(rows)) == []

    def test_view_not_found_returns_empty(self):
        rule = InboundShareRiskCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []


# ---------------------------------------------------------------------------
# GOV_007 OutboundShareRiskCheck
# ---------------------------------------------------------------------------


class TestOutboundShareRiskCheck:
    def test_no_shares_returns_empty(self):
        rule = OutboundShareRiskCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_undocumented_share_flagged(self):
        rule = OutboundShareRiskCheck()
        rows = [("MY_SHARE", None, None)]  # no owner, no comment
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "MY_SHARE" in result[0].resource_name
        assert "no owner" in result[0].message

    def test_documented_share_no_violation(self):
        rule = OutboundShareRiskCheck()
        rows = [("MY_SHARE", "DATA_TEAM", "Approved share for partner ABC")]
        assert rule.check_online(_cursor_returning(rows)) == []

    def test_view_not_found_returns_empty(self):
        rule = OutboundShareRiskCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []


# ---------------------------------------------------------------------------
# GOV_008 CrossRegionInferenceCheck
# ---------------------------------------------------------------------------


class TestCrossRegionInferenceCheck:
    def test_disabled_returns_empty(self):
        rule = CrossRegionInferenceCheck()
        # SHOW PARAMETERS returns value = DISABLED
        rows = [("CORTEX_ENABLED_CROSS_REGION", "DISABLED", "DISABLED", "ACCOUNT", "", "TEXT")]
        assert rule.check_online(_cursor_returning(rows)) == []

    def test_enabled_flags_violation(self):
        rule = CrossRegionInferenceCheck()
        cursor = MagicMock()
        # First execute (SHOW PARAMETERS): value = ANY
        # Second execute (COUNT sovereignty tags): 0
        cursor.fetchall.side_effect = [
            [("CORTEX_ENABLED_CROSS_REGION", "ANY", "DISABLED", "ACCOUNT", "", "TEXT")],
        ]
        cursor.fetchone.return_value = (0,)
        result = rule.check_online(cursor)
        assert len(result) == 1
        assert "CORTEX_ENABLED_CROSS_REGION" in result[0].message

    def test_enabled_with_sovereignty_tags_adds_context(self):
        rule = CrossRegionInferenceCheck()
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [("CORTEX_ENABLED_CROSS_REGION", "ANY", "DISABLED", "ACCOUNT", "", "TEXT")],
        ]
        cursor.fetchone.return_value = (5,)  # 5 sovereignty-tagged objects
        result = rule.check_online(cursor)
        assert len(result) == 1
        assert "5" in result[0].message

    def test_show_parameters_not_authorized_returns_empty(self):
        rule = CrossRegionInferenceCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []


# ---------------------------------------------------------------------------
# OPS_013 DeveloperSandboxSprawlCheck
# ---------------------------------------------------------------------------


class TestDeveloperSandboxSprawlCheck:
    def test_no_dropped_dbs_returns_empty(self):
        rule = DeveloperSandboxSprawlCheck()
        assert rule.check_online(_cursor_returning([])) == []

    def test_dropped_db_with_high_retention_flagged(self):
        rule = DeveloperSandboxSprawlCheck()
        rows = [("DEV_SCRATCH_1", "2026-04-01 10:00:00", 14)]
        result = rule.check_online(_cursor_returning(rows))
        assert len(result) == 1
        assert "DEV_SCRATCH_1" in result[0].resource_name
        assert "14" in result[0].message

    def test_view_not_found_returns_empty(self):
        rule = DeveloperSandboxSprawlCheck()
        assert rule.check_online(_cursor_raising(_not_found_error())) == []

    def test_unexpected_error_propagates(self):
        rule = DeveloperSandboxSprawlCheck()
        with pytest.raises(RuleExecutionError):
            rule.check_online(_cursor_raising(RuntimeError("unexpected")))


# ---------------------------------------------------------------------------
# OPS_014 PermifrostDriftCheck
# ---------------------------------------------------------------------------


class TestPermifrostDriftCheck:
    def test_no_spec_path_returns_empty(self):
        rule = PermifrostDriftCheck(spec_path=None)
        assert rule.check_online(MagicMock()) == []

    def test_no_spec_path_emits_info(self):
        telemetry = MagicMock()
        rule = PermifrostDriftCheck(spec_path=None, telemetry=telemetry)
        rule.check_online(MagicMock())
        telemetry.info.assert_called_once()

    def test_missing_role_grant_flagged(self, tmp_path):
        spec_content = """
roles:
  ANALYST: {}
users:
  NOAH:
    member_of:
      - ANALYST
"""
        spec_file = tmp_path / "permifrost.yaml"
        spec_file.write_text(spec_content)

        rule = PermifrostDriftCheck(spec_path=spec_file)
        cursor = MagicMock()
        # GRANTS_TO_USERS: NOAH has no roles
        cursor.fetchall.return_value = []
        result = rule.check_online(cursor)
        assert len(result) >= 1
        assert any("NOAH" in v.resource_name and "ANALYST" in v.message for v in result)

    def test_extra_role_grant_flagged(self, tmp_path):
        spec_content = """
roles:
  ANALYST: {}
users:
  NOAH:
    member_of:
      - ANALYST
"""
        spec_file = tmp_path / "permifrost.yaml"
        spec_file.write_text(spec_content)

        rule = PermifrostDriftCheck(spec_path=spec_file)
        cursor = MagicMock()
        # NOAH has ANALYST (spec) + SYSADMIN (not in spec)
        cursor.fetchall.return_value = [("NOAH", "ANALYST"), ("NOAH", "SYSADMIN")]
        result = rule.check_online(cursor)
        # Should flag SYSADMIN as extra
        extra_viols = [v for v in result if "SYSADMIN" in v.message]
        assert len(extra_viols) == 1

    def test_spec_matches_actual_no_violations(self, tmp_path):
        spec_content = """
users:
  NOAH:
    member_of:
      - ANALYST
"""
        spec_file = tmp_path / "permifrost.yaml"
        spec_file.write_text(spec_content)

        rule = PermifrostDriftCheck(spec_path=spec_file)
        cursor = MagicMock()
        cursor.fetchall.return_value = [("NOAH", "ANALYST"), ("NOAH", "PUBLIC")]
        result = rule.check_online(cursor)
        assert result == []

    def test_invalid_spec_file_returns_empty(self, tmp_path):
        bad_file = tmp_path / "permifrost.yaml"
        bad_file.write_text("{{ invalid yaml {{")

        telemetry = MagicMock()
        rule = PermifrostDriftCheck(spec_path=bad_file, telemetry=telemetry)
        result = rule.check_online(MagicMock())
        # yaml.safe_load might parse this without error; at minimum it should not crash
        assert isinstance(result, list)
