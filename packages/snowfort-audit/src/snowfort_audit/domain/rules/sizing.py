"""Warehouse sizing and storage optimization rules (Directive B).

This module hosts the foundation rules for Directive B:
- PERF_020: ThreeLayerUtilizationCheck — P50 exec/queue/idle utilization
- PERF_021: QueryDurationAnomalyCheck — P95/P50 ratio anomaly detection
- PERF_022: WorkloadIsolationCheck — bimodal short+long workloads in same window
- PERF_023: AutoSuspendOptimizationCheck — P75 inter-query gap vs auto_suspend
- COST_034: ConsolidationCandidatesCheck — low-utilization warehouse pair detection
- COST_035: SavingsProjectionCheck — dollar-denominated downsize savings via metering
- COST_036: DormantWarehouseCheck — zero queries for 30+ days and not suspended
- COST_037: ExcessiveTimeTravelRetentionCheck — large, rarely-queried tables with long retention

Remaining Directive B rules (COST_038/039/040) ship as follow-up PRs using the same scaffolding.
"""

from __future__ import annotations

from itertools import combinations
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
from snowfort_audit.domain.workload_profile import project_annual_savings, size_credit_rate

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

_SIZE_ORDER = [
    "X-SMALL",
    "SMALL",
    "MEDIUM",
    "LARGE",
    "X-LARGE",
    "2X-LARGE",
    "3X-LARGE",
    "4X-LARGE",
    "5X-LARGE",
    "6X-LARGE",
]


def _downsize_one(size: str) -> str | None:
    """Return the next smaller Snowflake warehouse size, or None if already smallest."""
    try:
        idx = _SIZE_ORDER.index(size.upper())
    except ValueError:
        return None
    return _SIZE_ORDER[idx - 1] if idx > 0 else None


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


