"""Shared ACCOUNT_USAGE.GRANTS_TO_ROLES / GRANTS_TO_USERS prefetch helpers.

All rules that access these views must use get_or_fetch() with the constants
defined here so that each view is fetched exactly once per scan session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import Row

# Cache key window — 0 means "no time window; fetch all active (non-deleted) rows".
GRANTS_CACHE_WINDOW = 0

# Column indices for GRANTS_TO_ROLES rows returned by _gtr_fetcher.
# SQL: SELECT GRANTEE_NAME, NAME, GRANTED_ON, PRIVILEGE, TABLE_CATALOG, GRANTED_TO
GTR_GRANTEE_NAME = 0
GTR_NAME = 1
GTR_GRANTED_ON = 2
GTR_PRIVILEGE = 3
GTR_TABLE_CATALOG = 4
GTR_GRANTED_TO = 5

# Column indices for GRANTS_TO_USERS rows returned by _gtu_fetcher.
# SQL: SELECT GRANTEE_NAME, ROLE
GTU_GRANTEE_NAME = 0
GTU_ROLE = 1


def gtr_fetcher(cursor: SnowflakeCursorProtocol):
    """Return a get_or_fetch-compatible fetcher for GRANTS_TO_ROLES.

    Cache key: ("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW).
    Fetches all active role-level grant rows.
    """

    def _fetch(view: str, window: int) -> tuple[Row, ...]:
        cursor.execute(
            "SELECT GRANTEE_NAME, NAME, GRANTED_ON, PRIVILEGE, TABLE_CATALOG, GRANTED_TO"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
            " WHERE DELETED_ON IS NULL"
        )
        return tuple(cursor.fetchall())

    return _fetch


def gtu_fetcher(cursor: SnowflakeCursorProtocol):
    """Return a get_or_fetch-compatible fetcher for GRANTS_TO_USERS.

    Cache key: ("GRANTS_TO_USERS", GRANTS_CACHE_WINDOW).
    Fetches all active user-role assignment rows.
    """

    def _fetch(view: str, window: int) -> tuple[Row, ...]:
        cursor.execute(
            "SELECT GRANTEE_NAME, ROLE"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS"
            " WHERE DELETED_ON IS NULL"
        )
        return tuple(cursor.fetchall())

    return _fetch


def admin_role_user_counts(
    gtr: tuple[Row, ...],
    gtu: tuple[Row, ...],
) -> dict[str, set[str]]:
    """BFS: return {admin_role: set[user_name]} for users who can reach each admin role.

    A1 fix: traverses the full role-inheritance graph.  A user who holds
    ROLE_A → ROLE_B → ACCOUNTADMIN is correctly counted as an ACCOUNTADMIN
    grantee — something the old SHOW GRANTS OF ROLE approach missed.

    Args:
        gtr: Rows from GRANTS_TO_ROLES (columns per GTR_* indices above).
        gtu: Rows from GRANTS_TO_USERS (columns per GTU_* indices above).

    Returns:
        Mapping from "ACCOUNTADMIN"/"SECURITYADMIN"/"SYSADMIN" to the set of
        users who can reach that admin role via any path.
    """
    _ADMIN_ROLES = frozenset({"ACCOUNTADMIN", "SECURITYADMIN", "SYSADMIN"})

    # Build role-containment graph: role -> roles it inherits.
    # When GRANTED_ON='ROLE', NAME was granted TO GRANTEE_NAME, meaning
    # GRANTEE_NAME "contains"/inherits NAME.
    role_contains: dict[str, list[str]] = {}
    for row in gtr:
        if str(row[GTR_GRANTED_ON]).upper() == "ROLE":
            parent = str(row[GTR_GRANTEE_NAME]).upper()
            child = str(row[GTR_NAME]).upper()
            role_contains.setdefault(parent, []).append(child)

    # Group users by their directly-assigned roles (from GRANTS_TO_USERS).
    user_direct_roles: dict[str, set[str]] = {}
    for row in gtu:
        user = str(row[GTU_GRANTEE_NAME])
        role = str(row[GTU_ROLE]).upper()
        user_direct_roles.setdefault(user, set()).add(role)

    result: dict[str, set[str]] = {r: set() for r in _ADMIN_ROLES}

    for user, start_roles in user_direct_roles.items():
        # BFS from this user's direct roles through the role-inheritance graph.
        visited: set[str] = set()
        queue: list[str] = list(start_roles)
        while queue:
            role = queue.pop()
            if role in visited:
                continue
            visited.add(role)
            if role in _ADMIN_ROLES:
                result[role].add(user)
            for inherited in role_contains.get(role, []):
                if inherited not in visited:
                    queue.append(inherited)

    return result
