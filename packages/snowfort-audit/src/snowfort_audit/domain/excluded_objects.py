"""Excluded databases and object name prefixes for online scan.

Filter these at the source in rule queries and SHOW result handling so we never
collect violations for Snowflake system or Snowfort tool objects. Use the same
constants in the view-phase list (online_scan) for consistency.

SNOWFORT is excluded by default but can be included via --include-snowfort-db
when auditing the Snowfort project; that toggle is applied in the use case
(view list and post-filter), not in rule SQL.
"""

# Exclude from TABLE_CATALOG / DATABASE_NAME in rule SQL and from SHOW DATABASES/WAREHOUSES iteration.
EXCLUDED_DATABASES_ALWAYS = frozenset(
    (
        "SNOWFLAKE",
        "SNOWFLAKE_SAMPLE_DATA",
    )
)

# Excluded when include_snowfort_db is False (see online_scan); not used in rule SQL so --include-snowfort-db can include it.
EXCLUDED_DATABASES_DEFAULT = EXCLUDED_DATABASES_ALWAYS | frozenset(("SNOWFORT",))

# Object names (e.g. warehouse) that start with these are Snowflake-managed; skip in SHOW results.
SYSTEM_OBJECT_PREFIXES = ("SYSTEM$",)

# SQL fragment for WHERE: AND TABLE_CATALOG NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA')
# Rules that must respect --include-snowfort-db cannot use SNOWFORT here; they rely on post-filter or a future context.
SQL_EXCLUDE_SYSTEM_DATABASES = " AND UPPER(TABLE_CATALOG) NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA')"

# For rules that always exclude SNOWFORT (no override), use:
SQL_EXCLUDE_SYSTEM_AND_SNOWFORT = " AND UPPER(TABLE_CATALOG) NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA', 'SNOWFORT')"


def is_excluded_database(name: str | None, include_snowfort: bool = False) -> bool:
    """True if database name should be excluded from scans (system/tool)."""
    if not name:
        return False
    u = name.strip().upper()
    if u in EXCLUDED_DATABASES_ALWAYS:
        return True
    if not include_snowfort and u == "SNOWFORT":
        return True
    return False


def is_excluded_warehouse_or_object_name(name: str | None) -> bool:
    """True if warehouse/object name is Snowflake-managed (e.g. SYSTEM$*)."""
    if not name:
        return False
    u = name.strip().upper()
    if u in EXCLUDED_DATABASES_ALWAYS or u == "SNOWFORT":
        return True
    return any(u.startswith(p) for p in SYSTEM_OBJECT_PREFIXES)
