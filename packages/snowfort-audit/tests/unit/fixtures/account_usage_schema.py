"""ACCOUNT_USAGE view schema fixture for SQL column-name regression tests.

Maps view names to the frozenset of valid column names used by snowfort-audit rules.
These are the columns verified correct as of Snowflake documentation (2026-04-25).
Not exhaustive — covers the columns actually referenced by audit rules.

Snowflake docs:
  https://docs.snowflake.com/en/sql-reference/account-usage.html
  https://docs.snowflake.com/en/sql-reference/functions/system_functions.html

DEPRECATED_COLUMNS maps view → columns that were once mistakenly referenced in rule
SQL queries. Tests assert these do NOT appear in the captured SQL strings.
"""

# ---------------------------------------------------------------------------
# SNOWFLAKE.ACCOUNT_USAGE views
# ---------------------------------------------------------------------------

ACCOUNT_USAGE_SCHEMA: dict[str, frozenset[str]] = {
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_events_history
    "WAREHOUSE_EVENTS_HISTORY": frozenset(
        {
            "TIMESTAMP",
            "WAREHOUSE_ID",
            "WAREHOUSE_NAME",
            "CLUSTER_NUMBER",
            "EVENT_NAME",
            "EVENT_REASON",
            "EVENT_STATE",
            "USER_NAME",
            "ROLE_NAME",
            "QUERY_ID",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_metering_history
    "WAREHOUSE_METERING_HISTORY": frozenset(
        {
            "START_TIME",
            "END_TIME",
            "WAREHOUSE_ID",
            "WAREHOUSE_NAME",
            "CREDITS_USED",
            "CREDITS_USED_COMPUTE",
            "CREDITS_USED_CLOUD_SERVICES",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_load_history
    "WAREHOUSE_LOAD_HISTORY": frozenset(
        {
            "START_TIME",
            "END_TIME",
            "WAREHOUSE_NAME",
            "AVG_RUNNING",
            "AVG_QUEUED_LOAD",
            "AVG_QUEUED_PROVISIONING",
            "AVG_BLOCKED",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/dynamic_table_refresh_history
    "DYNAMIC_TABLE_REFRESH_HISTORY": frozenset(
        {
            "NAME",
            "SCHEMA_NAME",
            "DATABASE_NAME",
            "STATE",
            "STATE_CODE",
            "STATE_MESSAGE",
            "QUERY_ID",
            "DATA_TIMESTAMP",
            "REFRESH_START_TIME",
            "REFRESH_END_TIME",
            "COMPLETION_TARGET",
            "QUALIFIED_NAME",
            "LAST_COMPLETED_DEPENDENCY",
            "STATISTICS",
            "TARGET_LAG_SEC",
            "GRAPH_HISTORY_VALID_FROM",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/tables
    "TABLES": frozenset(
        {
            "TABLE_CATALOG",
            "TABLE_SCHEMA",
            "TABLE_NAME",
            "TABLE_TYPE",
            "BYTES",
            "ROW_COUNT",
            "RETENTION_TIME",
            "CLUSTERING_KEY",
            "COMMENT",
            "CREATED",
            "LAST_ALTERED",
            "DELETED",
            "AUTO_CLUSTERING_ON",
            "IS_TRANSIENT",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/databases
    "DATABASES": frozenset(
        {
            "DATABASE_ID",
            "DATABASE_NAME",
            "DATABASE_OWNER",
            "COMMENT",
            "CREATED",
            "LAST_ALTERED",
            "DELETED",
            "TYPE",
            "RETENTION_TIME",
            "IS_DEFAULT",
            "IS_CURRENT",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/shares
    "SHARES": frozenset(
        {
            "SHARE_ID",
            "NAME",
            "OWNER",
            "COMMENT",
            "CREATED",
            "DELETED_ON",
            "DATABASE_NAME",
            "KIND",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/grants_to_roles
    "GRANTS_TO_ROLES": frozenset(
        {
            "CREATED_ON",
            "MODIFIED_ON",
            "PRIVILEGE",
            "GRANTED_ON",
            "NAME",
            "TABLE_CATALOG",
            "TABLE_SCHEMA",
            "GRANTED_TO",
            "GRANTEE_NAME",
            "GRANT_OPTION",
            "GRANTED_BY",
            "DELETED_ON",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/grants_to_users
    "GRANTS_TO_USERS": frozenset(
        {
            "CREATED_ON",
            "DELETED_ON",
            "ROLE",
            "GRANTED_TO",
            "GRANTEE_NAME",
            "GRANTED_BY",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/tag_references
    "TAG_REFERENCES": frozenset(
        {
            "TAG_DATABASE",
            "TAG_SCHEMA",
            "TAG_ID",
            "TAG_NAME",
            "TAG_VALUE",
            "OBJECT_DATABASE",
            "OBJECT_SCHEMA",
            "OBJECT_NAME",
            "COLUMN_NAME",
            "DOMAIN",
            "OBJECT_DELETED",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/table_storage_metrics
    "TABLE_STORAGE_METRICS": frozenset(
        {
            "ID",
            "TABLE_NAME",
            "TABLE_SCHEMA_ID",
            "TABLE_SCHEMA",
            "TABLE_CATALOG_ID",
            "TABLE_CATALOG",
            "CLONE_GROUP_ID",
            "IS_TRANSIENT",
            "IS_CLONE",
            "ACTIVE_BYTES",
            "TIME_TRAVEL_BYTES",
            "FAILSAFE_BYTES",
            "RETAINED_FOR_CLONE_BYTES",
            "TABLE_CREATED",
            "TABLE_DROPPED",
            "TABLE_ENTERED_FAILSAFE",
            "DELETED",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/query_history
    "QUERY_HISTORY": frozenset(
        {
            "QUERY_ID",
            "QUERY_TEXT",
            "DATABASE_ID",
            "DATABASE_NAME",
            "SCHEMA_ID",
            "SCHEMA_NAME",
            "QUERY_TYPE",
            "SESSION_ID",
            "USER_NAME",
            "ROLE_NAME",
            "WAREHOUSE_ID",
            "WAREHOUSE_NAME",
            "WAREHOUSE_SIZE",
            "WAREHOUSE_TYPE",
            "CLUSTER_NUMBER",
            "QUERY_TAG",
            "EXECUTION_STATUS",
            "ERROR_CODE",
            "ERROR_MESSAGE",
            "START_TIME",
            "END_TIME",
            "TOTAL_ELAPSED_TIME",
            "BYTES_SCANNED",
            "ROWS_PRODUCED",
            "COMPILATION_TIME",
            "EXECUTION_TIME",
            "QUEUED_PROVISIONING_TIME",
            "QUEUED_REPAIR_TIME",
            "QUEUED_OVERLOAD_TIME",
            "TRANSACTION_BLOCKED_TIME",
            "OUTBOUND_DATA_TRANSFER_CLOUD",
            "OUTBOUND_DATA_TRANSFER_REGION",
            "OUTBOUND_DATA_TRANSFER_BYTES",
            "INBOUND_DATA_TRANSFER_CLOUD",
            "INBOUND_DATA_TRANSFER_REGION",
            "INBOUND_DATA_TRANSFER_BYTES",
            "CREDITS_USED_CLOUD_SERVICES",
            "RELEASE_VERSION",
            "EXTERNAL_FUNCTION_TOTAL_INVOCATIONS",
            "EXTERNAL_FUNCTION_TOTAL_SENT_ROWS",
            "EXTERNAL_FUNCTION_TOTAL_RECEIVED_ROWS",
            "EXTERNAL_FUNCTION_TOTAL_SENT_BYTES",
            "EXTERNAL_FUNCTION_TOTAL_RECEIVED_BYTES",
            "IS_CLIENT_GENERATED_STATEMENT",
            "CHILD_QUERIES_WAIT_TIME",
            "ROLE_TYPE",
            "QUERY_ACCELERATION_BYTES_SCANNED",
            "QUERY_ACCELERATION_PARTITIONS_SCANNED",
            "QUERY_ACCELERATION_UPPER_LIMIT_SCALE_FACTOR",
        }
    ),
    # Verified from: https://docs.snowflake.com/en/sql-reference/account-usage/task_history
    "TASK_HISTORY": frozenset(
        {
            "QUERY_ID",
            "NAME",
            "DATABASE_NAME",
            "SCHEMA_NAME",
            "QUERY_TEXT",
            "CONDITION_TEXT",
            "STATE",
            "ERROR_CODE",
            "ERROR_MESSAGE",
            "SCHEDULED_TIME",
            "QUERY_START_TIME",
            "COMPLETED_TIME",
            "ROOT_TASK_ID",
            "GRAPH_VERSION",
            "RUN_ID",
            "RETURN_VALUE",
            "SCHEDULED_FROM",
            "ATTEMPT_NUMBER",
            "CONFIG",
            "QUERY_HASH",
            "QUERY_HASH_VERSION",
        }
    ),
}

# ---------------------------------------------------------------------------
# SNOWFLAKE.TRUST_CENTER views (separate schema from ACCOUNT_USAGE)
# ---------------------------------------------------------------------------

TRUST_CENTER_SCHEMA: dict[str, frozenset[str]] = {
    # Verified from: https://docs.snowflake.com/en/sql-reference/snowflake-db/trust_center/findings
    "FINDINGS": frozenset(
        {
            "FINDING_ID",
            "SCANNER_NAME",
            "TITLE",
            "FINDING_TYPE",  # kept for completeness — not the PK column referenced in rules
            "SEVERITY",
            "STATE",
            "CREATED_AT",
            "UPDATED_AT",
            "RESOURCE_TYPE",
            "RESOURCE_NAME",
        }
    ),
}

# ---------------------------------------------------------------------------
# Cortex ACCOUNT_USAGE views — columns vary by view but share a common shape
# ---------------------------------------------------------------------------

# The _CortexRule base class issues `SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.<VIEW>
# WHERE <TIME_COL> >= ...`. The TIME_COL is START_TIME for most views (not USAGE_TIME).
# CORTEX_SEARCH_DAILY_USAGE_HISTORY uses USAGE_DATE instead.
CORTEX_USAGE_VIEWS: dict[str, str] = {
    "CORTEX_AI_FUNCTIONS_USAGE_HISTORY": "START_TIME",
    "CORTEX_AISQL_USAGE_HISTORY": "START_TIME",
    "CORTEX_CODE_CLI_USAGE_HISTORY": "START_TIME",
    "CORTEX_AGENT_USAGE_HISTORY": "START_TIME",
    "SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY": "START_TIME",
    "CORTEX_ANALYST_USAGE_HISTORY": "START_TIME",
    "CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY": "START_TIME",
    "CORTEX_SEARCH_DAILY_USAGE_HISTORY": "USAGE_DATE",
}

# ---------------------------------------------------------------------------
# Deprecated / historically-wrong column names per view.
# These MUST NOT appear in rule SQL queries (caught by regression tests).
# ---------------------------------------------------------------------------

DEPRECATED_COLUMNS: dict[str, frozenset[str]] = {
    # ZombieWarehouseCheck: used START_TIME instead of TIMESTAMP
    "WAREHOUSE_EVENTS_HISTORY": frozenset({"START_TIME"}),
    # _CortexRule base: used USAGE_TIME instead of START_TIME for most Cortex views
    "CORTEX_AI_FUNCTIONS_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "CORTEX_AISQL_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "CORTEX_CODE_CLI_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "CORTEX_AGENT_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "CORTEX_ANALYST_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    "CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY": frozenset({"USAGE_TIME"}),
    # DynamicTable rules: used TABLE_CATALOG/TABLE_SCHEMA and ERROR_MESSAGE
    "DYNAMIC_TABLE_REFRESH_HISTORY": frozenset({"TABLE_CATALOG", "TABLE_SCHEMA", "ERROR_MESSAGE"}),
    # TrustCenterExtensionsCheck: used FINDING_TYPE and STATUS
    "TRUST_CENTER.FINDINGS": frozenset({"STATUS"}),
    # OutboundShareRiskCheck: used SHARE_NAME (column is NAME) and DELETED (column is DELETED_ON)
    "SHARES": frozenset({"SHARE_NAME"}),
}
