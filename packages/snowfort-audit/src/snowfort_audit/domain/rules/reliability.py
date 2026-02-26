from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT,
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB,
    Rule,
    Severity,
    Violation,
    is_excluded_db_or_warehouse_name,
)

# Removed Infrastructure import


if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        violations = []
        try:
            # 1. Identify PRD Databases
            cursor.execute("SHOW DATABASES")
            all_dbs = []
            cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}

            for row in cursor.fetchall():
                name = row[cols["name"]]
                if is_excluded_db_or_warehouse_name(name):
                    continue
                if "PRD" in name.upper() or "PROD" in name.upper():
                    all_dbs.append(name)

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

        except Exception:
            pass

        return violations


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}.{row[2]}",
                    "Production table has 0 days retention (Time Travel disabled).",
                    self.severity,
                )
                for row in rows
            ]
        except Exception:
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                self.violation(
                    f"{row[0]}.{row[1]}.{row[2]}",
                    "Production table has only 1-day Time Travel retention; consider 7+ days for critical data.",
                )
                for row in rows
            ]
        except Exception:
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}.{row[2]}",
                    "Table has automatic schema evolution enabled.",
                    self.severity,
                )
                for row in rows
            ]
        except Exception:
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"FailoverGroupCompletenessCheck failed: {e}")
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"ReplicationLagMonitoringCheck failed: {e}")
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"FailedTaskDetectionCheck failed: {e}")
            return []


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
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
        except Exception as e:
            if self.telemetry:
                err_str = str(e).lower()
                if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                    self.telemetry.debug(f"REL_008 skipped (REPLICATION_DATABASES not available): {e}")
                else:
                    self.telemetry.error(f"PipelineObjectReplicationCheck failed: {e}")
            return []
