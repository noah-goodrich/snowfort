"""Regression tests: rule SQL queries must not reference deprecated ACCOUNT_USAGE columns.

Each test captures the SQL string(s) executed by a rule against a mock cursor and
validates them against DEPRECATED_COLUMNS in the schema fixture. A test failure means
the rule still references a column name that was found to be wrong in a live Snowflake
account (bugs fixed in commit 5167e00).

Helper contract:
  assert_no_deprecated_cols(sql, view_name) — raises AssertionError if the SQL
  contains any word that appears in DEPRECATED_COLUMNS[view_name]. View names are
  bare (no "SNOWFLAKE.ACCOUNT_USAGE." prefix) to keep tests readable.
"""

import re
from unittest.mock import MagicMock

from tests.unit.fixtures.account_usage_schema import CORTEX_USAGE_VIEWS, DEPRECATED_COLUMNS


def _capture_sqls(mock_cursor) -> list[str]:
    """Return all SQL strings passed to cursor.execute() during the test."""
    return [call[0][0] for call in mock_cursor.execute.call_args_list if call[0]]


def assert_no_deprecated_cols(sql: str, view: str) -> None:
    """Assert sql contains no word-boundary match for any deprecated column of view."""
    deprecated = DEPRECATED_COLUMNS.get(view, frozenset())
    sql_upper = sql.upper()
    hits = {col for col in deprecated if re.search(rf"\b{col}\b", sql_upper)}
    assert not hits, (
        f"SQL for {view} references deprecated column(s) {hits}.\n"
        f"Fix: update the query to use the correct column name per ACCOUNT_USAGE_SCHEMA."
    )


# ---------------------------------------------------------------------------
# COST_002 — ZombieWarehouseCheck
# Bug: WHERE START_TIME → WHERE TIMESTAMP in WAREHOUSE_EVENTS_HISTORY
# ---------------------------------------------------------------------------


def test_cost002_warehouse_events_history_uses_timestamp():
    """ZombieWarehouseCheck uses TIMESTAMP (not START_TIME) in WAREHOUSE_EVENTS_HISTORY."""
    from snowfort_audit.domain.rules.cost import ZombieWarehouseCheck

    c = MagicMock()
    c.fetchall.side_effect = [[], []]
    ZombieWarehouseCheck().check_online(c)
    sqls = _capture_sqls(c)
    weh_sql = next((s for s in sqls if "WAREHOUSE_EVENTS_HISTORY" in s.upper()), None)
    assert weh_sql is not None, "Expected SQL against WAREHOUSE_EVENTS_HISTORY"
    assert_no_deprecated_cols(weh_sql, "WAREHOUSE_EVENTS_HISTORY")
    assert re.search(r"\bTIMESTAMP\b", weh_sql.upper()), "WHERE clause must reference TIMESTAMP"


# ---------------------------------------------------------------------------
# REL_009 — DynamicTableRefreshLagCheck
# Bug: TABLE_CATALOG, TABLE_SCHEMA → DATABASE_NAME, SCHEMA_NAME
# ---------------------------------------------------------------------------


def test_rel009_dynamic_table_lag_uses_database_name():
    """DynamicTableRefreshLagCheck uses DATABASE_NAME/SCHEMA_NAME (not TABLE_CATALOG/TABLE_SCHEMA)."""
    from snowfort_audit.domain.rules.reliability import DynamicTableRefreshLagCheck

    c = MagicMock()
    c.fetchall.return_value = []
    DynamicTableRefreshLagCheck().check_online(c)
    sqls = _capture_sqls(c)
    dt_sql = next((s for s in sqls if "DYNAMIC_TABLE_REFRESH_HISTORY" in s.upper()), None)
    assert dt_sql is not None, "Expected SQL against DYNAMIC_TABLE_REFRESH_HISTORY"
    assert_no_deprecated_cols(dt_sql, "DYNAMIC_TABLE_REFRESH_HISTORY")
    assert re.search(r"\bDATABASE_NAME\b", dt_sql.upper()), "Must use DATABASE_NAME"
    assert re.search(r"\bSCHEMA_NAME\b", dt_sql.upper()), "Must use SCHEMA_NAME"


# ---------------------------------------------------------------------------
# REL_010 — DynamicTableFailureDetectionCheck
# Bug: TABLE_CATALOG, TABLE_SCHEMA, ERROR_MESSAGE → DATABASE_NAME, SCHEMA_NAME, STATE_MESSAGE
# ---------------------------------------------------------------------------


