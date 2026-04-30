"""Directive D — Sensitive Data Detection rules.

GOV_030  Unmasked Sensitive Columns     — PII/PCI columns with no masking policy
GOV_031  Untagged Sensitive Columns     — PII/PCI columns with no sensitivity tag
GOV_032  No Row Policy on Sensitive Tables — tables with ≥N sensitive cols, no RAP
GOV_033  Over-Permissive Sensitive Access — too many roles SELECT on sensitive table
GOV_034  Content-Based PII Detection    — opt-in sampling for PII values in columns
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import SensitiveDataThresholds, SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.rules._grants import (
    GRANTS_CACHE_WINDOW,
    GTR_GRANTED_ON,
    GTR_GRANTEE_NAME,
    GTR_NAME,
    GTR_PRIVILEGE,
    GTR_TABLE_CATALOG,
    gtr_fetcher,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import Row, ScanContext


# ---------------------------------------------------------------------------
# Cache key windows
# ---------------------------------------------------------------------------

_STATIC_WINDOW = 0  # no time filter — fetch all active (non-deleted) rows
_ACCESS_WINDOW = 7  # 7-day lookback for ACCESS_HISTORY

# ---------------------------------------------------------------------------
# Named column indices for ACCOUNT_USAGE.COLUMNS
# SQL: SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
# ---------------------------------------------------------------------------
COL_TABLE_CATALOG = 0
COL_TABLE_SCHEMA = 1
COL_TABLE_NAME = 2
COL_COLUMN_NAME = 3
COL_DATA_TYPE = 4

# ---------------------------------------------------------------------------
# Named column indices for ACCOUNT_USAGE.POLICY_REFERENCES
# SQL: SELECT REF_DATABASE_NAME, REF_SCHEMA_NAME, REF_ENTITY_NAME,
#             REF_COLUMN_NAME, POLICY_KIND
# ---------------------------------------------------------------------------
PR_REF_DATABASE = 0
PR_REF_SCHEMA = 1
PR_REF_ENTITY_NAME = 2
PR_REF_COLUMN_NAME = 3
PR_POLICY_KIND = 4

# ---------------------------------------------------------------------------
# Named column indices for TAG_REFERENCES filtered to COLUMN domain
# SQL: SELECT OBJECT_DATABASE, OBJECT_SCHEMA, OBJECT_NAME,
#             COLUMN_NAME, TAG_NAME, TAG_VALUE
# ---------------------------------------------------------------------------
TRC_OBJECT_DATABASE = 0
TRC_OBJECT_SCHEMA = 1
TRC_OBJECT_NAME = 2
TRC_COLUMN_NAME = 3
TRC_TAG_NAME = 4
TRC_TAG_VALUE = 5

# ---------------------------------------------------------------------------
# Content-level PII patterns for GOV_034 (compiled at module import time).
# These check actual data VALUES, not column names.
# ---------------------------------------------------------------------------
_CONTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "PII_SSN"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "PII_EMAIL"),
    (re.compile(r"\b(?:\d[ \-]?){13,16}\b"), "PCI_CARD"),
]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _default_sd(conventions: SnowfortConventions | None) -> SensitiveDataThresholds:
    """Return SensitiveDataThresholds from conventions, or defaults."""
    if conventions is None:
        return SensitiveDataThresholds()
    return conventions.thresholds.sensitive_data


# ---------------------------------------------------------------------------
# Fetchers (get_or_fetch-compatible closures)
# ---------------------------------------------------------------------------


def _columns_fetcher(cursor: "SnowflakeCursorProtocol"):
    """Fetcher for ACCOUNT_USAGE.COLUMNS — all active columns."""

    def _fetch(_view: str, _window: int) -> "tuple[Row, ...]":
        cursor.execute(
            "SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS"
            " WHERE DELETED IS NULL"
        )
        return tuple(cursor.fetchall())

    return _fetch


def _policy_refs_fetcher(cursor: "SnowflakeCursorProtocol"):
    """Fetcher for ACCOUNT_USAGE.POLICY_REFERENCES — all active policy attachments."""

    def _fetch(_view: str, _window: int) -> "tuple[Row, ...]":
        cursor.execute(
            "SELECT REF_DATABASE_NAME, REF_SCHEMA_NAME, REF_ENTITY_NAME,"
            " REF_COLUMN_NAME, POLICY_KIND"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES"
            " WHERE DELETED IS NULL"
        )
        return tuple(cursor.fetchall())

    return _fetch


def _tag_refs_columns_fetcher(cursor: "SnowflakeCursorProtocol"):
    """Fetcher for TAG_REFERENCES restricted to the COLUMN domain.

    Uses a dedicated cache key ("ACCOUNT_USAGE.TAG_REFERENCES_COLUMNS") so that
    it is fetched separately from the pre-built tag_refs_index (which maps at
    table/object level and does not distinguish individual columns).
    """

    def _fetch(_view: str, _window: int) -> "tuple[Row, ...]":
        cursor.execute(
            "SELECT OBJECT_DATABASE, OBJECT_SCHEMA, OBJECT_NAME,"
            " COLUMN_NAME, TAG_NAME, TAG_VALUE"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES"
            " WHERE DOMAIN = 'COLUMN' AND OBJECT_DELETED IS NULL"
        )
        return tuple(cursor.fetchall())

    return _fetch


# ---------------------------------------------------------------------------
# Shared computation helpers
# ---------------------------------------------------------------------------


def _build_sensitive_cols(
    columns: "tuple[Row, ...]",
    compiled: "list[tuple[re.Pattern[str], str]]",
) -> "list[tuple[str, str, str, str, str]]":
    """Return (catalog, schema, table, column, category) for each sensitive column.

    Only the first matching pattern per column wins (patterns are ordered by
    specificity in SensitiveDataThresholds.column_patterns).
    """
    results: list[tuple[str, str, str, str, str]] = []
    for row in columns:
        col_name = str(row[COL_COLUMN_NAME])
        for pattern, category in compiled:
            if pattern.search(col_name):
                results.append(
                    (
                        str(row[COL_TABLE_CATALOG]),
                        str(row[COL_TABLE_SCHEMA]),
                        str(row[COL_TABLE_NAME]),
                        col_name,
                        category,
                    )
                )
                break
    return results


def _masked_col_keys(
    policy_refs: "tuple[Row, ...]",
) -> "frozenset[tuple[str, str, str, str]]":
    """Return (db, schema, table, column) keys for columns with a masking policy."""
    return frozenset(
        (
            str(row[PR_REF_DATABASE]).upper(),
            str(row[PR_REF_SCHEMA]).upper(),
            str(row[PR_REF_ENTITY_NAME]).upper(),
            str(row[PR_REF_COLUMN_NAME]).upper(),
        )
        for row in policy_refs
        if row[PR_REF_COLUMN_NAME] is not None and "MASKING" in str(row[PR_POLICY_KIND]).upper()
    )


def _row_policy_table_keys(
    policy_refs: "tuple[Row, ...]",
) -> "frozenset[tuple[str, str, str]]":
    """Return (db, schema, table) keys for tables that have a row-access policy."""
    return frozenset(
        (
            str(row[PR_REF_DATABASE]).upper(),
            str(row[PR_REF_SCHEMA]).upper(),
            str(row[PR_REF_ENTITY_NAME]).upper(),
        )
        for row in policy_refs
        if row[PR_REF_COLUMN_NAME] is None and "ROW" in str(row[PR_POLICY_KIND]).upper()
    )


def _tagged_col_keys(
    tag_refs: "tuple[Row, ...]",
) -> "frozenset[tuple[str, str, str, str]]":
    """Return (db, schema, table, column) keys for columns that have any tag."""
    return frozenset(
        (
            str(row[TRC_OBJECT_DATABASE]).upper(),
            str(row[TRC_OBJECT_SCHEMA]).upper(),
            str(row[TRC_OBJECT_NAME]).upper(),
            str(row[TRC_COLUMN_NAME]).upper(),
        )
        for row in tag_refs
    )


# ---------------------------------------------------------------------------
# Shared rule base
# ---------------------------------------------------------------------------


class _SensitiveDataBase(Rule):
    """Base class for GOV_030–034. Compiles column-name patterns at init time."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        severity: Severity,
        rationale: str,
        remediation: str,
        remediation_key: str,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            rule_id,
            name,
            severity,
            telemetry=telemetry,
            rationale=rationale,
            remediation=remediation,
            remediation_key=remediation_key,
        )
        self._thresholds = _default_sd(conventions)
        # Compile column-name patterns once at init — never inside check_online.
        self._compiled_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(p.pattern), p.category) for p in self._thresholds.column_patterns
        ]