class QueryDurationAnomalyCheck(Rule):
    """PERF_021: Warehouses where P95/P50 query duration ratio exceeds the configured threshold.

    A high P95/P50 ratio signals that a small number of long queries coexist with a fast
    median workload — a classic indicator of mixed-workload sizing mismatch. The warehouse
    is sized for the long tail, penalising the majority of fast queries with unnecessary cost.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "PERF_021",
            "Query Duration Anomaly",
            Severity.LOW,
            rationale=(
                "A P95/P50 query duration ratio > 10× indicates that a small number of long queries "
                "inflate the tail while most queries complete quickly. This signals a bimodal workload "
                "where sizing and scheduling should be separated."
            ),
            remediation=(
                "Review long-running queries and consider routing them to a dedicated batch warehouse. "
                "This frees the interactive warehouse to run at a smaller, cheaper size."
            ),
            remediation_key="ISOLATE_LONG_QUERIES",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        query = f"""
        SELECT
            WAREHOUSE_NAME,
            APPROX_PERCENTILE(EXECUTION_TIME / 1000.0, 0.5)  AS p50_seconds,
            APPROX_PERCENTILE(EXECUTION_TIME / 1000.0, 0.95) AS p95_seconds,
            COUNT(*) AS query_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
          AND EXECUTION_TIME > 0
          AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY 1
        HAVING query_count >= 10
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name = row[0]
                p50 = float(row[1] or 0.0)
                p95 = float(row[2] or 0.0)
                if p50 <= 0.0:
                    continue
                ratio = p95 / p50
                if ratio > thresholds.duration_anomaly_ratio:
                    msg = (
                        f"Warehouse '{name}' has a P95/P50 query duration ratio of {ratio:.1f}× "
                        f"(P50={p50:.1f}s, P95={p95:.1f}s) — exceeds threshold of "
                        f"{thresholds.duration_anomaly_ratio}×. Mixed workloads may be inflating costs."
                    )
                    violations.append(
                        self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class WorkloadIsolationCheck(Rule):
    """PERF_022: Warehouses serving both short interactive and long batch queries.

    Identifies warehouses where some hourly windows have a short median (< 5 s) and others
    have a long median (> 60 s), indicating bimodal traffic that would benefit from
    workload separation.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "PERF_022",
            "Workload Isolation",
            Severity.MEDIUM,
            rationale=(
                "Mixing short interactive queries with long batch queries on the same warehouse forces "
                "a size trade-off: too small starves batch jobs; too large wastes credits on interactive "
                "traffic. Separating workloads lets each warehouse right-size independently."
            ),
            remediation=(
                "Create a dedicated batch warehouse for queries with P50 > 60 s. "
                "Route ETL/reporting jobs via a separate connection or role binding."
            ),
            remediation_key="SEPARATE_WORKLOADS",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        short_p50 = thresholds.workload_split_short_p50_seconds
        long_p50 = thresholds.workload_split_long_p50_seconds
        query = f"""
        WITH hourly AS (
            SELECT
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS hr,
                APPROX_PERCENTILE(EXECUTION_TIME / 1000.0, 0.5) AS p50_seconds
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
              AND EXECUTION_TIME > 0
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT
            WAREHOUSE_NAME,
            SUM(CASE WHEN p50_seconds < {short_p50} THEN 1 ELSE 0 END)  AS short_hours,
            SUM(CASE WHEN p50_seconds > {long_p50}  THEN 1 ELSE 0 END)  AS long_hours,
            COUNT(*) AS total_hours
        FROM hourly
        GROUP BY 1
        HAVING short_hours >= 1 AND long_hours >= 1
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name = row[0]
                short_hours = int(row[1] or 0)
                long_hours = int(row[2] or 0)
                total_hours = int(row[3] or 0)
                if short_hours < 1 or long_hours < 1:
                    continue
                msg = (
                    f"Warehouse '{name}' has mixed workloads: {short_hours} hour(s) with P50 < {short_p50}s "
                    f"and {long_hours} hour(s) with P50 > {long_p50}s out of {total_hours} total hours. "
                    f"Recommend separating interactive and batch workloads."
                )
                violations.append(
                    self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class AutoSuspendOptimizationCheck(Rule):
    """PERF_023: P75 inter-query gap vs current auto_suspend setting.

    If the P75 gap between consecutive queries is shorter than auto_suspend, the warehouse
    idles for longer than necessary between most queries — recommend tightening.
    If the P75 gap exceeds 10× auto_suspend, the warehouse suspends and resumes very
    frequently — flag as already aggressive to avoid churn overhead.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "PERF_023",
            "Auto-Suspend Optimization",
            Severity.LOW,
            rationale=(
                "The auto_suspend setting controls how long a warehouse idles before suspending. "
                "Setting it longer than the typical inter-query gap wastes credits on idle time. "
                "Setting it shorter than necessary causes excessive resume overhead."
            ),
            remediation=(
                "Tighten: ALTER WAREHOUSE <name> SET AUTO_SUSPEND = <p75_gap_seconds>. "
                "For aggressive cases, review whether resume latency is acceptable before loosening."
            ),
            remediation_key="TUNE_AUTO_SUSPEND",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        query = f"""
        WITH gaps AS (
            SELECT
                WAREHOUSE_NAME,
                DATEDIFF(
                    'SECOND',
                    LAG(START_TIME) OVER (PARTITION BY WAREHOUSE_NAME ORDER BY START_TIME),
                    START_TIME
                ) AS gap_seconds
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
        )
        SELECT
            g.WAREHOUSE_NAME,
            APPROX_PERCENTILE(g.gap_seconds, 0.75) AS p75_gap_seconds,
            w.AUTO_SUSPEND                          AS auto_suspend_seconds
        FROM gaps g
        JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES w
          ON w.NAME = g.WAREHOUSE_NAME
         AND w.DELETED IS NULL
        WHERE g.gap_seconds > 0
        GROUP BY g.WAREHOUSE_NAME, w.AUTO_SUSPEND
        HAVING COUNT(*) >= 5
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name = row[0]
                p75_gap = float(row[1] or 0.0)
                auto_suspend = int(row[2] or 0)
                if auto_suspend <= 0:
                    continue
                if p75_gap < auto_suspend:
                    msg = (
                        f"Warehouse '{name}': P75 inter-query gap is {p75_gap:.0f}s but AUTO_SUSPEND "
                        f"is {auto_suspend}s — tighten AUTO_SUSPEND to reduce idle credit spend."
                    )
                    violations.append(
                        self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
                elif p75_gap > thresholds.auto_suspend_aggressive_ratio * auto_suspend:
                    msg = (
                        f"Warehouse '{name}': P75 inter-query gap is {p75_gap:.0f}s but AUTO_SUSPEND "
                        f"is only {auto_suspend}s — warehouse suspends and resumes very frequently "
                        f"(gap is {p75_gap / auto_suspend:.1f}× the suspend window). "
                        f"Consider raising AUTO_SUSPEND to reduce resume overhead."
                    )
                    violations.append(
                        self.violation(name, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ConsolidationCandidatesCheck(Rule):
    """COST_034: Warehouse pairs whose combined P50 utilization is below the consolidation threshold.

    Two warehouses that are each lightly loaded may be cheaper to run as one, eliminating
    per-warehouse minimum-uptime overhead and simplifying governance.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_034",
            "Consolidation Candidates",
            Severity.MEDIUM,
            rationale=(
                "Each running warehouse incurs minimum credit charges on resume. Two lightly-loaded "
                "warehouses with combined P50 utilization well below saturation can often be merged "
                "into one, halving fixed overhead with no throughput impact."
            ),
            remediation=(
                "Evaluate whether the two warehouses serve compatible workloads (similar users, "
                "no security isolation requirement). If so, consolidate and monitor utilization "
                "for 30 days before removing the redundant warehouse."
            ),
            remediation_key="CONSOLIDATE_WAREHOUSES",
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
                AVG(AVG_RUNNING) AS avg_running
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
            GROUP BY 1, 2
        )
        SELECT
            WAREHOUSE_NAME,
            APPROX_PERCENTILE(avg_running, 0.5) AS p50_utilization
        FROM hourly
        GROUP BY 1
        HAVING p50_utilization < {thresholds.consolidation_combined_p50_max / 2.0}
        """
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            warehouses = [(str(row[0]), float(row[1] or 0.0)) for row in rows]
            violations: list[Violation] = []
            combined_max = thresholds.consolidation_combined_p50_max
            for (name_a, p50_a), (name_b, p50_b) in combinations(warehouses, 2):
                combined = p50_a + p50_b
                if combined < combined_max:
                    msg = (
                        f"Warehouses '{name_a}' (P50={p50_a:.2f}) and '{name_b}' (P50={p50_b:.2f}) "
                        f"have combined P50 utilization of {combined:.2f} — below the consolidation "
                        f"threshold of {combined_max}. Consider merging into a single warehouse."
                    )
                    pair_key = f"{name_a}+{name_b}"
                    violations.append(
                        self.violation(pair_key, msg, severity=self.severity, category=FindingCategory.ACTIONABLE)
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class SavingsProjectionCheck(Rule):
    """COST_035: Dollar-denominated annual savings from downsizing underutilized warehouses.

    Queries WAREHOUSE_METERING_HISTORY for actual credit consumption and WAREHOUSE_LOAD_HISTORY
    for P50 utilization. For each underutilized warehouse, projects the annual savings from
    downsizing one tier using published Snowflake credit-per-hour rates.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_035",
            "Savings Projection",
            Severity.LOW,
            rationale=(
                "Translating utilization findings into dollar figures makes the business case concrete. "
                "Credit savings are computed from actual WAREHOUSE_METERING_HISTORY consumption and "
                "Snowflake's published credit-per-size table — not estimates."
            ),
            remediation=(
                "Downsize: ALTER WAREHOUSE <name> SET WAREHOUSE_SIZE = <recommended_size>. "
                "Monitor query latency for 48 hours post-change before making permanent."
            ),
            remediation_key="DOWNSIZE_WAREHOUSE",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        thresholds = _sizing_thresholds(self._conventions)
        query = f"""
        WITH metering AS (
            SELECT
                WAREHOUSE_NAME,
                WAREHOUSE_SIZE,
                SUM(CREDITS_USED) AS total_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
            GROUP BY 1, 2
        ),
        utilization AS (
            SELECT
                WAREHOUSE_NAME,
                APPROX_PERCENTILE(avg_running, 0.5) AS p50_running
            FROM (
                SELECT
                    WAREHOUSE_NAME,
                    DATE_TRUNC('HOUR', START_TIME) AS hr,
                    AVG(AVG_RUNNING) AS avg_running
                FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
                WHERE START_TIME >= DATEADD('DAY', -{thresholds.lookback_days}, CURRENT_TIMESTAMP())
                GROUP BY 1, 2
            )
            GROUP BY 1
        )
        SELECT
            m.WAREHOUSE_NAME,
            m.WAREHOUSE_SIZE,
            m.total_credits,
            u.p50_running
        FROM metering m
        LEFT JOIN utilization u ON u.WAREHOUSE_NAME = m.WAREHOUSE_NAME
        WHERE COALESCE(u.p50_running, 0) < {thresholds.utilization_underused_p50}
          AND m.WAREHOUSE_SIZE != 'X-SMALL'
        """
        try:
            cursor.execute(query)
            violations: list[Violation] = []
            for row in cursor.fetchall():
                name = row[0]
                current_size = str(row[1] or "").upper()
                total_credits = float(row[2] or 0.0)
                recommended_size = _downsize_one(current_size)
                if recommended_size is None:
                    continue
                current_rate = size_credit_rate(current_size)
                monthly_hours = total_credits / current_rate if current_rate > 0 else 0.0
                annual_savings = project_annual_savings(
                    current_size=current_size,
                    recommended_size=recommended_size,
                    monthly_hours=monthly_hours,
                    credit_price=thresholds.credit_price_per_hour,
                )
                if annual_savings <= 0:
                    continue
                msg = (
                    f"Warehouse '{name}' ({current_size}) consumed {total_credits:.0f} credits "
                    f"in {thresholds.lookback_days} days. Downsizing to {recommended_size} could "
                    f"save ~${annual_savings:,.2f}/year at ${thresholds.credit_price_per_hour}/credit."
                )
                violations.append(
                    self.violation(name, msg, severity=self.severity, category=FindingCategory.INFORMATIONAL)
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
