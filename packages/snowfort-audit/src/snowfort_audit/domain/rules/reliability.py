from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT,
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB,
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
    is_excluded_db_or_warehouse_name,
)
from snowfort_audit.domain.scan_context import (
    TC_ENABLE_SCHEMA_EVOLUTION,
    TC_RETENTION_TIME,
    TC_TABLE_CATALOG,
    TC_TABLE_NAME,
    TC_TABLE_SCHEMA,
    TC_TABLE_TYPE,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext


class ReplicationCheck(Rule):
    """REL_001: Ensure Production databases are being replicated."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_001",
            "Replication Gaps",
            Severity.CRITICAL,
            rationale=(
                "Production databases must be replicated to a secondary region/account for Disaster Recovery. "
                "Single-region deployments are a single point of failure."
            ),
            remediation=(
                "Add database to a FAILOVER GROUP or REPLICATION GROUP: 'ALTER FAILOVER GROUP <grp> ADD <db>'."
            ),
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        violations = []
        try:
            # 1. Identify PRD Databases
            all_dbs = self._fetch_prod_db_names(cursor, scan_context)

            if not all_dbs:
                return []

            # 2. Check Replication Status
            cursor.execute("SHOW REPLICATION DATABASES")
            replicated_dbs = {row[1] for row in cursor.fetchall()}  # name is usually 2nd col

            # 3. Find gaps
            for db in all_dbs:
                if db not in replicated_dbs:
                    violations.append(
                        Violation(
                            self.id,
                            f"Database '{db}'",
                            "Production Database is NOT configured for Replication.",
                            self.severity,
                        )
                    )

        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc

        return violations

    def _fetch_prod_db_names(self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None) -> list[str]:
        all_dbs = []
        if scan_context is not None and scan_context.databases is not None:
            name_idx = scan_context.databases_cols.get("name", 1)
            rows: list = list(scan_context.databases)
        else:
            cursor.execute("SHOW DATABASES")
            cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
            rows = cursor.fetchall()
            name_idx = cols.get("name", 1)
        for row in rows:
            name = row[name_idx]
            if not is_excluded_db_or_warehouse_name(name) and ("PRD" in name.upper() or "PROD" in name.upper()):
                all_dbs.append(name)
        return all_dbs


class RetentionSafetyCheck(Rule):
    """REL_002: Flag Production Tables with DATA_RETENTION_TIME_IN_DAYS = 0."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_002",
            "Retention Safety",
            Severity.HIGH,
            rationale=(
                "Time Travel allows you to restore data modified or deleted. "
                "0 days retention means data is lost instantly upon error."
            ),
            remediation=(
                "Increase DATA_RETENTION_TIME_IN_DAYS to at least 1 for all Production tables "
                "(up to 90 for Enterprise Edition)."
            ),
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            if scan_context is not None and scan_context.tables is not None:
                rows = [
                    r
                    for r in scan_context.tables
                    if r[TC_TABLE_TYPE] == "BASE TABLE"
                    and r[TC_RETENTION_TIME] == 0
                    and ("PRD" in str(r[TC_TABLE_CATALOG]).upper() or "PROD" in str(r[TC_TABLE_CATALOG]).upper())
                    and not is_excluded_db_or_warehouse_name(r[TC_TABLE_CATALOG])
                ][:50]
            else:
                query = (
                    """
                SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
                WHERE DELETED IS NULL
                AND RETENTION_TIME = 0
                AND TABLE_TYPE = 'BASE TABLE'
                AND (TABLE_CATALOG ILIKE '%PRD%' OR TABLE_CATALOG ILIKE '%PROD%')
                """
                    + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
                    + """
                LIMIT 50
                """
                )
                cursor.execute(query)
                rows = cursor.fetchall()
            return [
                Violation(
                    self.id,
                    f"{row[TC_TABLE_CATALOG]}.{row[TC_TABLE_SCHEMA]}.{row[TC_TABLE_NAME]}",
                    "Production table has 0 days retention (Time Travel disabled).",
                    self.severity,
                )
                for row in rows
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class AdequateTimeTravelRetentionCheck(Rule):
    """REL_006: Flag production tables with minimal (1-day) retention that may need longer (WAF: adequate retention)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_006",
            "Adequate Time Travel Retention",
            Severity.LOW,
            rationale="Critical production tables with only 1-day retention offer limited recovery window; WAF recommends balancing recovery needs with storage costs.",
            remediation="Increase DATA_RETENTION_TIME_IN_DAYS for critical tables (e.g., 7+ days); up to 90 for Enterprise Edition.",
            remediation_key="INCREASE_RETENTION_DAYS",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            if scan_context is not None and scan_context.tables is not None:
                rows = [
                    r
                    for r in scan_context.tables
                    if r[TC_TABLE_TYPE] == "BASE TABLE"
                    and r[TC_RETENTION_TIME] == 1
                    and ("PRD" in str(r[TC_TABLE_CATALOG]).upper() or "PROD" in str(r[TC_TABLE_CATALOG]).upper())
                    and not is_excluded_db_or_warehouse_name(r[TC_TABLE_CATALOG])
                ][:50]
            else:
                query = (
                    """
                SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
                WHERE DELETED IS NULL
                AND TABLE_TYPE = 'BASE TABLE'
                AND (TABLE_CATALOG ILIKE '%PRD%' OR TABLE_CATALOG ILIKE '%PROD%')
                AND RETENTION_TIME = 1
                """
                    + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
                    + """
                LIMIT 50
                """
                )
                cursor.execute(query)
                rows = cursor.fetchall()
            return [
                self.violation(
                    f"{row[TC_TABLE_CATALOG]}.{row[TC_TABLE_SCHEMA]}.{row[TC_TABLE_NAME]}",
                    "Production table has only 1-day Time Travel retention; consider 7+ days for critical data.",
                )
                for row in rows
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class SchemaEvolutionCheck(Rule):
    """REL_003: Flag Production Tables with ENABLE_SCHEMA_EVOLUTION = TRUE."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_003",
            "Schema Instability",
            Severity.HIGH,
            rationale=(
                "Schema Evolution allows tables to change structure automatically, "
                "which can break downstream pipelines and governance controls."
            ),
            remediation=(
                "Disable schema evolution: 'ALTER TABLE <name> SET ENABLE_SCHEMA_EVOLUTION = FALSE'. "
                "Manage schema changes via controlled deployment pipelines."
            ),
            telemetry=telemetry,
        )

    def check(self, resource: dict, resource_name: str) -> list[Violation]:
        if resource.get("type", "").upper() == "TABLE" and resource.get("enable_schema_evolution", False):
            return [
                Violation(
                    self.id,
                    resource_name,
                    "Schema Evolution enabled in manifest",
                    self.severity,
                )
            ]
        return []

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            if scan_context is not None and scan_context.tables is not None:
                rows = [
                    r
                    for r in scan_context.tables
                    if str(r[TC_ENABLE_SCHEMA_EVOLUTION] or "").upper() in ("YES", "TRUE", "1")
                    and not is_excluded_db_or_warehouse_name(r[TC_TABLE_CATALOG])
                ][:50]
            else:
                query = (
                    """
                SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
                WHERE DELETED IS NULL
                AND ENABLE_SCHEMA_EVOLUTION = 'YES'
                """
                    + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
                    + """
                LIMIT 50
                """
                )
                cursor.execute(query)
                rows = cursor.fetchall()
            return [
                Violation(
                    self.id,
                    f"{row[TC_TABLE_CATALOG]}.{row[TC_TABLE_SCHEMA]}.{row[TC_TABLE_NAME]}",
                    "Table has automatic schema evolution enabled.",
                    self.severity,
                )
                for row in rows
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class FailoverGroupCompletenessCheck(Rule):
    """REL_004: Verify failover groups include account objects (users, roles, warehouses) alongside databases (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_004",
            "Failover Group Completeness",
            Severity.MEDIUM,
            rationale="Replicating only data leaves account objects (users, roles, warehouses) out of DR; WAF recommends replicating account objects too.",
            remediation="Add account object types to the failover group so users, roles, and warehouses are replicated.",
            remediation_key="FAILOVER_ACCOUNT_OBJECTS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW FAILOVER GROUPS")
            rows = cursor.fetchall()
            if not rows:
                return []
            cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
            name_idx = cols.get("name", 1)
            obj_types_idx = cols.get("object_types", -1)
            if obj_types_idx < 0:
                return []
            violations = []
            for row in rows:
                name = row[name_idx]
                obj_types = str(row[obj_types_idx] or "").upper()
                if "ROLES" not in obj_types and "USERS" not in obj_types and "ACCOUNT" not in obj_types:
                    violations.append(
                        self.violation(
                            name,
                            "Failover group does not include account objects (e.g. ROLES, USERS, WAREHOUSES); add them for full DR.",
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ReplicationLagMonitoringCheck(Rule):
    """REL_005: Flag replication lag exceeding threshold (WAF: align replication schedule with requirements)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_005",
            "Replication Lag Monitoring",
            Severity.MEDIUM,
            rationale="High replication lag increases RPO risk; WAF recommends configuring a frequent replication schedule aligned with business requirements.",
            remediation="Increase replication frequency or optimize source workload to reduce lag.",
            remediation_key="REDUCE_REPLICATION_LAG",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT t.REPLICATION_GROUP_NAME, t.PRIMARY_SNAPSHOT_TIMESTAMP,
               DATEDIFF('minute', t.PRIMARY_SNAPSHOT_TIMESTAMP, CURRENT_TIMESTAMP()) AS LAG_MIN
        FROM (
            SELECT REPLICATION_GROUP_NAME, PRIMARY_SNAPSHOT_TIMESTAMP, END_TIME,
                   ROW_NUMBER() OVER (PARTITION BY REPLICATION_GROUP_NAME ORDER BY END_TIME DESC) AS rn
            FROM SNOWFLAKE.ACCOUNT_USAGE.REPLICATION_GROUP_REFRESH_HISTORY
            WHERE END_TIME >= DATEADD(day, -1, CURRENT_TIMESTAMP())
        ) t
        WHERE t.rn = 1 AND DATEDIFF('minute', t.PRIMARY_SNAPSHOT_TIMESTAMP, CURRENT_TIMESTAMP()) > 60
        LIMIT 50
        """
        try:
            cursor.execute(query)
            return [
                self.violation(
                    row[0],
                    f"Replication lag exceeds 60 minutes (current lag ~{row[2]} min).",
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class FailedTaskDetectionCheck(Rule):
    """REL_007: Flag recurring task failures in last 7 days (WAF: monitor TASK_HISTORY)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_007",
            "Failed Task Detection",
            Severity.MEDIUM,
            rationale="Recurring task failures indicate pipeline or configuration issues; WAF recommends monitoring operational health via TASK_HISTORY.",
            remediation="Inspect task error messages, fix dependencies or permissions, and consider SUSPEND_TASK_AFTER_NUM_FAILURES and alerting.",
            remediation_key="FIX_FAILED_TASKS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT NAME, DATABASE_NAME, SCHEMA_NAME, COUNT(*) AS FAIL_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
        WHERE STATE IN ('FAILED', 'FAILED_AND_AUTO_SUSPENDED')
        AND QUERY_START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB
            + """
        GROUP BY NAME, DATABASE_NAME, SCHEMA_NAME
        HAVING COUNT(*) >= 1
        ORDER BY FAIL_COUNT DESC
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            return [
                self.violation(
                    f"{row[1]}.{row[2]}.{row[0]}",
                    f"Task failed {row[3]} time(s) in last 7 days; investigate and fix.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class PipelineObjectReplicationCheck(Rule):
    """REL_008: Flag production databases with pipes/stages that are not in a replication group (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_008",
            "Pipeline Object Replication",
            Severity.MEDIUM,
            rationale="Production Snowpipes and stages should be in replication scope; WAF recommends including them in failover groups.",
            remediation="Add the database (and thus its pipes/stages) to a replication group, or replicate account objects that include integrations.",
            remediation_key="REPLICATE_PIPELINE_OBJECTS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT p.database_name
        FROM SNOWFLAKE.ACCOUNT_USAGE.PIPES p
        WHERE p.deleted IS NULL
        AND (p.database_name ILIKE '%PRD%' OR p.database_name ILIKE '%PROD%')
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB.replace("DATABASE_NAME", "p.database_name")
            + """
        AND NOT EXISTS (
            SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.REPLICATION_DATABASES r
            WHERE r.database_name = p.database_name
        )
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            seen_db: set[str] = set()
            violations = []
            for row in cursor.fetchall():
                db = row[0]
                if db not in seen_db:
                    seen_db.add(db)
                    violations.append(
                        self.violation(
                            db,
                            "Production database contains pipes but is not in a replication group; add to replication for DR.",
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class DynamicTableRefreshLagCheck(Rule):
    """REL_009: Flag Dynamic Tables whose actual refresh lag exceeds their target lag.

    Briefing: Dynamic Tables with persistent lag mean downstream consumers are reading
    stale data, potentially breaking SLAs that depend on near-real-time freshness.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_009",
            "Dynamic Table Refresh Lag",
            Severity.MEDIUM,
            rationale=(
                "A Dynamic Table falling behind its target refresh lag means downstream "
                "consumers see stale data. Persistent lag indicates insufficient warehouse "
                "capacity or blocking refresh chains."
            ),
            remediation=(
                "Increase the warehouse size for the Dynamic Table's refresh task, or "
                "reduce the table's complexity / dependency chain depth. "
                "Review DYNAMIC_TABLE_REFRESH_HISTORY for errors."
            ),
            remediation_key="FIX_DT_LAG",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT
            TABLE_CATALOG,
            TABLE_SCHEMA,
            NAME,
            TARGET_LAG_SEC,
            ACTUAL_LAG_SEC
        FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
        WHERE REFRESH_END_TIME >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
          AND ACTUAL_LAG_SEC IS NOT NULL
          AND TARGET_LAG_SEC IS NOT NULL
          AND ACTUAL_LAG_SEC > TARGET_LAG_SEC * 1.5
        LIMIT 50
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, name, target, actual = row[0], row[1], row[2], row[3], row[4]
                fq = f"{db}.{schema}.{name}"
                violations.append(
                    self.violation(
                        fq,
                        f"Dynamic Table '{fq}' actual lag {actual:.0f}s exceeds "
                        f"target lag {target:.0f}s (>{target * 1.5:.0f}s threshold).",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class DynamicTableFailureDetectionCheck(Rule):
    """REL_010: Flag Dynamic Tables in FAILED state within the last 24 hours.

    Briefing: A FAILED Dynamic Table stops refreshing entirely, causing all downstream
    consumers to receive permanently stale data with no visible error to end users.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "REL_010",
            "Dynamic Table Failure Detection",
            Severity.HIGH,
            rationale=(
                "A Dynamic Table with STATE='FAILED' has stopped refreshing. "
                "Downstream consumers receive permanently stale data silently."
            ),
            remediation=(
                "Investigate failure via DYNAMIC_TABLE_REFRESH_HISTORY. "
                "Check for upstream table errors, schema changes, or resource exhaustion. "
                "Resume with: ALTER DYNAMIC TABLE <name> RESUME."
            ),
            remediation_key="RESUME_FAILED_DT",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT DISTINCT
            TABLE_CATALOG,
            TABLE_SCHEMA,
            NAME,
            STATE,
            ERROR_MESSAGE
        FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
        WHERE REFRESH_END_TIME >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
          AND STATE = 'FAILED'
        LIMIT 50
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, name, state = row[0], row[1], row[2], row[3]
                err_msg = row[4] or "No error details available."
                fq = f"{db}.{schema}.{name}"
                violations.append(
                    self.violation(
                        fq,
                        f"Dynamic Table '{fq}' is in {state} state. Error: {str(err_msg)[:120]}",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
