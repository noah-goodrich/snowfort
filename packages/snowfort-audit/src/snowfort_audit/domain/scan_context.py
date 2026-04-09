"""ScanContext: pre-fetched shared query results passed to check_online().

Created once before rules run in OnlineScanUseCase; passed to each rule via
check_online(cursor, scan_context=ctx).  Read-only by convention — workers
hold references to the same immutable data.

Named column indices for ACCOUNT_USAGE.TAG_REFERENCES rows (TR_*):
    TR_DOMAIN=0  TR_OBJECT_NAME=1  TR_TAG_NAME=2  TR_TAG_VALUE=3  TR_COLUMN_NAME=4

Named column indices for ACCOUNT_USAGE.TABLES rows (TC_*):
    TC_TABLE_CATALOG=0  TC_TABLE_SCHEMA=1  TC_TABLE_NAME=2  TC_TABLE_TYPE=3
    TC_BYTES=4  TC_ROW_COUNT=5  TC_RETENTION_TIME=6  TC_ENABLE_SCHEMA_EVOLUTION=7
    TC_CLUSTERING_KEY=8  TC_COMMENT=9

For SHOW command data (warehouses, users, databases, roles), use ScanContext.col()
with the corresponding *_cols dict to look up columns by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

Row = tuple[Any, ...]

# ---------------------------------------------------------------------------
# Named column indices for scan_context.tag_refs (ACCOUNT_USAGE.TAG_REFERENCES)
# Use these constants instead of magic integer literals when filtering tag_refs.
# ---------------------------------------------------------------------------
TR_DOMAIN = 0
TR_OBJECT_NAME = 1
TR_TAG_NAME = 2
TR_TAG_VALUE = 3
TR_COLUMN_NAME = 4

# ---------------------------------------------------------------------------
# Named column indices for scan_context.tables (ACCOUNT_USAGE.TABLES)
# Use these constants instead of magic integer literals when filtering tables.
# The SQL fallback queries in each rule always SELECT columns in this order,
# so the constants are valid for both the prefetch path and the cursor path.
# ---------------------------------------------------------------------------
TC_TABLE_CATALOG = 0
TC_TABLE_SCHEMA = 1
TC_TABLE_NAME = 2
TC_TABLE_TYPE = 3
TC_BYTES = 4
TC_ROW_COUNT = 5
TC_RETENTION_TIME = 6
TC_ENABLE_SCHEMA_EVOLUTION = 7
TC_CLUSTERING_KEY = 8
TC_COMMENT = 9


@dataclass
class ScanContext:
    """Pre-fetched shared query results for a scan session."""

    # SHOW WAREHOUSES
    warehouses: tuple[Row, ...] | None = None
    warehouses_cols: dict[str, int] = field(default_factory=dict)
    # SHOW USERS
    users: tuple[Row, ...] | None = None
    users_cols: dict[str, int] = field(default_factory=dict)
    # SHOW DATABASES
    databases: tuple[Row, ...] | None = None
    databases_cols: dict[str, int] = field(default_factory=dict)
    # SHOW ROLES
    roles: tuple[Row, ...] | None = None
    roles_cols: dict[str, int] = field(default_factory=dict)
    # SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES (OBJECT_DELETED IS NULL)
    # cols: DOMAIN=0, OBJECT_NAME=1, TAG_NAME=2, TAG_VALUE=3, COLUMN_NAME=4
    tag_refs: tuple[Row, ...] | None = None
    # Pre-built index: (DOMAIN_UPPER, OBJECT_NAME_UPPER) -> {TAG_NAME_UPPER: TAG_VALUE}
    tag_refs_index: dict[tuple[str, str], dict[str, str]] | None = None
    # SNOWFLAKE.ACCOUNT_USAGE.TABLES (DELETED IS NULL)
    # cols: TABLE_CATALOG=0, TABLE_SCHEMA=1, TABLE_NAME=2, TABLE_TYPE=3,
    #        BYTES=4, ROW_COUNT=5, RETENTION_TIME=6, ENABLE_SCHEMA_EVOLUTION=7,
    #        CLUSTERING_KEY=8, COMMENT=9
    tables: tuple[Row, ...] | None = None
    # Derived SSO detection: True when ≥50% of active human users have ext_authn_uid populated
    # (detected during _prefetch). None means not yet computed.
    sso_enforced: bool | None = None
    # Set of lowercase usernames flagged as zombie (inactive) by ZombieUserCheck during prefetch.
    # Used by FederatedAuthenticationCheck (B6) to skip users already reported elsewhere.
    zombie_user_logins: frozenset[str] | None = None
    # Generalized prefetch cache: (view_name, window_days) -> fetched rows.
    # Populated lazily by get_or_fetch(); shared across all rules in a scan session.
    _fetch_cache: dict[tuple[str, int], tuple[Row, ...]] = field(default_factory=dict, repr=False)

    def get_or_fetch(
        self,
        view: str,
        window_days: int,
        fetcher: Callable[[str, int], tuple[Row, ...]],
    ) -> tuple[Row, ...]:
        """Return cached rows for (view, window_days), fetching once if not cached.

        The fetcher is called exactly once per (view, window_days) pair per scan session.
        Sessions 1b–6 wire their ACCOUNT_USAGE views through this cache so that
        multiple rules hitting the same view incur only one round-trip to Snowflake.

        Args:
            view: ACCOUNT_USAGE view name (e.g. "GRANTS_TO_ROLES").
            window_days: Lookback window in days (used in WHERE clause by the fetcher).
            fetcher: Callable(view, window_days) -> tuple[Row, ...].

        Returns:
            Cached or freshly-fetched rows as a tuple.
        """
        key = (view, window_days)
        if key not in self._fetch_cache:
            self._fetch_cache[key] = fetcher(view, window_days)
        return self._fetch_cache[key]

    def col(self, row: Row, cols: dict[str, int], name: str) -> Any:
        """Return a named column value from a SHOW-command row.

        Provides a self-documenting alternative to magic integer indices for
        data fetched via SHOW commands (warehouses, users, databases, roles),
        where column positions are determined at runtime from cursor.description.

        Args:
            row: A result row tuple from a SHOW command.
            cols: Column-name → index dict (e.g. ``self.warehouses_cols``).
            name: Column name exactly as it appears in the dict keys.

        Returns:
            The column value at the resolved index.

        Example::

            name = ctx.col(wh, ctx.warehouses_cols, "name")
        """
        return row[cols[name]]
