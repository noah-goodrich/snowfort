"""Shared IaC-drift and dbt-grant prefetch helpers.

All rules in the ``iac_drift`` module must use :func:`get_or_fetch` with the
constants defined here so that each view is fetched at most once per scan
session.  QUERY_HISTORY is always aggregated server-side to avoid pulling raw
rows into Python.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import Row

# ---------------------------------------------------------------------------
# Cache keys — different from _grants.py so they don't collide.
# ---------------------------------------------------------------------------
QH_IAC_CACHE_WINDOW = 30  # QUERY_HISTORY lookback in days (matches convention default).
SCHEMA_OWNERS_CACHE_WINDOW = 0  # No time window: current schema owners.

# ---------------------------------------------------------------------------
# Column indices for QH_IAC_SUMMARY rows returned by qh_iac_fetcher.
# SQL: SELECT USER_NAME, TOOL_LABEL, QUERY_COUNT
# ---------------------------------------------------------------------------
QH_USER_NAME = 0
QH_TOOL_LABEL = 1
QH_QUERY_COUNT = 2

# ---------------------------------------------------------------------------
# Column indices for QH_DDL_NON_SVC rows returned by qh_ddl_non_svc_fetcher.
# SQL: SELECT USER_NAME, QUERY_TYPE, DATABASE_NAME, SCHEMA_NAME, QUERY_COUNT
# ---------------------------------------------------------------------------
DDL_USER_NAME = 0
DDL_QUERY_TYPE = 1
DDL_DATABASE_NAME = 2
DDL_SCHEMA_NAME = 3
DDL_QUERY_COUNT = 4

# ---------------------------------------------------------------------------
# Column indices for QH_GRANT_ROWS returned by qh_grant_fetcher.
# SQL: SELECT QUERY_TEXT, USER_NAME
# ---------------------------------------------------------------------------
GR_QUERY_TEXT = 0
GR_USER_NAME = 1

# ---------------------------------------------------------------------------
# Column indices for SCHEMA_OWNERS rows returned by schema_owners_fetcher.
# SQL: SELECT CATALOG_NAME, SCHEMA_NAME, SCHEMA_OWNER
# ---------------------------------------------------------------------------
SO_CATALOG_NAME = 0
SO_SCHEMA_NAME = 1
SO_SCHEMA_OWNER = 2

# MANAGED_BY-like tag names used for IaC tagging (upper-cased for comparison).
MANAGED_BY_TAG_NAMES = frozenset({"MANAGED_BY", "MANAGEMENT", "SOURCE", "TERRAFORM"})


def _sf_regex(pattern: str) -> tuple[str, str]:
    """Convert a Python-style regex to Snowflake REGEXP_LIKE args.

    Strips ``(?i)`` inline flags (unsupported by Snowflake) and returns
    ``(pattern_without_flags, snowflake_flags)`` for use in
    ``REGEXP_LIKE(col, pattern, flags)``.
    """
    flags = ""
    clean = pattern
    if "(?i)" in pattern:
        flags = "i"
        clean = pattern.replace("(?i)", "")
    return clean, flags


def _sf_regexp_like(col: str, pattern: str) -> str:
    """Build a ``REGEXP_LIKE(col, 'pattern', 'flags')`` SQL fragment."""
    clean, flags = _sf_regex(pattern)
    if flags:
        return f"REGEXP_LIKE({col}, '{clean}', '{flags}')"
    return f"REGEXP_LIKE({col}, '{clean}')"


def qh_iac_fetcher(cursor: "SnowflakeCursorProtocol", comment_patterns: tuple[str, ...]):
    """Return a ``get_or_fetch``-compatible fetcher for IaC tool presence in QUERY_HISTORY.

    Aggregates server-side: groups by USER_NAME and detected tool label using
    ``REGEXP_LIKE`` on QUERY_TEXT, so we never pull raw query text into Python.

    Cache key: ``("QUERY_HISTORY_IAC", QH_IAC_CACHE_WINDOW)``.
    """
    # Build a CASE expression that maps each comment pattern to a tool label.
    when_clauses = []
    for pat in comment_patterns:
        # Derive a human-readable label from the regex (e.g., "(?i)terraform" → "TERRAFORM").
        label = re.sub(r"\(\?i\)", "", pat).upper().strip()
        when_clauses.append(f"WHEN {_sf_regexp_like('QUERY_TEXT', pat)} THEN '{label}'")
    case_expr = " ".join(when_clauses) if when_clauses else "WHEN 1=0 THEN 'NONE'"

    or_clauses = [_sf_regexp_like("QUERY_TEXT", p) for p in comment_patterns]
    filter_expr = " OR ".join(or_clauses)

    sql = (
        "SELECT USER_NAME,"
        f" CASE {case_expr} ELSE 'OTHER' END AS TOOL_LABEL,"
        " COUNT(*) AS QUERY_COUNT"
        " FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY"
        " WHERE START_TIME >= DATEADD('day', -%(window)s, CURRENT_TIMESTAMP())"
        " AND QUERY_TEXT IS NOT NULL"
        f" AND ({filter_expr})"
        " GROUP BY USER_NAME, TOOL_LABEL"
    )

    def _fetch(view: str, window: int) -> "tuple[Row, ...]":
        cursor.execute(sql, {"window": window})
        return tuple(cursor.fetchall())

    return _fetch


def qh_ddl_non_svc_fetcher(cursor: "SnowflakeCursorProtocol", svc_pattern: str):
    """Return a fetcher for DDL statements by non-service-account users.

    Used by OPS_016 drift detection: finds DDL changes made by human users
    in the lookback window.  Aggregated server-side.

    Cache key: ``("QUERY_HISTORY_DDL_NON_SVC", QH_IAC_CACHE_WINDOW)``.
    """
    sql = (
        "SELECT USER_NAME, QUERY_TYPE, DATABASE_NAME, SCHEMA_NAME, COUNT(*) AS QUERY_COUNT"
        " FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY"
        " WHERE START_TIME >= DATEADD('day', -%(window)s, CURRENT_TIMESTAMP())"
        " AND QUERY_TYPE IN ('CREATE', 'ALTER', 'DROP', 'CREATE_TABLE', 'ALTER_TABLE_ADD_COLUMN',"
        " 'ALTER_TABLE_DROP_COLUMN', 'CREATE_VIEW', 'ALTER_VIEW', 'GRANT', 'REVOKE')"
        f" AND NOT {_sf_regexp_like('USER_NAME', svc_pattern)}"
        " AND DATABASE_NAME IS NOT NULL"
        " GROUP BY USER_NAME, QUERY_TYPE, DATABASE_NAME, SCHEMA_NAME"
    )

    def _fetch(view: str, window: int) -> "tuple[Row, ...]":
        cursor.execute(sql, {"window": window})
        return tuple(cursor.fetchall())

    return _fetch


def qh_grant_fetcher(cursor: "SnowflakeCursorProtocol", comment_patterns: tuple[str, ...]):
    """Return a fetcher for GRANT statements emitted by dbt (identified by comment pattern).

    Returns individual GRANT QUERY_TEXT rows (limited to GRANT/REVOKE types with dbt
    comment pattern) for GOV_025 to parse grant targets.

    Cache key: ``("QUERY_HISTORY_DBT_GRANTS", QH_IAC_CACHE_WINDOW)``.
    """
    # Use only the dbt comment pattern(s) to filter.
    dbt_patterns = [p for p in comment_patterns if "dbt" in p.lower()]
    if not dbt_patterns:
        dbt_patterns = [r"(?i)dbt"]
    filter_expr = " OR ".join(_sf_regexp_like("QUERY_TEXT", p) for p in dbt_patterns)

    sql = (
        "SELECT QUERY_TEXT, USER_NAME"
        " FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY"
        " WHERE START_TIME >= DATEADD('day', -%(window)s, CURRENT_TIMESTAMP())"
        " AND QUERY_TYPE IN ('GRANT', 'REVOKE')"
        f" AND ({filter_expr})"
        " LIMIT 10000"
    )

    def _fetch(view: str, window: int) -> "tuple[Row, ...]":
        cursor.execute(sql, {"window": window})
        return tuple(cursor.fetchall())

    return _fetch


def schema_owners_fetcher(cursor: "SnowflakeCursorProtocol"):
    """Return a fetcher for schema ownership info from ACCOUNT_USAGE.SCHEMATA.

    Cache key: ``("SCHEMATA_OWNERS", SCHEMA_OWNERS_CACHE_WINDOW)``.
    """
    sql = (
        "SELECT CATALOG_NAME, SCHEMA_NAME, SCHEMA_OWNER"
        " FROM SNOWFLAKE.ACCOUNT_USAGE.SCHEMATA"
        " WHERE DELETED IS NULL"
        " AND SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA', 'PUBLIC')"
        " AND CATALOG_NAME NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA')"
    )

    def _fetch(view: str, window: int) -> "tuple[Row, ...]":
        cursor.execute(sql)
        return tuple(cursor.fetchall())

    return _fetch


# ---------------------------------------------------------------------------
# Graph / analysis helpers
# ---------------------------------------------------------------------------


def detect_iac_tools(
    qh_rows: "tuple[Row, ...]",
    tag_refs_index: dict[tuple[str, str], dict[str, str]] | None,
) -> dict[str, list[str]]:
    """Detect IaC tools present in the account.

    Returns a mapping of tool label → list of evidence strings.  Evidence
    comes from two sources:

    1. QUERY_HISTORY comment patterns (``qh_rows`` from :func:`qh_iac_fetcher`).
    2. MANAGED_BY tags on objects (``tag_refs_index`` from ScanContext).
    """
    tools: dict[str, list[str]] = {}

    # Evidence from QUERY_HISTORY aggregated rows.
    for row in qh_rows:
        label = str(row[QH_TOOL_LABEL])
        if label == "OTHER":
            continue
        user = str(row[QH_USER_NAME])
        count = int(row[QH_QUERY_COUNT])
        tools.setdefault(label, []).append(f"User {user}: {count} queries with {label} comment")

    # Evidence from MANAGED_BY tags.
    if tag_refs_index:
        for (_domain, _obj_name), tags in tag_refs_index.items():
            for tag_name, tag_value in tags.items():
                if tag_name.upper() in MANAGED_BY_TAG_NAMES and tag_value:
                    tool_label = tag_value.upper().strip()
                    tools.setdefault(tool_label, []).append(f"Tag {tag_name}={tag_value} on {_domain}.{_obj_name}")

    return tools


def managed_tag_coverage_by_database(
    tag_refs_index: dict[tuple[str, str], dict[str, str]] | None,
    databases: "tuple[Row, ...] | None",
    databases_cols: dict[str, int] | None,
) -> dict[str, float]:
    """Compute fraction of objects with MANAGED_BY tag per database.

    Returns a mapping of database_name → coverage fraction [0.0, 1.0].
    Only includes databases that have at least one tagged object.
    """
    if not tag_refs_index:
        return {}

    # Count tagged and total objects per database.
    db_tagged: dict[str, int] = {}
    db_total: dict[str, int] = {}

    for (domain, obj_name), tags in tag_refs_index.items():
        # Infer database from the object name (e.g., "MYDB.MYSCHEMA.MYTABLE" → "MYDB").
        parts = obj_name.split(".")
        db_name = parts[0].upper() if parts else "UNKNOWN"
        if db_name in ("SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"):
            continue
        db_total[db_name] = db_total.get(db_name, 0) + 1
        has_managed = any(t.upper() in MANAGED_BY_TAG_NAMES for t in tags)
        if has_managed:
            db_tagged[db_name] = db_tagged.get(db_name, 0) + 1

    coverage: dict[str, float] = {}
    for db_name, total in db_total.items():
        if total > 0:
            coverage[db_name] = db_tagged.get(db_name, 0) / total

    return coverage


def parse_grant_target_role(query_text: str) -> str | None:
    """Extract the target role name from a GRANT ... TO ROLE ... statement.

    Returns the role name (upper-cased) or None if the statement can't be parsed.
    Handles common dbt grant patterns::

        GRANT SELECT ON TABLE ... TO ROLE MY_ROLE;
        GRANT USAGE ON SCHEMA ... TO ROLE MY_ROLE;
    """
    match = re.search(r"(?i)\bTO\s+ROLE\s+([\"']?(\w+)[\"']?)", query_text)
    if match:
        return match.group(2).upper()
    return None
