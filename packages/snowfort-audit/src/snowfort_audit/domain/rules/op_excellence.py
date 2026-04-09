from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation, is_excluded_db_or_warehouse_name
from snowfort_audit.domain.scan_context import TR_DOMAIN, TR_OBJECT_NAME, TR_TAG_NAME

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext

# Removed Infrastructure import


class ResourceMonitorCheck(Rule):
    """OP_001: Check for missing Resource Monitors at account/warehouse level."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OP_001",
            "Resource Monitoring",
            Severity.MEDIUM,
            rationale="Unmonitored compute resources can lead to surprise billing spikes; Resource Monitors provide a critical hard-limit safety net to automatically suspend a warehouse.",
            remediation=(
                "Configure Resource Monitors or set up Snowflake Budgets (public preview) "
                "to alert on spending thresholds."
            ),
            remediation_key="CREATE_RESOURCE_MONITOR",
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
            # Check for any resource monitors
            cursor.execute("SHOW RESOURCE MONITORS")
            monitors = cursor.fetchall()
            if not monitors:
                violations.append(
                    Violation(
                        self.id,
                        "Account",
                        "No Resource Monitors defined in account.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                )

            # Check warehouses without monitors (skip system/tool warehouses)
            if scan_context is not None and scan_context.warehouses is not None:
                warehouses = list(scan_context.warehouses)
                _wh_cols = scan_context.warehouses_cols
                rm_idx = _wh_cols.get("resource_monitor", 16)
                name_idx = _wh_cols.get("name", 0)
            else:
                cursor.execute("SHOW WAREHOUSES")
                wh_desc = cursor.description or []
                _wh_cols = {col[0].lower(): i for i, col in enumerate(wh_desc)}
                warehouses = cursor.fetchall()
                rm_idx = _wh_cols.get("resource_monitor", 16)
                name_idx = _wh_cols.get("name", 0)
            for wh in warehouses:
                wh_name = wh[name_idx]
                if is_excluded_db_or_warehouse_name(wh_name):
                    continue
                wh_monitor = wh[rm_idx]  # 'resource_monitor' column
                if wh_monitor == "null" or not wh_monitor:
                    is_prod = "PROD" in wh_name.upper() or "PRODUCTION" in wh_name.upper()
                    is_sandbox = "SANDBOX" in wh_name.upper() or "SB" in wh_name.upper()

                    effective_severity = self.severity
                    if is_sandbox:
                        effective_severity = Severity.CRITICAL
                    elif is_prod:
                        effective_severity = Severity.MEDIUM

                    violations.append(
                        Violation(
                            self.id,
                            wh_name,
                            f"Warehouse '{wh_name}' has no Resource Monitor attached.",
                            effective_severity,
                            remediation_key=self.remediation_key,
                        )
                    )

        except Exception:
            pass
        return violations


class ObjectCommentCheck(Rule):
    """OP_002: Ensure Databases/Schemas have comments for documentation/ownership."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OP_002",
            "Object Documentation",
            Severity.LOW,
            rationale="Lack of documentation (comments) makes it hard to understand data ownership and purpose, increasing coordination costs and the risk of accidental data deletion.",
            remediation="Add comments to objects: 'ALTER DATABASE <name> SET COMMENT = \"Description\"'.",
            remediation_key="FIX_DOCUMENTATION",
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
            if scan_context is not None and scan_context.databases is not None:
                dbs = list(scan_context.databases)
                name_idx = scan_context.databases_cols.get("name", 1)
                comment_idx = scan_context.databases_cols.get("comment", 9)
            else:
                cursor.execute("SHOW DATABASES")
                db_desc = cursor.description or []
                db_cols = {col[0].lower(): i for i, col in enumerate(db_desc)}
                dbs = cursor.fetchall()
                name_idx = db_cols.get("name", 1)
                comment_idx = db_cols.get("comment", 9)
            for db in dbs:
                db_name = db[name_idx]
                if is_excluded_db_or_warehouse_name(db_name):
                    continue
                comment = db[comment_idx]
                if not comment or comment == "":
                    msg = f"Database '{db_name}' is missing a comment/description."
                    violations.append(
                        Violation(self.id, db_name, msg, self.severity, remediation_key=self.remediation_key)
                    )
        except Exception:
            pass
        return violations


