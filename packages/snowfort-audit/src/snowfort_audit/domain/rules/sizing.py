"""Warehouse sizing and storage optimization rules (Directive B pilots).

This module hosts the foundation rules for Directive B:
- PERF_020: ThreeLayerUtilizationCheck — P50 exec/queue/idle utilization
- COST_036: DormantWarehouseCheck — zero queries for 30+ days and not suspended
- COST_037: ExcessiveTimeTravelRetentionCheck — large, rarely-queried tables with long retention

Remaining Directive B rules (PERF_021/022/023, COST_034/035, COST_038/039/040)
ship as follow-up PRs using the same scaffolding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import SnowfortConventions, StorageThresholds, WarehouseSizingThresholds
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    FindingCategory,
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol


def _sizing_thresholds(conv: SnowfortConventions | None) -> WarehouseSizingThresholds:
    return conv.thresholds.warehouse_sizing if conv is not None else WarehouseSizingThresholds()


def _storage_thresholds(conv: SnowfortConventions | None) -> StorageThresholds:
    return conv.thresholds.storage if conv is not None else StorageThresholds()


class ThreeLayerUtilizationCheck(Rule):
    """PERF_020: P50 execution/queue/peak utilization profile per warehouse.

    Uses the pattern from the directive's reference SQL: aggregate
    WAREHOUSE_LOAD_HISTORY per warehouse-hour, then APPROX_PERCENTILE across
    hours. Underutilization (P50 running < threshold) and overload (P50 queued >
    threshold) both surface as MEDIUM / ACTIONABLE findings.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "PERF_020",
            "Three-Layer Utilization Profile",
            Severity.MEDIUM,
            rationale=(
                "P50 utilization across running, queued, and peak layers reveals whether a warehouse is "
                "chronically under-provisioned (queueing), over-provisioned (idle), or right-sized. "
                "Averages hide bimodal workloads; percentiles do not."
            ),
            remediation=(
                "Under-utilized (P50 running below convention): downsize one tier and observe. "
                "Overloaded (P50 queued above convention): upsize one tier or enable multi-cluster."
            ),
            remediation_key="RIGHTSIZE_WAREHOUSE",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        query = f"""
        WITH hourly AS (
            SELECT
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS hr,
                AVG(AVG_RUNNING) AS avg_running,
                AVG(AVG_QUEUED_LOAD) AS avg_queued,
                MAX(AVG_RUNNING + AVG_QUEUED_LOAD + AVG_QUEUED_PROVISIONING + AVG_BLOCKED) AS peak_load
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
            GROUP BY 1, 2
        )
        SELECT
            WAREHOUSE_NAME,
            APPROX_PERCENTILE(avg_running, 0.5) AS p50_running,
            APPROX_PERCENTILE(avg_queued, 0.5) AS p50_queued,
            APPROX_PERCENTILE(peak_load, 0.95) AS p95_peak
        FROM hourly
        GROUP BY 1
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name = row[0]
                p50_running = float(row[1] or 0.0)
                p50_queued = float(row[2] or 0.0)
                p95_peak = float(row[3] or 0.0)
                if p50_running < thresholds.utilization_underused_p50 and p50_running > 0:
                    msg = (
                        f"Warehouse '{name}' underutilized: P50 running={p50_running:.2f} "
                        f"(< {thresholds.utilization_underused_p50}), P95 peak={p95_peak:.2f}."
                    )
                    violations.append(
                        self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
                elif p50_queued > thresholds.utilization_overloaded_p50_queue:
                    msg = (
                        f"Warehouse '{name}' overloaded: P50 queued={p50_queued:.2f} "
                        f"(> {thresholds.utilization_overloaded_p50_queue}), P95 peak={p95_peak:.2f}."
                    )
                    violations.append(
                        self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class DormantWarehouseCheck(Rule):
    """COST_036: Warehouses with zero queries in N+ days that are not suspended."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_036",
            "Dormant Warehouse",
            Severity.HIGH,
            rationale=(
                "A running warehouse with zero queries still incurs minimum-uptime charges when "
                "auto-resume fires. Dormant warehouses should be suspended explicitly or dropped."
            ),
            remediation=(
                "Suspend the warehouse: ALTER WAREHOUSE <name> SUSPEND. "
                "If the warehouse is no longer needed, DROP it to eliminate discovery surface."
            ),
            remediation_key="SUSPEND_DORMANT_WAREHOUSE",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        query = f"""
        WITH last_query AS (
            SELECT WAREHOUSE_NAME, MAX(START_TIME) AS last_seen
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -365, CURRENT_TIMESTAMP())
            GROUP BY 1
        )
        SELECT
            w.NAME,
            w.STATE,
            DATEDIFF('DAY', COALESCE(lq.last_seen, DATEADD('DAY', -365, CURRENT_TIMESTAMP())), CURRENT_TIMESTAMP()) AS days_idle
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES w
        LEFT JOIN last_query lq ON lq.WAREHOUSE_NAME = w.NAME
        WHERE w.DELETED IS NULL
          AND (lq.last_seen IS NULL OR lq.last_seen < DATEADD('DAY', -{thresholds.dormant_days}, CURRENT_TIMESTAMP()))
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name, state, days_idle = row[0], str(row[1] or "").upper(), int(row[2] or 0)
                if state == "SUSPENDED":
                    continue
                if days_idle < thresholds.dormant_days:
                    continue
                msg = (
                    f"Warehouse '{name}' has not run a query in {days_idle} days "
                    f"(>= {thresholds.dormant_days}) and is not suspended."
                )
                violations.append(
                    self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ExcessiveTimeTravelRetentionCheck(Rule):
    """COST_037: Large, rarely-queried tables with long time-travel retention."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_037",
            "Excessive Time Travel Retention",
            Severity.MEDIUM,
            rationale=(
                "Time-travel storage is billed on the churn rate multiplied by the retention window. "
                "Large tables that are rarely queried rarely need long undo history; shorter retention "
                "saves storage credits with no analytical impact."
            ),
            remediation=(
                "Reduce DATA_RETENTION_TIME_IN_DAYS: ALTER TABLE <name> SET DATA_RETENTION_TIME_IN_DAYS = 1. "
                "Or convert the table to TRANSIENT if failsafe is not required."
            ),
            remediation_key="REDUCE_RETENTION",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _storage_thresholds(self._conventions)
        query = f"""
        WITH recent_queries AS (
            SELECT
                COALESCE(oa.OBJECT_NAME, '') AS table_qn,
                COUNT(*) AS q_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY h,
                 LATERAL FLATTEN(input => h.BASE_OBJECTS_ACCESSED) oa
            WHERE h.QUERY_START_TIME >= DATEADD('DAY', -30, CURRENT_TIMESTAMP())
            GROUP BY 1
        )
        SELECT
            sm.TABLE_CATALOG || '.' || sm.TABLE_SCHEMA || '.' || sm.TABLE_NAME AS qn,
            sm.ACTIVE_BYTES,
            t.RETENTION_TIME,
            COALESCE(rq.q_count, 0) AS q_count_30d
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS sm
        JOIN SNOWFLAKE.ACCOUNT_USAGE.TABLES t
          ON t.TABLE_CATALOG = sm.TABLE_CATALOG
         AND t.TABLE_SCHEMA = sm.TABLE_SCHEMA
         AND t.TABLE_NAME = sm.TABLE_NAME
        LEFT JOIN recent_queries rq ON rq.table_qn = qn
        WHERE sm.TABLE_DROPPED IS NULL
          AND sm.ACTIVE_BYTES >= {thresholds.excessive_retention_min_bytes}
          AND t.RETENTION_TIME > {thresholds.excessive_retention_min_days}
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            # "<1 query/day" per the directive → fewer than `lookback_days` queries in that window.
            lookback_days = 30
            for row in cursor.fetchall():
                qn = row[0]
                active_bytes = int(row[1] or 0)
                retention_days = int(row[2] or 0)
                q_count = int(row[3] or 0)
                # Python-side guards so the rule is correct even when callers
                # pass pre-filtered rows (e.g. unit tests with mocked cursors).
                if active_bytes < thresholds.excessive_retention_min_bytes:
                    continue
                if retention_days <= thresholds.excessive_retention_min_days:
                    continue
                if q_count >= lookback_days:
                    continue
                gb = active_bytes / (1024**3)
                msg = (
                    f"Table '{qn}' is {gb:.1f} GB with {retention_days}-day retention but only "
                    f"{q_count} queries in {lookback_days}d — retention is disproportionate to query frequency."
                )
                violations.append(self.violation(qn, msg, severity=self.severity, category=FindingCategory.ACTIONABLE))
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