def test_rel010_dynamic_table_failure_uses_state_message():
    """DynamicTableFailureDetectionCheck uses STATE_MESSAGE (not ERROR_MESSAGE)."""
    from snowfort_audit.domain.rules.reliability import DynamicTableFailureDetectionCheck

    c = MagicMock()
    c.fetchall.return_value = []
    DynamicTableFailureDetectionCheck().check_online(c)
    sqls = _capture_sqls(c)
    dt_sql = next((s for s in sqls if "DYNAMIC_TABLE_REFRESH_HISTORY" in s.upper()), None)
    assert dt_sql is not None, "Expected SQL against DYNAMIC_TABLE_REFRESH_HISTORY"
    assert_no_deprecated_cols(dt_sql, "DYNAMIC_TABLE_REFRESH_HISTORY")
    assert re.search(r"\bSTATE_MESSAGE\b", dt_sql.upper()), "Must use STATE_MESSAGE"


# ---------------------------------------------------------------------------
# GOV_006 — InboundShareRiskCheck
# Bug: queried SHARES → now queries DATABASES with TYPE = 'IMPORTED DATABASE'
# ---------------------------------------------------------------------------


def test_gov006_inbound_share_queries_databases_not_shares():
    """InboundShareRiskCheck queries ACCOUNT_USAGE.DATABASES (not SHARES)."""
    from snowfort_audit.domain.rules.governance import InboundShareRiskCheck

    c = MagicMock()
    c.fetchall.return_value = []
    InboundShareRiskCheck().check_online(c)
    sqls = _capture_sqls(c)
    db_sql = next((s for s in sqls if "ACCOUNT_USAGE.DATABASES" in s.upper()), None)
    assert db_sql is not None, "Expected SQL against ACCOUNT_USAGE.DATABASES"
    assert re.search(r"TYPE\s*=\s*'IMPORTED DATABASE'", db_sql, re.IGNORECASE), (
        "Must filter with TYPE = 'IMPORTED DATABASE'"
    )
    assert "ACCOUNT_USAGE.SHARES" not in db_sql.upper(), "Must not query ACCOUNT_USAGE.SHARES"


# ---------------------------------------------------------------------------
# GOV_007 — OutboundShareRiskCheck
# Bug: SHARE_NAME → NAME, DELETED → DELETED_ON in ACCOUNT_USAGE.SHARES
# ---------------------------------------------------------------------------


def test_gov007_outbound_share_uses_name_and_deleted_on():
    """OutboundShareRiskCheck uses NAME and DELETED_ON (not SHARE_NAME or DELETED)."""
    from snowfort_audit.domain.rules.governance import OutboundShareRiskCheck

    c = MagicMock()
    c.fetchall.return_value = []
    OutboundShareRiskCheck().check_online(c)
    sqls = _capture_sqls(c)
    shares_sql = next((s for s in sqls if "ACCOUNT_USAGE.SHARES" in s.upper()), None)
    assert shares_sql is not None, "Expected SQL against ACCOUNT_USAGE.SHARES"
    assert_no_deprecated_cols(shares_sql, "SHARES")
    assert re.search(r"\bDELETED_ON\b", shares_sql.upper()), "Must use DELETED_ON"


# ---------------------------------------------------------------------------
# SEC_021 — TrustCenterExtensionsCheck
# Bug: FINDING_TYPE, STATUS → SCANNER_NAME, STATE in TRUST_CENTER.FINDINGS
# ---------------------------------------------------------------------------


def test_sec021_trust_center_uses_scanner_name_and_state():
    """TrustCenterExtensionsCheck uses SCANNER_NAME and STATE (not FINDING_TYPE/STATUS)."""
    from snowfort_audit.domain.rules.security_advanced import TrustCenterExtensionsCheck

    c = MagicMock()
    c.fetchall.return_value = []
    TrustCenterExtensionsCheck().check_online(c)
    sqls = _capture_sqls(c)
    tc_sql = next((s for s in sqls if "TRUST_CENTER" in s.upper()), None)
    assert tc_sql is not None, "Expected SQL against TRUST_CENTER.FINDINGS"
    assert_no_deprecated_cols(tc_sql, "TRUST_CENTER.FINDINGS")
    assert re.search(r"\bSCANNER_NAME\b", tc_sql.upper()), "Must use SCANNER_NAME"
    assert re.search(r"\bSTATE\b", tc_sql.upper()), "Must use STATE"


# ---------------------------------------------------------------------------
# Cortex rules — _CortexRule base class
# Bug: TIME_COL default was USAGE_TIME → should be START_TIME
# CORTEX_SEARCH_DAILY_USAGE_HISTORY is the exception (USAGE_DATE)
# ---------------------------------------------------------------------------


