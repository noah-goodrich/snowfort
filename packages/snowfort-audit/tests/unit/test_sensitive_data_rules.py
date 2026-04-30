"""Unit tests for Directive D — Sensitive Data Detection rules.

Coverage targets:
  GOV_030  UnmaskedSensitiveColumnsCheck    ≥5 tests
  GOV_031  UntaggedSensitiveColumnsCheck    ≥5 tests
  GOV_032  NoRowPolicyOnSensitiveTableCheck ≥5 tests
  GOV_033  OverPermissiveSensitiveAccessCheck ≥5 tests
  GOV_034  ContentPiiDetectionCheck         ≥5 tests
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.conventions import (
    ColumnPatternDef,
    SensitiveDataThresholds,
    SnowfortConventions,
)
from snowfort_audit.domain.rules.sensitive_data import (
    ContentPiiDetectionCheck,
    NoRowPolicyOnSensitiveTableCheck,
    OverPermissiveSensitiveAccessCheck,
    UnmaskedSensitiveColumnsCheck,
    UntaggedSensitiveColumnsCheck,
)
from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Tuple-building helpers
# ---------------------------------------------------------------------------


def _col_row(
    catalog: str = "MYDB",
    schema: str = "PUBLIC",
    table: str = "USERS",
    column: str = "EMAIL",
    data_type: str = "VARCHAR",
) -> tuple:
    """Build a row for ACCOUNT_USAGE.COLUMNS."""
    return (catalog, schema, table, column, data_type)


def _policy_row(
    db: str = "MYDB",
    schema: str = "PUBLIC",
    table: str = "USERS",
    column: str | None = "EMAIL",
    kind: str = "MASKING_POLICY",
) -> tuple:
    """Build a row for ACCOUNT_USAGE.POLICY_REFERENCES."""
    return (db, schema, table, column, kind)


def _tag_row(
    db: str = "MYDB",
    schema: str = "PUBLIC",
    table: str = "USERS",
    column: str = "EMAIL",
    tag_name: str = "SENSITIVITY",
    tag_value: str = "PII",
) -> tuple:
    """Build a row for ACCOUNT_USAGE.TAG_REFERENCES (COLUMN domain)."""
    return (db, schema, table, column, tag_name, tag_value)


def _gtr_select(
    role: str = "ANALYST",
    table_name: str = "USERS",
    catalog: str = "MYDB",
    granted_on: str = "TABLE",
) -> tuple:
    """Build a SELECT grant-to-role row (index order: grantee, name, granted_on, priv, catalog, granted_to)."""
    return (role, table_name, granted_on, "SELECT", catalog, "ROLE")


def _gtr_other(
    role: str = "ANALYST",
    table_name: str = "USERS",
    catalog: str = "MYDB",
    priv: str = "INSERT",
    granted_on: str = "TABLE",
) -> tuple:
    """Build a non-SELECT grant-to-role row."""
    return (role, table_name, granted_on, priv, catalog, "ROLE")


# ---------------------------------------------------------------------------
# ScanContext helpers
# ---------------------------------------------------------------------------


def _ctx(
    columns: tuple = (),
    policy_refs: tuple = (),
    tag_refs: tuple = (),
    gtr: tuple = (),
) -> ScanContext:
    """Build a ScanContext pre-seeded with all four cache keys."""
    ctx = ScanContext()
    ctx.get_or_fetch("ACCOUNT_USAGE.COLUMNS", 0, lambda v, w: columns)
    ctx.get_or_fetch("ACCOUNT_USAGE.POLICY_REFERENCES", 0, lambda v, w: policy_refs)
    ctx.get_or_fetch("ACCOUNT_USAGE.TAG_REFERENCES_COLUMNS", 0, lambda v, w: tag_refs)
    ctx.get_or_fetch("GRANTS_TO_ROLES", 0, lambda v, w: gtr)
    return ctx


def _no_cursor() -> MagicMock:
    c = MagicMock()
    c.execute.side_effect = AssertionError("cursor must not be used when scan_context is set")
    return c


def _conventions(thresholds: SensitiveDataThresholds) -> SnowfortConventions:
    """Build a SnowfortConventions instance with custom sensitive_data thresholds."""
    c = SnowfortConventions()
    object.__setattr__(c.thresholds, "sensitive_data", thresholds)
    return c


# ---------------------------------------------------------------------------
# GOV_030 — UnmaskedSensitiveColumnsCheck
# ---------------------------------------------------------------------------


class TestUnmaskedSensitiveColumnsCheck:
    def test_scan_context_none_returns_empty(self):
        rule = UnmaskedSensitiveColumnsCheck()
        assert rule.check_online(_no_cursor(), scan_context=None) == []

    def test_no_sensitive_columns_no_violations(self):
        rule = UnmaskedSensitiveColumnsCheck()
        ctx = _ctx(columns=(_col_row(column="NOTES"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_masked_column_no_violation(self):
        rule = UnmaskedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(_col_row(column="EMAIL"),),
            policy_refs=(_policy_row(column="EMAIL", kind="MASKING_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_unmasked_sensitive_column_is_flagged(self):
        rule = UnmaskedSensitiveColumnsCheck()
        ctx = _ctx(columns=(_col_row(column="EMAIL"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "EMAIL" in result[0].resource_name
        assert "masking policy" in result[0].message

    def test_below_threshold_no_violation(self):
        # min_sensitive_columns_unmasked=2; only 1 unmasked column → no violation
        thresholds = SensitiveDataThresholds(min_sensitive_columns_unmasked=2)
        rule = UnmaskedSensitiveColumnsCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_partially_masked_only_unmasked_flagged(self):
        rule = UnmaskedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
            ),
            policy_refs=(_policy_row(column="EMAIL", kind="MASKING_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "SSN" in result[0].resource_name

    def test_multiple_tables_each_evaluated_independently(self):
        rule = UnmaskedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(
                _col_row(catalog="DB", schema="S", table="T1", column="EMAIL"),
                _col_row(catalog="DB", schema="S", table="T2", column="SSN"),
            ),
            policy_refs=(_policy_row(db="DB", schema="S", table="T1", column="EMAIL", kind="MASKING_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "T2" in result[0].resource_name

    def test_case_insensitive_masking_lookup(self):
        rule = UnmaskedSensitiveColumnsCheck()
        # Column stored as lowercase, policy reference stored as uppercase
        ctx = _ctx(
            columns=(_col_row(column="email"),),
            policy_refs=(_policy_row(column="EMAIL", kind="MASKING_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_rule_id(self):
        assert UnmaskedSensitiveColumnsCheck().id == "GOV_030"


# ---------------------------------------------------------------------------
# GOV_031 — UntaggedSensitiveColumnsCheck
# ---------------------------------------------------------------------------


class TestUntaggedSensitiveColumnsCheck:
    def test_scan_context_none_returns_empty(self):
        rule = UntaggedSensitiveColumnsCheck()
        assert rule.check_online(_no_cursor(), scan_context=None) == []

    def test_no_sensitive_columns_no_violations(self):
        rule = UntaggedSensitiveColumnsCheck()
        ctx = _ctx(columns=(_col_row(column="NOTES"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_tagged_column_no_violation(self):
        rule = UntaggedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(_col_row(column="EMAIL"),),
            tag_refs=(_tag_row(column="EMAIL"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_untagged_sensitive_column_is_flagged(self):
        rule = UntaggedSensitiveColumnsCheck()
        ctx = _ctx(columns=(_col_row(column="EMAIL"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "tag" in result[0].message

    def test_below_threshold_no_violation(self):
        thresholds = SensitiveDataThresholds(min_sensitive_columns_untagged=2)
        rule = UntaggedSensitiveColumnsCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_partially_tagged_only_untagged_flagged(self):
        rule = UntaggedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
            ),
            tag_refs=(_tag_row(column="EMAIL"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "SSN" in result[0].resource_name

    def test_case_insensitive_tag_lookup(self):
        rule = UntaggedSensitiveColumnsCheck()
        ctx = _ctx(
            columns=(_col_row(column="email"),),
            tag_refs=(_tag_row(column="EMAIL"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_rule_id(self):
        assert UntaggedSensitiveColumnsCheck().id == "GOV_031"


# ---------------------------------------------------------------------------
# GOV_032 — NoRowPolicyOnSensitiveTableCheck
# ---------------------------------------------------------------------------


class TestNoRowPolicyOnSensitiveTableCheck:
    def test_scan_context_none_returns_empty(self):
        rule = NoRowPolicyOnSensitiveTableCheck()
        assert rule.check_online(_no_cursor(), scan_context=None) == []

    def test_no_sensitive_columns_no_violations(self):
        rule = NoRowPolicyOnSensitiveTableCheck()
        ctx = _ctx(columns=(_col_row(column="NOTES"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_table_with_row_policy_no_violation(self):
        rule = NoRowPolicyOnSensitiveTableCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
                _col_row(column="PHONE"),
            ),
            # Row-access policies have column=None
            policy_refs=(_policy_row(column=None, kind="ROW_ACCESS_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_table_without_row_policy_above_threshold_flagged(self):
        rule = NoRowPolicyOnSensitiveTableCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
                _col_row(column="PHONE"),
            ),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "row-access policy" in result[0].message

    def test_below_threshold_no_violation(self):
        # default min_sensitive_columns_no_row_policy=3; only 2 cols
        rule = NoRowPolicyOnSensitiveTableCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
            ),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_custom_threshold_respected(self):
        thresholds = SensitiveDataThresholds(min_sensitive_columns_no_row_policy=2)
        rule = NoRowPolicyOnSensitiveTableCheck(conventions=_conventions(thresholds))
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
            ),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1

    def test_masking_policy_does_not_satisfy_row_policy(self):
        # A masking policy row has column IS NOT None → not counted as row policy
        rule = NoRowPolicyOnSensitiveTableCheck()
        ctx = _ctx(
            columns=(
                _col_row(column="EMAIL"),
                _col_row(column="SSN"),
                _col_row(column="PHONE"),
            ),
            policy_refs=(_policy_row(column="EMAIL", kind="MASKING_POLICY"),),
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1

    def test_rule_id(self):
        assert NoRowPolicyOnSensitiveTableCheck().id == "GOV_032"


# ---------------------------------------------------------------------------
# GOV_033 — OverPermissiveSensitiveAccessCheck
# ---------------------------------------------------------------------------


class TestOverPermissiveSensitiveAccessCheck:
    def test_scan_context_none_returns_empty(self):
        rule = OverPermissiveSensitiveAccessCheck()
        assert rule.check_online(_no_cursor(), scan_context=None) == []

    def test_no_sensitive_columns_no_violations(self):
        rule = OverPermissiveSensitiveAccessCheck()
        ctx = _ctx(columns=(_col_row(column="NOTES"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_few_roles_no_violation(self):
        # Default threshold=10; 3 roles → no violation
        rule = OverPermissiveSensitiveAccessCheck()
        gtr = tuple(_gtr_select(role=f"ROLE_{i}", table_name="USERS", catalog="MYDB") for i in range(3))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),), gtr=gtr)
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_too_many_roles_flagged(self):
        # 11 distinct roles > threshold=10
        rule = OverPermissiveSensitiveAccessCheck()
        gtr = tuple(_gtr_select(role=f"ROLE_{i}", table_name="USERS", catalog="MYDB") for i in range(11))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),), gtr=gtr)
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1
        assert "11" in result[0].message

    def test_non_select_grants_ignored(self):
        rule = OverPermissiveSensitiveAccessCheck()
        gtr = tuple(_gtr_other(role=f"ROLE_{i}", table_name="USERS", catalog="MYDB", priv="INSERT") for i in range(15))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),), gtr=gtr)
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_non_sensitive_table_not_flagged(self):
        rule = OverPermissiveSensitiveAccessCheck()
        gtr = tuple(_gtr_select(role=f"ROLE_{i}", table_name="AUDIT_LOG", catalog="MYDB") for i in range(15))
        ctx = _ctx(
            # Sensitive table is USERS, grants are on AUDIT_LOG
            columns=(_col_row(table="USERS", column="EMAIL"),),
            gtr=gtr,
        )
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_custom_threshold_respected(self):
        thresholds = SensitiveDataThresholds(max_roles_accessing_sensitive_table=3)
        rule = OverPermissiveSensitiveAccessCheck(conventions=_conventions(thresholds))
        gtr = tuple(_gtr_select(role=f"ROLE_{i}", table_name="USERS", catalog="MYDB") for i in range(4))
        ctx = _ctx(columns=(_col_row(column="EMAIL"),), gtr=gtr)
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert len(result) == 1

    def test_duplicate_role_grants_counted_once(self):
        # Same role granted twice → still counts as 1 role
        thresholds = SensitiveDataThresholds(max_roles_accessing_sensitive_table=1)
        rule = OverPermissiveSensitiveAccessCheck(conventions=_conventions(thresholds))
        gtr = (
            _gtr_select(role="ANALYST", table_name="USERS", catalog="MYDB"),
            _gtr_select(role="ANALYST", table_name="USERS", catalog="MYDB"),
        )
        ctx = _ctx(columns=(_col_row(column="EMAIL"),), gtr=gtr)
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []  # 1 distinct role ≤ threshold=1

    def test_rule_id(self):
        assert OverPermissiveSensitiveAccessCheck().id == "GOV_033"


# ---------------------------------------------------------------------------
# GOV_034 — ContentPiiDetectionCheck
# ---------------------------------------------------------------------------


class TestContentPiiDetectionCheck:
    def test_scan_context_none_returns_empty(self):
        rule = ContentPiiDetectionCheck()
        assert rule.check_online(_no_cursor(), scan_context=None) == []

    def test_disabled_by_default(self):
        # enable_content_sampling=False → returns [] without touching cursor
        rule = ContentPiiDetectionCheck()
        ctx = _ctx(columns=(_col_row(column="NOTES"),))
        result = rule.check_online(_no_cursor(), scan_context=ctx)
        assert result == []

    def test_ssn_content_flagged_when_enabled(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=10)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="NOTES"),))

        cursor = MagicMock()
        cursor.fetchall.return_value = [("123-45-6789",), ("hello",)]
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "PII_SSN" in result[0].message

    def test_email_content_flagged_when_enabled(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=10)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="NOTES"),))

        cursor = MagicMock()
        cursor.fetchall.return_value = [("user@example.com",)]
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "PII_EMAIL" in result[0].message

    def test_no_pii_content_no_violation(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=10)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="NOTES"),))

        cursor = MagicMock()
        cursor.fetchall.return_value = [("just some notes",), ("nothing special",)]
        result = rule.check_online(cursor, scan_context=ctx)
        assert result == []

    def test_cursor_error_per_column_skipped_gracefully(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=10)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="NOTES"),))

        cursor = MagicMock()
        cursor.execute.side_effect = Exception("access denied")
        # Should not raise — column is skipped
        result = rule.check_online(cursor, scan_context=ctx)
        assert result == []

    def test_uses_parameterized_limit(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=42)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(column="NOTES"),))

        cursor = MagicMock()
        cursor.fetchall.return_value = []
        rule.check_online(cursor, scan_context=ctx)

        call_args = cursor.execute.call_args
        assert call_args is not None
        # Second arg to execute() should be the parameterized limit tuple
        assert call_args[0][1] == (42,)

    def test_quoted_identifiers_in_sql(self):
        thresholds = SensitiveDataThresholds(enable_content_sampling=True, content_sample_rows=10)
        rule = ContentPiiDetectionCheck(conventions=_conventions(thresholds))
        ctx = _ctx(columns=(_col_row(catalog="MY DB", schema="PUB LIC", table="US ERS", column="EM AIL"),))

        cursor = MagicMock()
        cursor.fetchall.return_value = []
        rule.check_online(cursor, scan_context=ctx)

        sql_used = cursor.execute.call_args[0][0]
        # All parts should be enclosed in double-quotes
        assert '"MY DB"' in sql_used
        assert '"PUB LIC"' in sql_used
        assert '"US ERS"' in sql_used
        assert '"EM AIL"' in sql_used

    def test_rule_id(self):
        assert ContentPiiDetectionCheck().id == "GOV_034"


# ---------------------------------------------------------------------------
# Cross-cutting: regex precompiled at init
# ---------------------------------------------------------------------------


class TestRegexPrecompilation:
    def test_compiled_patterns_set_at_init(self):
        import re

        rule = UnmaskedSensitiveColumnsCheck()
        assert hasattr(rule, "_compiled_patterns")
        assert all(isinstance(pat, re.Pattern) for pat, _cat in rule._compiled_patterns)

    def test_all_rules_have_compiled_patterns(self):
        rules = [
            UnmaskedSensitiveColumnsCheck(),
            UntaggedSensitiveColumnsCheck(),
            NoRowPolicyOnSensitiveTableCheck(),
            OverPermissiveSensitiveAccessCheck(),
            ContentPiiDetectionCheck(),
        ]
        for rule in rules:
            assert hasattr(rule, "_compiled_patterns"), f"{rule.id} missing _compiled_patterns"
            assert len(rule._compiled_patterns) > 0


# ---------------------------------------------------------------------------
# Conventions: ColumnPatternDef + SensitiveDataThresholds
# ---------------------------------------------------------------------------


class TestSensitiveDataConventions:
    def test_column_pattern_def_frozen(self):
        cpd = ColumnPatternDef(pattern=r"foo", category="BAR")
        with pytest.raises((AttributeError, TypeError)):
            cpd.pattern = "changed"  # type: ignore[misc]

    def test_sensitive_data_thresholds_defaults(self):
        t = SensitiveDataThresholds()
        assert t.min_sensitive_columns_unmasked == 1
        assert t.min_sensitive_columns_untagged == 1
        assert t.min_sensitive_columns_no_row_policy == 3
        assert t.max_roles_accessing_sensitive_table == 10
        assert t.enable_content_sampling is False
        assert t.content_sample_rows == 100
        assert len(t.column_patterns) == 10

    def test_sensitive_data_thresholds_in_conventions(self):
        from snowfort_audit.domain.conventions import RuleThresholdConventions

        rtc = RuleThresholdConventions()
        assert isinstance(rtc.sensitive_data, SensitiveDataThresholds)
