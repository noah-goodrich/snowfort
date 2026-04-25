"""Fixture ScanContext for snapshot regression testing.

Column indices are intentionally defined via the *_cols dicts so that
the column-name refactor in Session 3 can replace hardcoded indices without
changing the fixture data.  Rules that use cols["name"] and rules that
accidentally use row[0] will produce different results if the name column is
NOT at index 0 — which is the regression we want to catch.

For simplicity, warehouse "name" is at index 1 (not 0) to expose any
hardcoded row[0] access.
"""

from snowfort_audit.domain.scan_context import ScanContext

# ── Warehouse fixture ─────────────────────────────────────────────────────────
# Schema: (created_on, name, state, type, size, auto_suspend, auto_resume,
#          resource_monitor, comment, owner, scaling_policy)
WH_COLS = {
    "created_on": 0,
    "name": 1,
    "state": 2,
    "type": 3,
    "size": 4,
    "auto_suspend": 5,
    "auto_resume": 6,
    "resource_monitor": 7,
    "comment": 8,
    "owner": 9,
    "scaling_policy": 10,
}

_WAREHOUSES = (
    # BAD_COST_WH: auto_suspend=600s, no resource_monitor — should trigger COST_001
    ("2024-01-01", "BAD_COST_WH", "RUNNING", "STANDARD", "LARGE", 600, "true", "null", "", "ACCOUNTADMIN", "STANDARD"),
    # GOOD_WH: properly configured — no violation
    ("2024-01-01", "GOOD_WH", "SUSPENDED", "STANDARD", "SMALL", 60, "true", "MONITOR_1", "Main", "SYSADMIN", "ECONOMY"),
)

# ── User fixture ──────────────────────────────────────────────────────────────
# Schema: (created_on, login_name, name, has_mfa, type, default_role, owner)
USER_COLS = {
    "created_on": 0,
    "login_name": 1,
    "name": 2,
    "has_mfa": 3,
    "type": 4,
    "default_role": 5,
    "owner": 6,
}

_USERS = (
    ("2024-01-01", "ADMIN", "ADMIN", False, None, "ACCOUNTADMIN", "ACCOUNTADMIN"),
    ("2024-01-01", "SVC_MYAPP", "SVC_MYAPP", False, "SERVICE", "APP_ROLE", "SYSADMIN"),
)

# ── Database fixture ──────────────────────────────────────────────────────────
# Schema: (created_on, name, is_default, is_current, origin, owner, comment, retention_time)
DB_COLS = {
    "created_on": 0,
    "name": 1,
    "is_default": 2,
    "is_current": 3,
    "origin": 4,
    "owner": 5,
    "comment": 6,
    "retention_time": 7,
}

_DATABASES = (
    ("2024-01-01", "MY_APP_DB", "N", "N", "", "SYSADMIN", "", 1),
    ("2024-01-01", "SNOWFLAKE", "N", "N", "", "ACCOUNTADMIN", "System", 0),
)

# ── Role fixture ──────────────────────────────────────────────────────────────
# Schema: (created_on, name, is_default, is_current, is_inherited, granted_to_roles,
#          granted_roles, owner, comment)
ROLE_COLS = {
    "created_on": 0,
    "name": 1,
    "is_default": 2,
    "is_current": 3,
    "is_inherited": 4,
    "granted_to_roles": 5,
    "granted_roles": 6,
    "owner": 7,
    "comment": 8,
}

_ROLES = (
    ("2024-01-01", "ORPHAN_ROLE", "N", "N", "N", 0, 0, "ACCOUNTADMIN", ""),
    ("2024-01-01", "APP_ROLE", "N", "N", "N", 1, 2, "SYSADMIN", ""),
)

# ── Tag references fixture ────────────────────────────────────────────────────
# Schema: (DOMAIN, OBJECT_NAME, TAG_NAME, TAG_VALUE, COLUMN_NAME)
_TAG_REFS = (
    ("WAREHOUSE", "GOOD_WH", "ENVIRONMENT", "PRD", None),
    ("WAREHOUSE", "GOOD_WH", "COST_CENTER", "ANALYTICS", None),
    # BAD_COST_WH intentionally has no tags
)

# ── Tables fixture ────────────────────────────────────────────────────────────
# Schema: TABLE_CATALOG=0, TABLE_SCHEMA=1, TABLE_NAME=2, TABLE_TYPE=3,
#         BYTES=4, ROW_COUNT=5, RETENTION_TIME=6,
#         CLUSTERING_KEY=7, COMMENT=8
_TABLES = (
    ("MY_APP_DB", "PUBLIC", "EVENTS", "BASE TABLE", 1024 * 1024 * 500, 1_000_000, 1, None, ""),
    ("MY_APP_DB", "PUBLIC", "USERS", "BASE TABLE", 1024 * 1024 * 10, 50_000, 1, None, ""),
)


def make_fixture_context() -> ScanContext:
    """Return a minimal ScanContext with stable fixture data for snapshot tests.

    The column index for 'name' is NOT 0 for warehouses and users — this ensures
    that rules using hardcoded row[0] are distinguishable from rules using
    cols["name"] during the Session 3 column-name refactor.
    """
    ctx = ScanContext()
    ctx.warehouses = _WAREHOUSES
    ctx.warehouses_cols = WH_COLS
    ctx.users = _USERS
    ctx.users_cols = USER_COLS
    ctx.databases = _DATABASES
    ctx.databases_cols = DB_COLS
    ctx.roles = _ROLES
    ctx.roles_cols = ROLE_COLS
    ctx.tag_refs = _TAG_REFS

    # Build tag_refs_index from fixture tag_refs (same logic as online_scan.py _prefetch)
    idx: dict[tuple[str, str], dict[str, str]] = {}
    for row in _TAG_REFS:
        domain = str(row[0]).upper()
        obj = str(row[1]).upper()
        tag = str(row[2]).upper()
        val = str(row[3]) if row[3] is not None else ""
        key = (domain, obj)
        tags = idx.get(key)
        if tags is None:
            tags = {}
            idx[key] = tags
        tags[tag] = val
    ctx.tag_refs_index = idx

    ctx.tables = _TABLES
    return ctx