def test_cortex_base_class_time_col_default_is_start_time():
    """_CortexRule.TIME_COL defaults to START_TIME (not USAGE_TIME)."""
    from snowfort_audit.domain.rules.cortex_cost import _CortexRule

    assert _CortexRule.TIME_COL == "START_TIME"


def test_cortex_fetcher_uses_start_time_in_sql():
    """_cortex_fetcher builds SQL using START_TIME (not USAGE_TIME) for standard views."""
    from snowfort_audit.domain.rules.cortex_cost import _cortex_fetcher

    c = MagicMock()
    c.fetchall.return_value = []
    fetcher = _cortex_fetcher(c, "CORTEX_AI_FUNCTIONS_USAGE_HISTORY")
    fetcher("CORTEX_AI_FUNCTIONS_USAGE_HISTORY", 30)
    sql = c.execute.call_args_list[0][0][0]
    assert_no_deprecated_cols(sql, "CORTEX_AI_FUNCTIONS_USAGE_HISTORY")
    assert re.search(r"\bSTART_TIME\b", sql.upper()), "Must use START_TIME"


def test_cortex_search_uses_usage_date():
    """CORTEX_SEARCH_DAILY_USAGE_HISTORY uses USAGE_DATE (its correct time column)."""
    from snowfort_audit.domain.rules.cortex_cost import (
        CortexSearchConsumptionBreakdownCheck,
        CortexSearchZombieServiceCheck,
    )

    expected = CORTEX_USAGE_VIEWS["CORTEX_SEARCH_DAILY_USAGE_HISTORY"]
    assert CortexSearchConsumptionBreakdownCheck.TIME_COL == expected, (
        f"CORTEX_SEARCH_DAILY_USAGE_HISTORY must use {expected!r} as TIME_COL"
    )
    assert CortexSearchZombieServiceCheck.TIME_COL == expected


# ---------------------------------------------------------------------------
# Schema fixture sanity — AC-1
# ---------------------------------------------------------------------------


def test_account_usage_schema_covers_required_views():
    """Fixture covers the 8 views that had bugs plus additional commonly-used views (≥13)."""
    from tests.unit.fixtures.account_usage_schema import ACCOUNT_USAGE_SCHEMA

    required_views = {
        "WAREHOUSE_EVENTS_HISTORY",
        "DYNAMIC_TABLE_REFRESH_HISTORY",
        "DATABASES",
        "SHARES",
        "GRANTS_TO_ROLES",
        "TAG_REFERENCES",
        "TABLES",
        "WAREHOUSE_METERING_HISTORY",
        "WAREHOUSE_LOAD_HISTORY",
        "TABLE_STORAGE_METRICS",
        "QUERY_HISTORY",
        "TASK_HISTORY",
        "GRANTS_TO_USERS",
    }
    missing = required_views - set(ACCOUNT_USAGE_SCHEMA.keys())
    assert not missing, f"Schema fixture missing views: {missing}"
    assert len(ACCOUNT_USAGE_SCHEMA) >= 13


def test_deprecated_columns_not_in_valid_schema():
    """Deprecated columns (for most views) should not appear in the valid column set."""
    from tests.unit.fixtures.account_usage_schema import ACCOUNT_USAGE_SCHEMA

    # WAREHOUSE_EVENTS_HISTORY: START_TIME was wrong, TIMESTAMP is right
    weh = ACCOUNT_USAGE_SCHEMA["WAREHOUSE_EVENTS_HISTORY"]
    assert "TIMESTAMP" in weh, "TIMESTAMP must be in valid columns for WAREHOUSE_EVENTS_HISTORY"
    assert "START_TIME" not in weh, "START_TIME must NOT be in WAREHOUSE_EVENTS_HISTORY columns"

    # SHARES: NAME is correct, SHARE_NAME is wrong
    shares = ACCOUNT_USAGE_SCHEMA["SHARES"]
    assert "NAME" in shares
    assert "SHARE_NAME" not in shares
    assert "DELETED_ON" in shares

    # DYNAMIC_TABLE_REFRESH_HISTORY: DATABASE_NAME is correct, TABLE_CATALOG is wrong
    dtrf = ACCOUNT_USAGE_SCHEMA["DYNAMIC_TABLE_REFRESH_HISTORY"]
    assert "DATABASE_NAME" in dtrf
    assert "TABLE_CATALOG" not in dtrf
    assert "STATE_MESSAGE" in dtrf