class MandatoryTaggingCheck(Rule):
    """OPS_001: Ensure critical resources have mandatory tags (Cost Center, Owner, Environment)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "OPS_001",
            "Mandatory Tagging",
            Severity.MEDIUM,
            rationale="Missing tags for Cost Center or Owner makes financial accountability impossible, preventing accurate chargebacks and causing operational blindness.",
            remediation=(
                "Apply tags using: 'ALTER WAREHOUSE <name> SET TAG COST_CENTER = \"Value\"'. "
                "Recommended: COST_CENTER, OWNER, ENVIRONMENT."
            ),
            remediation_key="APPLY_MANDATORY_TAGS",
            telemetry=telemetry,
        )
        self._conventions = conventions
        self.recommended_tags = {"COST_CENTER", "OWNER", "ENVIRONMENT"}

    def _exclude_warehouse_patterns(self) -> tuple[str, ...]:
        if self._conventions is not None:
            return self._conventions.thresholds.mandatory_tagging.exclude_warehouse_patterns
        return ("COMPUTE_SERVICE_WH_*",)

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
            warehouses = self._resolve_warehouse_names(cursor, scan_context)
            databases = self._resolve_database_names(cursor, scan_context)
            tagged_objects = self._resolve_tag_map(cursor, scan_context)
            for wh in warehouses:
                violations.extend(self._validate_tags("WAREHOUSE", wh, tagged_objects))
            for db in databases:
                violations.extend(self._validate_tags("DATABASE", db, tagged_objects))
        except Exception:
            pass
        return violations

    def _resolve_warehouse_names(self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None) -> set[str]:
        exclude_patterns = self._exclude_warehouse_patterns()
        if scan_context is not None and scan_context.warehouses is not None:
            return {
                wh[0]
                for wh in scan_context.warehouses
                if not is_excluded_db_or_warehouse_name(wh[0])
                and not any(fnmatch.fnmatchcase(str(wh[0]).upper(), p.upper()) for p in exclude_patterns)
            }
        cursor.execute("SHOW WAREHOUSES")
        return {
            row[0]
            for row in cursor.fetchall()
            if not is_excluded_db_or_warehouse_name(row[0])
            and not any(fnmatch.fnmatchcase(str(row[0]).upper(), p.upper()) for p in exclude_patterns)
        }

    def _resolve_database_names(self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None) -> set[str]:
        if scan_context is not None and scan_context.databases is not None:
            idx = scan_context.databases_cols.get("name", 1)
            return {db[idx] for db in scan_context.databases if not is_excluded_db_or_warehouse_name(db[idx])}
        cursor.execute("SHOW DATABASES")
        return {row[1] for row in cursor.fetchall() if not is_excluded_db_or_warehouse_name(row[1])}

    def _resolve_tag_map(
        self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None
    ) -> dict[tuple[str, str], set[str]]:
        tagged: dict[tuple[str, str], set[str]] = {}
        if scan_context is not None and scan_context.tag_refs_index is not None:
            for (domain, obj_name), tags in scan_context.tag_refs_index.items():
                if domain in ("WAREHOUSE", "DATABASE"):
                    tagged[(domain, obj_name)] = set(tags.keys())
        elif scan_context is not None and scan_context.tag_refs is not None:
            for row in scan_context.tag_refs:
                domain = str(row[0]).upper()
                if domain not in ("WAREHOUSE", "DATABASE"):
                    continue
                key: tuple[str, str] = (domain, str(row[1]).upper())
                tagged.setdefault(key, set()).add(str(row[2]).upper())
        else:
            cursor.execute(
                "SELECT DOMAIN, OBJECT_NAME, TAG_NAME"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES"
                " WHERE DOMAIN IN ('WAREHOUSE', 'DATABASE') AND OBJECT_DELETED IS NULL"
            )
            for row in cursor.fetchall():
                key = (row[0].upper(), row[1].upper())
                tagged.setdefault(key, set()).add(row[2].upper())
        return tagged

    def _validate_tags(
        self, domain: str, name: str, tagged_objects: dict[tuple[str, str], set[str]]
    ) -> list[Violation]:
        existing_tags = tagged_objects.get((domain, name.upper()), set())
        if not existing_tags:
            return [
                Violation(
                    self.id,
                    f"{domain.title()} '{name}'",
                    "Object has ZERO tags. Governance failure.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        missing = self.recommended_tags - existing_tags
        if missing:
            return [
                Violation(
                    self.id,
                    f"{domain.title()} '{name}'",
                    f"Missing recommended WAF tags: {', '.join(missing)}",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class AlertConfigurationCheck(Rule):
    """OPS_003: Verify at least some Snowflake Alerts are configured and active (WAF: automate monitoring)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_003",
            "Alert Configuration",
            Severity.LOW,
            rationale="WAF recommends automated alerts for performance, cost, and failures; no alerts implies reactive-only operations.",
            remediation="Create Snowflake Alerts for critical conditions (e.g., failed tasks, long-running queries) and RESUME them.",
            remediation_key="CONFIGURE_ALERTS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW ALERTS")
            alerts = cursor.fetchall()
            cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
            state_idx = cols.get("state", cols.get("condition", 1))
            resumed = sum(
                1 for row in alerts if row[state_idx] == "started" or str(row[state_idx]).lower() == "resumed"
            )
            if not alerts:
                return [
                    self.violation(
                        "Account", "No Snowflake Alerts defined; configure alerts for key metrics and failures."
                    )
                ]
            if resumed == 0:
                return [
                    self.violation(
                        "Account", "Alerts exist but none are RESUMED; resume alerts to enable notifications."
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"AlertConfigurationCheck failed: {e}")
            return []
        return []


class NotificationIntegrationCheck(Rule):
    """OPS_007: Verify at least one notification integration exists (WAF: alert channels)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_007",
            "Notification Integration",
            Severity.LOW,
            rationale="Alerts need notification integrations (email, Slack, PagerDuty) to notify teams; WAF recommends configuring channels.",
            remediation="Create a notification integration: CREATE NOTIFICATION INTEGRATION ... TYPE = EMAIL | ... and use it in alerts.",
            remediation_key="CREATE_NOTIFICATION_INTEGRATION",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW NOTIFICATION INTEGRATIONS")
            integrations = cursor.fetchall()
            if not integrations:
                return [
                    self.violation(
                        "Account",
                        "No notification integration defined; create one to send alert notifications (email, webhook, etc.).",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"NotificationIntegrationCheck failed: {e}")
            return []
        return []


class ObservabilityInfrastructureCheck(Rule):
    """OPS_008: Check for centralized observability data model (WAF: dedicated OBSERVABILITY db or monitoring views)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_008",
            "Observability Infrastructure",
            Severity.LOW,
            rationale="WAF recommends a centralized observability database/schema with secure views on ACCOUNT_USAGE for consistent monitoring.",
            remediation="Create a dedicated database (e.g., OBSERVABILITY) with secure views on SNOWFLAKE.ACCOUNT_USAGE key views.",
            remediation_key="OBSERVABILITY_DATABASE",
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
            if scan_context is not None and scan_context.databases is not None:
                name_idx = scan_context.databases_cols.get("name", 1)
                dbs = [
                    db[name_idx].upper()
                    for db in scan_context.databases
                    if not is_excluded_db_or_warehouse_name(db[name_idx])
                ]
            else:
                cursor.execute("SHOW DATABASES")
                dbs = [row[1].upper() for row in cursor.fetchall() if not is_excluded_db_or_warehouse_name(row[1])]
            observability_like = [d for d in dbs if "OBSERVABILITY" in d or "MONITORING" in d or "METRICS" in d]
            if not observability_like:
                return [
                    self.violation(
                        "Account",
                        "No dedicated observability/monitoring database found; consider OBSERVABILITY or MONITORING db with views on ACCOUNT_USAGE.",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"ObservabilityInfrastructureCheck failed: {e}")
            return []
        return []


class IaCDriftReadinessCheck(Rule):
    """OPS_009: Check for IaC/managed-by tagging to support drift detection (WAF: tag resources managed by Terraform/IaC)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_009",
            "IaC Drift Readiness",
            Severity.LOW,
            rationale="WAF recommends periodic drift detection; tagging objects with MANAGED_BY (or similar) enables automation to detect manual changes.",
            remediation="Apply a tag (e.g., MANAGED_BY = 'terraform') to warehouses and databases managed by IaC.",
            remediation_key="TAG_MANAGED_BY",
            telemetry=telemetry,
        )
        self.managed_by_tag_names = {"MANAGED_BY", "MANAGEMENT", "SOURCE", "TERRAFORM"}

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            tagged = self._fetch_managed_tags(cursor, scan_context)
            wh_count = self._count_warehouses(cursor, scan_context)
            db_count = self._count_databases(cursor, scan_context)
            wh_tagged = len({obj for (dom, obj) in tagged if dom == "WAREHOUSE"})
            db_tagged = len({obj for (dom, obj) in tagged if dom == "DATABASE"})
            if wh_count > 0 and wh_tagged == 0:
                return [
                    self.violation(
                        "Account", "No warehouses have MANAGED_BY (or similar) tag; add tag for IaC/drift detection."
                    )
                ]
            if db_count > 0 and db_tagged == 0:
                return [
                    self.violation(
                        "Account", "No databases have MANAGED_BY (or similar) tag; add tag for IaC/drift detection."
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"IaCDriftReadinessCheck failed: {e}")
            return []
        return []

    def _fetch_managed_tags(
        self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None
    ) -> set[tuple[str, str]]:
        tagged: set[tuple[str, str]] = set()
        if scan_context is not None and scan_context.tag_refs_index is not None:
            for (domain, obj_name), tags in scan_context.tag_refs_index.items():
                if domain in ("WAREHOUSE", "DATABASE"):
                    if any(t in self.managed_by_tag_names for t in tags):
                        tagged.add((domain, obj_name))
        elif scan_context is not None and scan_context.tag_refs is not None:
            for row in scan_context.tag_refs:
                domain = str(row[TR_DOMAIN]).upper()
                if domain not in ("WAREHOUSE", "DATABASE"):
                    continue
                if (row[TR_TAG_NAME] or "").upper() in self.managed_by_tag_names:
                    tagged.add((domain, str(row[TR_OBJECT_NAME])))
        else:
            cursor.execute(
                "SELECT DOMAIN, OBJECT_NAME, TAG_NAME"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES"
                " WHERE DOMAIN IN ('WAREHOUSE', 'DATABASE') AND OBJECT_DELETED IS NULL"
            )
            for row in cursor.fetchall():
                if (row[2] or "").upper() in self.managed_by_tag_names:
                    tagged.add((row[0], row[1]))
        return tagged

    def _count_warehouses(self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None) -> int:
        if scan_context is not None and scan_context.warehouses is not None:
            idx = scan_context.warehouses_cols.get("name", 0)
            return sum(1 for r in scan_context.warehouses if not is_excluded_db_or_warehouse_name(r[idx]))
        cursor.execute("SHOW WAREHOUSES")
        return sum(1 for r in cursor.fetchall() if not is_excluded_db_or_warehouse_name(r[0]))

    def _count_databases(self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None) -> int:
        if scan_context is not None and scan_context.databases is not None:
            idx = scan_context.databases_cols.get("name", 1)
            return sum(1 for r in scan_context.databases if not is_excluded_db_or_warehouse_name(r[idx]))
        cursor.execute("SHOW DATABASES")
        return sum(1 for r in cursor.fetchall() if not is_excluded_db_or_warehouse_name(r[1]))


class EventTableConfigurationCheck(Rule):
    """OPS_010: Check whether the account has an event table configured (WAF: centralized monitoring)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_010",
            "Event Table Configuration",
            Severity.LOW,
            rationale="Event tables provide centralized error tracking and diagnostics for tasks, UDFs, and stored procedures; WAF recommends configuring an account-level event table for observability.",
            remediation=(
                "Create an event table: CREATE EVENT TABLE <db>.<schema>.<table>; "
                "Then set account-level: ALTER ACCOUNT SET EVENT_TABLE = <db>.<schema>.<table>;"
            ),
            remediation_key="CONFIGURE_EVENT_TABLE",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW EVENT TABLES IN ACCOUNT")
            rows = cursor.fetchall()
            desc = cursor.description or []
            col_index = next((i for i, c in enumerate(desc) if c[0] and str(c[0]).upper() == "OWNER"), 0)
            customer_owned = [r for r in rows if r[col_index] and str(r[col_index]).upper() != "SNOWFLAKE"]
            if not customer_owned:
                return [
                    self.violation(
                        "Account",
                        "No customer-owned event table configured; event tables enable centralized monitoring for tasks, UDFs, and stored procedures.",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"EventTableConfigurationCheck failed: {e}")
            return []
        return []


class AlertExecutionReliabilityCheck(Rule):
    """OPS_012: Flag alerts that are failing to execute (WAF: operational health)."""

    LOOKBACK_DAYS = 7

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_012",
            "Alert Execution Reliability",
            Severity.MEDIUM,
            rationale="Configured alerts that silently fail provide false confidence; WAF recommends verifying alert execution health.",
            remediation="Investigate failed alerts via ALERT_HISTORY; fix conditions, permissions, or notification integrations and RESUME.",
            remediation_key="FIX_ALERT_EXECUTION",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        lookback = self.LOOKBACK_DAYS
        query = f"""
        SELECT NAME, DATABASE_NAME, SCHEMA_NAME,
               COUNT_IF(STATE IN ('FAILED', 'CONDITION_FAILED', 'ACTION_FAILED')) AS err_count,
               COUNT(*) AS total_runs
        FROM SNOWFLAKE.ACCOUNT_USAGE.ALERT_HISTORY
        WHERE SCHEDULED_TIME >= DATEADD(day, -{lookback}, CURRENT_TIMESTAMP())
        GROUP BY NAME, DATABASE_NAME, SCHEMA_NAME
        HAVING err_count > 0
        ORDER BY err_count DESC
        LIMIT 20
        """
        try:
            cursor.execute(query)
            return [
                self.violation(
                    f"{row[1]}.{row[2]}.{row[0]}",
                    f"Alert had {row[3]} error(s) out of {row[4]} runs in last {lookback} days; investigate.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            if self.telemetry:
                err_str = str(e).lower()
                if "does not exist" in err_str or "not authorized" in err_str:
                    self.telemetry.debug(f"OPS_012 skipped (ALERT_HISTORY not available): {e}")
                else:
                    self.telemetry.error(f"AlertExecutionReliabilityCheck failed: {e}")
            return []


class DataMetricFunctionsCoverageCheck(Rule):
    """OPS_011: Check for Data Metric Functions (DMF) usage for data quality monitoring (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_011",
            "Data Metric Functions Coverage",
            Severity.LOW,
            rationale="Data Metric Functions help monitor data quality and detect anomalies in tables; WAF recommends using DMFs for key tables.",
            remediation=(
                "Create a DATA METRIC FUNCTION and attach to tables: "
                "ALTER TABLE <table> SET DATA_METRIC SCHEDULE = '1 HOUR' DATA METRIC FUNCTION <fn> ON (column);"
            ),
            remediation_key="CONFIGURE_DMF",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_METRIC_FUNCTION_REFERENCES
                WHERE SCHEDULE_STATUS NOT LIKE 'SUSPENDED%'
            """)
            row = cursor.fetchone()
            count = (row[0] or 0) if row else 0
            if count == 0:
                return [
                    self.violation(
                        "Account",
                        "No Data Metric Functions (DMF) references found; DMFs help monitor data quality and detect anomalies in tables.",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"DataMetricFunctionsCoverageCheck failed: {e}")
            return []
        return []
