"""Unit tests for Directive E — IaC Drift Detection + dbt Grant Analysis rules.

Coverage targets:
  OPS_015  IacToolDetectionCheck          ≥5 tests
  OPS_016  IacDriftIndicatorsCheck        ≥5 tests
  GOV_025  DbtGrantTargetValidationCheck  ≥5 tests
  GOV_026  DbtSchemaOwnershipCheck        ≥5 tests
  _iac     detect_iac_tools / managed_tag_coverage_by_database / parse_grant_target_role helpers
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.conventions import (
    DbtGrantsThresholds,
    IacDriftThresholds,
    RuleThresholdConventions,
    SnowfortConventions,
)
from snowfort_audit.domain.rule_definitions import FindingCategory, RuleExecutionError, Severity
from snowfort_audit.domain.rules._iac import (
    QH_IAC_CACHE_WINDOW,
    SCHEMA_OWNERS_CACHE_WINDOW,
    detect_iac_tools,
    managed_tag_coverage_by_database,
    parse_grant_target_role,
)
from snowfort_audit.domain.rules.iac_drift import (
    DbtGrantTargetValidationCheck,
    DbtSchemaOwnershipCheck,
    IacDriftIndicatorsCheck,
    IacToolDetectionCheck,
)
from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Tuple-building helpers (match _iac.py column order)
# ---------------------------------------------------------------------------


def _qh_iac_row(user: str, tool_label: str, count: int) -> tuple:
    """Build a QUERY_HISTORY_IAC aggregated row."""
    return (user, tool_label, count)


def _ddl_row(user: str, query_type: str, db: str, schema: str, count: int) -> tuple:
    """Build a QUERY_HISTORY_DDL_NON_SVC aggregated row."""
    return (user, query_type, db, schema, count)


def _grant_row(query_text: str, user: str = "SVC_DBT") -> tuple:
    """Build a QUERY_HISTORY_DBT_GRANTS row."""
    return (query_text, user)


def _schema_owner_row(catalog: str, schema: str, owner: str) -> tuple:
    """Build a SCHEMATA_OWNERS row."""
    return (catalog, schema, owner)


# ---------------------------------------------------------------------------
# ScanContext helpers
# ---------------------------------------------------------------------------


def _ctx(
    *,
    qh_iac: tuple = (),
    ddl_non_svc: tuple = (),
    dbt_grants: tuple = (),
    schema_owners: tuple = (),
    tag_refs_index: dict | None = None,
    users: tuple | None = None,
    users_cols: dict | None = None,
    databases: tuple | None = None,
    databases_cols: dict | None = None,
) -> ScanContext:
    """Build a ScanContext pre-seeded with IaC/dbt data."""
    ctx = ScanContext()
    ctx.get_or_fetch("QUERY_HISTORY_IAC", QH_IAC_CACHE_WINDOW, lambda v, w: qh_iac)
    ctx.get_or_fetch("QUERY_HISTORY_DDL_NON_SVC", QH_IAC_CACHE_WINDOW, lambda v, w: ddl_non_svc)
    ctx.get_or_fetch("QUERY_HISTORY_DBT_GRANTS", QH_IAC_CACHE_WINDOW, lambda v, w: dbt_grants)
    ctx.get_or_fetch("SCHEMATA_OWNERS", SCHEMA_OWNERS_CACHE_WINDOW, lambda v, w: schema_owners)
    if tag_refs_index is not None:
        ctx.tag_refs_index = tag_refs_index
    if users is not None:
        ctx.users = users
        ctx.users_cols = users_cols or {"name": 0}
    if databases is not None:
        ctx.databases = databases
        ctx.databases_cols = databases_cols or {"name": 0}
    return ctx


def _no_cursor() -> MagicMock:
    c = MagicMock()
    c.execute.side_effect = AssertionError("cursor must not be used when scan_context is set")
    return c


def _sf_error(errno: int = 2003):
    """Create a mock Snowflake error with the given errno."""
    exc = Exception("mock SF error")
    exc.errno = errno  # type: ignore[attr-defined]
    return exc


def _conventions(**iac_overrides) -> SnowfortConventions:
    """Build conventions with optional IaC threshold overrides."""
    iac = IacDriftThresholds(**iac_overrides) if iac_overrides else IacDriftThresholds()
    thresholds = RuleThresholdConventions(iac_drift=iac)
    return SnowfortConventions(thresholds=thresholds)


def _dbt_conventions(**dbt_overrides) -> SnowfortConventions:
    """Build conventions with optional dbt grant threshold overrides."""
    dbt = DbtGrantsThresholds(**dbt_overrides) if dbt_overrides else DbtGrantsThresholds()
    thresholds = RuleThresholdConventions(dbt_grants=dbt)
    return SnowfortConventions(thresholds=thresholds)


# ---------------------------------------------------------------------------
# Helpers: detect_iac_tools
# ---------------------------------------------------------------------------


class TestDetectIacTools:
    def test_empty(self):
        assert detect_iac_tools((), None) == {}

    def test_from_query_history(self):
        rows = (_qh_iac_row("SVC_TF", "TERRAFORM", 42),)
        tools = detect_iac_tools(rows, None)
        assert "TERRAFORM" in tools
        assert any("42 queries" in e for e in tools["TERRAFORM"])

    def test_from_managed_by_tags(self):
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("DATABASE", "PROD_DB"): {"MANAGED_BY": "terraform"},
        }
        tools = detect_iac_tools((), tag_index)
        assert "TERRAFORM" in tools

    def test_combined_sources(self):
        rows = (_qh_iac_row("SVC_DBT", "DBT", 10),)
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("DATABASE", "ANALYTICS"): {"MANAGED_BY": "dbt"},
        }
        tools = detect_iac_tools(rows, tag_index)
        assert "DBT" in tools
        assert len(tools["DBT"]) >= 2

    def test_other_label_excluded(self):
        rows = (_qh_iac_row("HUMAN_USER", "OTHER", 5),)
        tools = detect_iac_tools(rows, None)
        assert tools == {}


# ---------------------------------------------------------------------------
# Helpers: managed_tag_coverage_by_database
# ---------------------------------------------------------------------------


class TestManagedTagCoverage:
    def test_empty(self):
        assert managed_tag_coverage_by_database(None, None, None) == {}

    def test_full_coverage(self):
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"MANAGED_BY": "terraform"},
        }
        cov = managed_tag_coverage_by_database(tag_index, None, None)
        assert cov.get("PROD") == 1.0

    def test_partial_coverage(self):
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"COST_CENTER": "finance"},
        }
        cov = managed_tag_coverage_by_database(tag_index, None, None)
        assert cov.get("PROD") == 0.5

    def test_system_dbs_excluded(self):
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "SNOWFLAKE.ACCOUNT_USAGE.T1"): {"MANAGED_BY": "system"},
        }
        cov = managed_tag_coverage_by_database(tag_index, None, None)
        assert "SNOWFLAKE" not in cov


# ---------------------------------------------------------------------------
# Helpers: parse_grant_target_role
# ---------------------------------------------------------------------------


class TestParseGrantTargetRole:
    def test_standard_grant(self):
        assert parse_grant_target_role("GRANT SELECT ON TABLE T TO ROLE ANALYTICS_READ") == "ANALYTICS_READ"

    def test_quoted_role(self):
        assert parse_grant_target_role('GRANT USAGE ON SCHEMA S TO ROLE "My_Role"') == "MY_ROLE"

    def test_no_role_keyword(self):
        assert parse_grant_target_role("GRANT SELECT ON TABLE T TO USER foo") is None

    def test_case_insensitive(self):
        assert parse_grant_target_role("grant select on table t to role my_read") == "MY_READ"


# ---------------------------------------------------------------------------
# OPS_015: IacToolDetectionCheck
# ---------------------------------------------------------------------------


class TestIacToolDetectionCheck:
    def test_no_tools_detected(self):
        """No IaC evidence → informational 'consider adopting IaC'."""
        rule = IacToolDetectionCheck()
        ctx = _ctx()
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "No IaC tools detected" in v[0].message
        assert v[0].category == FindingCategory.INFORMATIONAL

    def test_terraform_detected_via_query_history(self):
        """Terraform comment in QUERY_HISTORY → informational detection."""
        rule = IacToolDetectionCheck()
        ctx = _ctx(qh_iac=(_qh_iac_row("SVC_TF", "TERRAFORM", 100),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert any("TERRAFORM" in vi.message for vi in v)
        assert all(vi.category == FindingCategory.INFORMATIONAL for vi in v)

    def test_dbt_detected_via_tags(self):
        """MANAGED_BY=dbt tag → detection."""
        rule = IacToolDetectionCheck()
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("DATABASE", "ANALYTICS"): {"MANAGED_BY": "dbt"},
        }
        ctx = _ctx(tag_refs_index=tag_index)
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert any("DBT" in vi.message for vi in v)

    def test_multiple_tools_detected(self):
        """Multiple tools → one finding per tool."""
        rule = IacToolDetectionCheck()
        ctx = _ctx(
            qh_iac=(
                _qh_iac_row("SVC_TF", "TERRAFORM", 50),
                _qh_iac_row("SVC_DBT", "DBT", 30),
            ),
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        messages = " ".join(vi.message for vi in v)
        assert "TERRAFORM" in messages
        assert "DBT" in messages

    def test_service_account_pattern_detection(self):
        """Service account matching IaC pattern → detection."""
        rule = IacToolDetectionCheck()
        ctx = _ctx(users=(("SVC_TERRAFORM",),), users_cols={"name": 0})
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) >= 1
        assert any("SVC_TERRAFORM" in vi.message for vi in v)

    def test_custom_comment_patterns(self):
        """Custom comment patterns from conventions are used."""
        conv = _conventions(iac_comment_patterns=(r"(?i)custom_tool",))
        rule = IacToolDetectionCheck(conventions=conv)
        ctx = _ctx(qh_iac=(_qh_iac_row("BOT", "CUSTOM_TOOL", 10),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert any("CUSTOM_TOOL" in vi.message for vi in v)

    def test_allowlisted_sf_error(self):
        """Snowflake error 2003 (view not found) → empty result, no raise."""
        rule = IacToolDetectionCheck()
        # Use a fresh ScanContext so get_or_fetch calls the fetcher (which will hit the cursor).
        ctx = ScanContext()
        cursor = MagicMock()
        cursor.execute.side_effect = _sf_error(2003)
        v = rule.check_online(cursor, scan_context=ctx)
        assert v == []

    def test_non_allowlisted_sf_error(self):
        """Non-allowlisted Snowflake error → RuleExecutionError."""
        rule = IacToolDetectionCheck()
        ctx = ScanContext()
        cursor = MagicMock()
        cursor.execute.side_effect = _sf_error(9999)
        with pytest.raises(RuleExecutionError):
            rule.check_online(cursor, scan_context=ctx)


# ---------------------------------------------------------------------------
# OPS_016: IacDriftIndicatorsCheck
# ---------------------------------------------------------------------------


class TestIacDriftIndicatorsCheck:
    def test_no_drift_no_tags(self):
        """No IaC tags, no DDL by non-svc → no findings."""
        rule = IacDriftIndicatorsCheck()
        ctx = _ctx()
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_ddl_drift_on_managed_database(self):
        """DDL by non-service-account on an IaC-managed database → drift finding."""
        rule = IacDriftIndicatorsCheck()
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"MANAGED_BY": "terraform"},
        }
        ctx = _ctx(
            ddl_non_svc=(_ddl_row("ALICE", "ALTER", "PROD", "PUBLIC", 5),),
            tag_refs_index=tag_index,
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) >= 1
        assert any("PROD" in vi.resource_name for vi in v)
        assert any("drift" in vi.message.lower() for vi in v)

    def test_ddl_on_unmanaged_database_no_finding(self):
        """DDL on a database with 0% tag coverage → no drift finding."""
        rule = IacDriftIndicatorsCheck()
        ctx = _ctx(ddl_non_svc=(_ddl_row("ALICE", "CREATE", "DEV", "PUBLIC", 3),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        # No tag coverage → DEV is not considered managed → no drift
        assert v == []

    def test_coverage_gap_finding(self):
        """Database with partial tag coverage → coverage gap finding."""
        rule = IacDriftIndicatorsCheck()
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"COST_CENTER": "eng"},
        }
        ctx = _ctx(tag_refs_index=tag_index)
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert any("coverage gap" in vi.message.lower() for vi in v)

    def test_full_coverage_no_gap_finding(self):
        """Database with 100% tag coverage → no coverage gap."""
        rule = IacDriftIndicatorsCheck()
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"MANAGED_BY": "terraform"},
        }
        ctx = _ctx(tag_refs_index=tag_index)
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        # 100% coverage → no gap findings (there may be ddl drift findings from empty ddl)
        gap_findings = [vi for vi in v if "coverage gap" in vi.message.lower()]
        assert gap_findings == []

    def test_custom_coverage_threshold(self):
        """Custom threshold changes what counts as 'managed'."""
        conv = _conventions(managed_tag_coverage_threshold=0.90)
        rule = IacDriftIndicatorsCheck(conventions=conv)
        # 50% coverage is below 90% threshold → not considered managed, no gap finding
        tag_index: dict[tuple[str, str], dict[str, str]] = {
            ("TABLE", "PROD.PUBLIC.T1"): {"MANAGED_BY": "terraform"},
            ("TABLE", "PROD.PUBLIC.T2"): {"COST_CENTER": "eng"},
        }
        ctx = _ctx(
            ddl_non_svc=(_ddl_row("ALICE", "ALTER", "PROD", "PUBLIC", 5),),
            tag_refs_index=tag_index,
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        # 50% < 90% → PROD not managed → no drift finding
        drift_findings = [vi for vi in v if "drift" in vi.message.lower() and "coverage" not in vi.message.lower()]
        assert drift_findings == []

    def test_allowlisted_sf_error(self):
        """Snowflake error 2003 → empty result."""
        rule = IacDriftIndicatorsCheck()
        cursor = MagicMock()
        cursor.execute.side_effect = _sf_error(2003)
        v = rule.check_online(cursor, scan_context=None)
        assert v == []

    def test_no_scan_context(self):
        """No scan_context → empty result (graceful degradation)."""
        rule = IacDriftIndicatorsCheck()
        cursor = MagicMock()
        v = rule.check_online(cursor, scan_context=None)
        assert v == []


# ---------------------------------------------------------------------------
# GOV_025: DbtGrantTargetValidationCheck
# ---------------------------------------------------------------------------


class TestDbtGrantTargetValidationCheck:
    def test_no_dbt_grants(self):
        """No dbt grant queries → no findings."""
        rule = DbtGrantTargetValidationCheck()
        ctx = _ctx()
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_grant_to_functional_role_clean(self):
        """Grant to functional role → no finding."""
        rule = DbtGrantTargetValidationCheck()
        ctx = _ctx(dbt_grants=(_grant_row("GRANT SELECT ON TABLE T TO ROLE ANALYTICS_READ"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_grant_to_business_role_violation(self):
        """Grant to business role → violation."""
        rule = DbtGrantTargetValidationCheck()
        ctx = _ctx(dbt_grants=(_grant_row("GRANT SELECT ON TABLE T TO ROLE FINANCE_TEAM"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "FINANCE_TEAM" in v[0].resource_name
        assert v[0].category == FindingCategory.ACTIONABLE

    def test_grant_to_role_matching_both_patterns(self):
        """Role matching both business AND functional patterns → no violation (functional wins)."""
        conv = _dbt_conventions(
            functional_role_pattern=r"(?i).*_READ$",
            business_role_pattern=r"(?i).*_TEAM_READ$",
        )
        rule = DbtGrantTargetValidationCheck(conventions=conv)
        ctx = _ctx(dbt_grants=(_grant_row("GRANT SELECT ON TABLE T TO ROLE FINANCE_TEAM_READ"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        # Matches functional → not flagged
        assert v == []

    def test_multiple_grants_same_role_deduplicated(self):
        """Multiple grants to same business role → only one finding."""
        rule = DbtGrantTargetValidationCheck()
        ctx = _ctx(
            dbt_grants=(
                _grant_row("GRANT SELECT ON TABLE T1 TO ROLE MARKETING_TEAM"),
                _grant_row("GRANT INSERT ON TABLE T2 TO ROLE MARKETING_TEAM"),
            )
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_custom_patterns(self):
        """Custom business/functional role patterns from conventions."""
        conv = _dbt_conventions(
            functional_role_pattern=r"(?i).*_ACCESS$",
            business_role_pattern=r"(?i).*_GROUP$",
        )
        rule = DbtGrantTargetValidationCheck(conventions=conv)
        ctx = _ctx(dbt_grants=(_grant_row("GRANT SELECT ON TABLE T TO ROLE ENG_GROUP"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "ENG_GROUP" in v[0].resource_name

    def test_unparseable_grant_ignored(self):
        """Grant statement that can't be parsed → silently skipped."""
        rule = DbtGrantTargetValidationCheck()
        ctx = _ctx(
            dbt_grants=(
                _grant_row("SELECT 1"),  # not a GRANT statement
            )
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_allowlisted_sf_error(self):
        """Snowflake error 2003 → empty result."""
        rule = DbtGrantTargetValidationCheck()
        cursor = MagicMock()
        cursor.execute.side_effect = _sf_error(2003)
        v = rule.check_online(cursor, scan_context=None)
        assert v == []


# ---------------------------------------------------------------------------
# GOV_026: DbtSchemaOwnershipCheck
# ---------------------------------------------------------------------------


class TestDbtSchemaOwnershipCheck:
    def test_no_schemas(self):
        """No schemas → no findings."""
        rule = DbtSchemaOwnershipCheck()
        ctx = _ctx()
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_schema_owned_by_dbo_role_clean(self):
        """Schema owned by DBO role → no finding."""
        rule = DbtSchemaOwnershipCheck()
        ctx = _ctx(schema_owners=(_schema_owner_row("ANALYTICS", "STAGING", "ANALYTICS_DBO"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_schema_owned_by_non_dbt_user_clean(self):
        """Schema owned by a non-dbt user → no finding (not our concern)."""
        rule = DbtSchemaOwnershipCheck()
        ctx = _ctx(schema_owners=(_schema_owner_row("ANALYTICS", "STAGING", "SYSADMIN"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert v == []

    def test_schema_owned_by_dbt_service_account_violation(self):
        """Schema owned by dbt service account → violation."""
        rule = DbtSchemaOwnershipCheck()
        ctx = _ctx(schema_owners=(_schema_owner_row("ANALYTICS", "STAGING", "SVC_DBT"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1
        assert "ANALYTICS.STAGING" in v[0].resource_name
        assert "SVC_DBT" in v[0].message
        assert v[0].category == FindingCategory.ACTIONABLE

    def test_multiple_schemas_multiple_violations(self):
        """Multiple schemas owned by dbt → one finding each."""
        rule = DbtSchemaOwnershipCheck()
        ctx = _ctx(
            schema_owners=(
                _schema_owner_row("ANALYTICS", "RAW", "DBT_USER"),
                _schema_owner_row("ANALYTICS", "STAGING", "DBT_USER"),
                _schema_owner_row("ANALYTICS", "MARTS", "ANALYTICS_DBO"),
            )
        )
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 2

    def test_custom_service_account_pattern(self):
        """Custom dbt service account pattern from conventions."""
        conv = _dbt_conventions(dbt_service_account_pattern=r"(?i)(DEPLOY_BOT)")
        rule = DbtSchemaOwnershipCheck(conventions=conv)
        ctx = _ctx(schema_owners=(_schema_owner_row("PROD", "CORE", "DEPLOY_BOT"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(v) == 1

    def test_custom_dbo_role_pattern(self):
        """Custom DBO pattern — matching owner is not flagged."""
        conv = _dbt_conventions(
            dbt_service_account_pattern=r"(?i)(SVC_DBT)",
            dbo_role_pattern=r"(?i)(SVC_DBT)",  # treat SVC_DBT as a DBO role (edge case)
        )
        rule = DbtSchemaOwnershipCheck(conventions=conv)
        ctx = _ctx(schema_owners=(_schema_owner_row("PROD", "CORE", "SVC_DBT"),))
        v = rule.check_online(_no_cursor(), scan_context=ctx)
        # Matches both service account AND DBO → DBO exemption → no finding
        assert v == []

    def test_allowlisted_sf_error(self):
        """Snowflake error 2003 → empty result."""
        rule = DbtSchemaOwnershipCheck()
        cursor = MagicMock()
        cursor.execute.side_effect = _sf_error(2003)
        v = rule.check_online(cursor, scan_context=None)
        assert v == []

    def test_no_scan_context(self):
        """No scan_context → empty result."""
        rule = DbtSchemaOwnershipCheck()
        cursor = MagicMock()
        cursor.execute.return_value = None
        cursor.fetchall.return_value = []
        v = rule.check_online(cursor, scan_context=None)
        assert v == []


# ---------------------------------------------------------------------------
# Rule metadata sanity checks
# ---------------------------------------------------------------------------


class TestRuleMetadata:
    def test_ops_015_metadata(self):
        rule = IacToolDetectionCheck()
        assert rule.id == "OPS_015"
        assert rule.severity == Severity.LOW
        assert rule.pillar == "Operations"

    def test_ops_016_metadata(self):
        rule = IacDriftIndicatorsCheck()
        assert rule.id == "OPS_016"
        assert rule.severity == Severity.MEDIUM
        assert rule.pillar == "Operations"

    def test_gov_025_metadata(self):
        rule = DbtGrantTargetValidationCheck()
        assert rule.id == "GOV_025"
        assert rule.severity == Severity.MEDIUM
        assert rule.pillar == "Governance"

    def test_gov_026_metadata(self):
        rule = DbtSchemaOwnershipCheck()
        assert rule.id == "GOV_026"
        assert rule.severity == Severity.LOW
        assert rule.pillar == "Governance"
