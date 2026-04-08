"""ScanContext: pre-fetched shared query results passed to check_online().

Created once before rules run in OnlineScanUseCase; passed to each rule via
check_online(cursor, scan_context=ctx).  Read-only by convention — workers
hold references to the same immutable data.

Column indices for tag_refs rows:
    0=DOMAIN  1=OBJECT_NAME  2=TAG_NAME  3=TAG_VALUE  4=COLUMN_NAME

Column indices for tables rows:
    0=TABLE_CATALOG  1=TABLE_SCHEMA  2=TABLE_NAME  3=TABLE_TYPE
    4=BYTES  5=ROW_COUNT  6=RETENTION_TIME  7=ENABLE_SCHEMA_EVOLUTION
    8=CLUSTERING_KEY  9=COMMENT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Row = tuple[Any, ...]


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
    # SNOWFLAKE.ACCOUNT_USAGE.TABLES (DELETED IS NULL)
    # cols: TABLE_CATALOG=0, TABLE_SCHEMA=1, TABLE_NAME=2, TABLE_TYPE=3,
    #        BYTES=4, ROW_COUNT=5, RETENTION_TIME=6, ENABLE_SCHEMA_EVOLUTION=7,
    #        CLUSTERING_KEY=8, COMMENT=9
    tables: tuple[Row, ...] | None = None