# ---------------------------------------------------------------------------
# GOV_030 — Unmasked Sensitive Columns
# ---------------------------------------------------------------------------


class UnmaskedSensitiveColumnsCheck(_SensitiveDataBase):
    """GOV_030: Sensitive columns that have no masking policy applied."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "GOV_030",
            "Unmasked Sensitive Columns",
            Severity.HIGH,
            rationale=(
                "Columns containing PII or PCI data without a masking policy expose raw values "
                "to any role with SELECT access. Masking policies enforce data protection at the "
                "platform layer, independent of upstream access controls."
            ),
            remediation=(
                "Apply a masking policy to each flagged column: "
                "ALTER TABLE <t> ALTER COLUMN <c> SET MASKING POLICY <policy>."
            ),
            remediation_key="APPLY_MASKING_POLICY",
            conventions=conventions,
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        if scan_context is None:
            return []
        try:
            columns = scan_context.get_or_fetch("ACCOUNT_USAGE.COLUMNS", _STATIC_WINDOW, _columns_fetcher(cursor))
            policy_refs = scan_context.get_or_fetch(
                "ACCOUNT_USAGE.POLICY_REFERENCES", _STATIC_WINDOW, _policy_refs_fetcher(cursor)
            )
            sensitive = _build_sensitive_cols(columns, self._compiled_patterns)
            masked = _masked_col_keys(policy_refs)
            min_threshold = self._thresholds.min_sensitive_columns_unmasked

            # Group unmasked cols by table; only flag tables meeting the threshold.
            table_unmasked: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
            for catalog, schema, table, col, category in sensitive:
                key = (catalog.upper(), schema.upper(), table.upper())
                col_key = (*key, col.upper())
                if col_key not in masked:
                    table_unmasked[key].append((col, category))

            violations: list[Violation] = []
            for (catalog, schema, table), cols in table_unmasked.items():
                if len(cols) < min_threshold:
                    continue
                for col, category in cols:
                    fqn = f"{catalog}.{schema}.{table}.{col}"
                    violations.append(
                        self.violation(
                            fqn,
                            f"Sensitive column '{col}' (category: {category}) in "
                            f"{catalog}.{schema}.{table} has no masking policy.",
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# GOV_031 — Untagged Sensitive Columns
# ---------------------------------------------------------------------------


class UntaggedSensitiveColumnsCheck(_SensitiveDataBase):
    """GOV_031: Sensitive columns that have no sensitivity tag applied."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "GOV_031",
            "Untagged Sensitive Columns",
            Severity.MEDIUM,
            rationale=(
                "Tags on sensitive columns enable automated data cataloging, lineage tracking, "
                "and tag-based masking policies. Untagged PII/PCI columns are invisible to "
                "governance tooling and may be missed by downstream policy enforcement."
            ),
            remediation=(
                "Apply a sensitivity tag to each flagged column: "
                "ALTER TABLE <t> ALTER COLUMN <c> SET TAG <tag> = '<value>'."
            ),
            remediation_key="APPLY_SENSITIVITY_TAG",
            conventions=conventions,
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        if scan_context is None:
            return []
        try:
            columns = scan_context.get_or_fetch("ACCOUNT_USAGE.COLUMNS", _STATIC_WINDOW, _columns_fetcher(cursor))
            tag_refs = scan_context.get_or_fetch(
                "ACCOUNT_USAGE.TAG_REFERENCES_COLUMNS",
                _STATIC_WINDOW,
                _tag_refs_columns_fetcher(cursor),
            )
            sensitive = _build_sensitive_cols(columns, self._compiled_patterns)
            tagged = _tagged_col_keys(tag_refs)
            min_threshold = self._thresholds.min_sensitive_columns_untagged

            table_untagged: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
            for catalog, schema, table, col, category in sensitive:
                key = (catalog.upper(), schema.upper(), table.upper())
                col_key = (*key, col.upper())
                if col_key not in tagged:
                    table_untagged[key].append((col, category))

            violations: list[Violation] = []
            for (catalog, schema, table), cols in table_untagged.items():
                if len(cols) < min_threshold:
                    continue
                for col, category in cols:
                    fqn = f"{catalog}.{schema}.{table}.{col}"
                    violations.append(
                        self.violation(
                            fqn,
                            f"Sensitive column '{col}' (category: {category}) in "
                            f"{catalog}.{schema}.{table} has no sensitivity tag.",
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# GOV_032 — No Row-Access Policy on Sensitive Tables
# ---------------------------------------------------------------------------


class NoRowPolicyOnSensitiveTableCheck(_SensitiveDataBase):
    """GOV_032: Sensitive tables with no row-access policy."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "GOV_032",
            "No Row-Access Policy on Sensitive Table",
            Severity.HIGH,
            rationale=(
                "Tables with multiple PII/PCI columns that lack a row-access policy allow "
                "any role with SELECT to read all rows. Row-access policies enforce "
                "record-level filtering based on the querying role or session context."
            ),
            remediation=(
                "Create a row-access policy and attach it to each flagged table: "
                "ALTER TABLE <t> ADD ROW ACCESS POLICY <policy> ON (<col>)."
            ),
            remediation_key="APPLY_ROW_ACCESS_POLICY",
            conventions=conventions,
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        if scan_context is None:
            return []
        try:
            columns = scan_context.get_or_fetch("ACCOUNT_USAGE.COLUMNS", _STATIC_WINDOW, _columns_fetcher(cursor))
            policy_refs = scan_context.get_or_fetch(
                "ACCOUNT_USAGE.POLICY_REFERENCES", _STATIC_WINDOW, _policy_refs_fetcher(cursor)
            )
            sensitive = _build_sensitive_cols(columns, self._compiled_patterns)
            row_protected = _row_policy_table_keys(policy_refs)
            min_threshold = self._thresholds.min_sensitive_columns_no_row_policy

            # Count sensitive columns per table.
            table_counts: dict[tuple[str, str, str], int] = defaultdict(int)
            for catalog, schema, table, _col, _cat in sensitive:
                table_counts[(catalog.upper(), schema.upper(), table.upper())] += 1

            violations: list[Violation] = []
            for (catalog, schema, table), count in table_counts.items():
                if count < min_threshold:
                    continue
                if (catalog, schema, table) in row_protected:
                    continue
                fqn = f"{catalog}.{schema}.{table}"
                violations.append(
                    self.violation(
                        fqn,
                        f"Table {fqn} has {count} sensitive column(s) but no row-access policy.",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# GOV_033 — Over-Permissive Access to Sensitive Tables
# ---------------------------------------------------------------------------


class OverPermissiveSensitiveAccessCheck(_SensitiveDataBase):
    """GOV_033: Too many roles have SELECT access on a sensitive table."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "GOV_033",
            "Over-Permissive Sensitive Table Access",
            Severity.MEDIUM,
            rationale=(
                "A high number of roles with direct SELECT access on a sensitive table "
                "increases the risk of accidental or malicious data exposure. Sensitive "
                "data should be accessed through a small set of purpose-built roles."
            ),
            remediation=(
                "Revoke direct SELECT grants from roles that don't require raw access. "
                "Use views or dynamic data masking to provide least-privilege access."
            ),
            remediation_key="RESTRICT_SENSITIVE_ACCESS",
            conventions=conventions,
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        if scan_context is None:
            return []
        try:
            columns = scan_context.get_or_fetch("ACCOUNT_USAGE.COLUMNS", _STATIC_WINDOW, _columns_fetcher(cursor))
            gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
            sensitive = _build_sensitive_cols(columns, self._compiled_patterns)
            max_roles = self._thresholds.max_roles_accessing_sensitive_table

            # Build set of (catalog, table_name) pairs that are sensitive.
            # GTR does not include schema, so matching is on (catalog, table_name).
            sensitive_tables: set[tuple[str, str]] = {
                (catalog.upper(), table.upper()) for catalog, _schema, table, _col, _cat in sensitive
            }

            # Count distinct roles with SELECT on each sensitive (catalog, table) pair.
            table_roles: dict[tuple[str, str], set[str]] = defaultdict(set)
            for row in gtr:
                priv = str(row[GTR_PRIVILEGE]).upper()
                granted_on = str(row[GTR_GRANTED_ON]).upper()
                if priv != "SELECT" or granted_on not in ("TABLE", "VIEW"):
                    continue
                t_key = (
                    str(row[GTR_TABLE_CATALOG]).upper(),
                    str(row[GTR_NAME]).upper(),
                )
                if t_key in sensitive_tables:
                    table_roles[t_key].add(str(row[GTR_GRANTEE_NAME]).upper())

            violations: list[Violation] = []
            for (catalog, table), roles in table_roles.items():
                if len(roles) > max_roles:
                    violations.append(
                        self.violation(
                            f"{catalog}.{table}",
                            f"Sensitive table {catalog}.{table} is accessible by {len(roles)} "
                            f"roles (threshold: {max_roles}). Roles: "
                            + ", ".join(sorted(roles)[:10])
                            + ("..." if len(roles) > 10 else "."),
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# GOV_034 — Content-Based PII Detection (opt-in)
# ---------------------------------------------------------------------------


class ContentPiiDetectionCheck(_SensitiveDataBase):
    """GOV_034: Opt-in sampling of column values for PII content patterns.

    Disabled by default (enable_content_sampling=False).  When enabled, samples
    up to ``content_sample_rows`` distinct values from each candidate column and
    checks them against known PII content patterns (SSN, email, credit card).
    Uses fully-quoted identifiers and a parameterised LIMIT to prevent injection.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "GOV_034",
            "Content-Based PII Detection",
            Severity.HIGH,
            rationale=(
                "Column names alone cannot detect mis-stored PII (e.g. SSNs in a 'notes' "
                "column). Content sampling provides a second layer of detection for "
                "sensitive data that bypasses name-based classification."
            ),
            remediation=(
                "Classify the flagged column, apply a masking policy, and investigate "
                "whether PII is stored in an unexpected location."
            ),
            remediation_key="INVESTIGATE_PII_CONTENT",
            conventions=conventions,
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        if scan_context is None:
            return []
        if not self._thresholds.enable_content_sampling:
            return []
        try:
            columns = scan_context.get_or_fetch("ACCOUNT_USAGE.COLUMNS", _STATIC_WINDOW, _columns_fetcher(cursor))
            sample_limit = self._thresholds.content_sample_rows
            violations: list[Violation] = []

            for row in columns:
                catalog = str(row[COL_TABLE_CATALOG])
                schema = str(row[COL_TABLE_SCHEMA])
                table = str(row[COL_TABLE_NAME])
                col = str(row[COL_COLUMN_NAME])

                # Use fully-quoted identifiers to prevent identifier injection.
                # LIMIT uses %s parameter — never string-interpolated user data.
                sql = ('SELECT DISTINCT "{col}" FROM "{cat}"."{sch}"."{tbl}" LIMIT %s').format(
                    col=col.replace('"', '""'),
                    cat=catalog.replace('"', '""'),
                    sch=schema.replace('"', '""'),
                    tbl=table.replace('"', '""'),
                )
                try:
                    cursor.execute(sql, (sample_limit,))
                    sample_rows = cursor.fetchall()
                except Exception:  # noqa: BLE001 — skip unqueryable columns gracefully
                    continue

                matched_categories: set[str] = set()
                for sample_row in sample_rows:
                    value = str(sample_row[0]) if sample_row[0] is not None else ""
                    for pattern, category in _CONTENT_PATTERNS:
                        if pattern.search(value):
                            matched_categories.add(category)

                for category in sorted(matched_categories):
                    fqn = f"{catalog}.{schema}.{table}.{col}"
                    violations.append(
                        self.violation(
                            fqn,
                            f"Column '{col}' in {catalog}.{schema}.{table} contains values "
                            f"matching {category} pattern. Review and apply masking policy.",
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
