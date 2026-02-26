from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT,
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB,
    Rule,
    Severity,
    Violation,
)

# Removed Infrastructure import


CLUSTERING_DEPTH_THRESHOLD = 2.0
ONE_TB_BYTES = 1099511627776


if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol


class ClusterKeyValidationCheck(Rule):
    """PERF_001: Cluster Key Validation for large tables."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_001",
            "Cluster Key Validation",
            Severity.HIGH,
            rationale="Large tables without clustering or with high clustering depth cause partition scanning inefficiencies and increased cost.",
            remediation="Define a clustering key or re-cluster the table to reduce depth.",
            remediation_key="DEFINE_CLUSTER_KEY",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        violations = []
        # Use ACCOUNT_USAGE.TABLES so no current database is required (INFORMATION_SCHEMA is per-database)
        query = (
            f"""
        SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, CLUSTERING_KEY
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE DELETED IS NULL
        AND TABLE_TYPE = 'BASE TABLE'
        AND BYTES > {ONE_TB_BYTES}
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
        )
        try:
            cursor.execute(query)
            tables = cursor.fetchall()

            for row in tables:
                violations.extend(self._check_table_clustering(cursor, row))
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"ClusterKeyValidationCheck failed: {e}")

        return violations

    def _check_table_clustering(self, cursor: SnowflakeCursorProtocol, row: tuple) -> list[Violation]:
        catalog, schema, name, clustering_key = row
        # Fully qualify with quotes to handle special characters
        fqdn = f'"{catalog}"."{schema}"."{name}"'

        if not clustering_key:
            return [
                Violation(
                    self.id,
                    fqdn,
                    "Large table (> 1TB) is missing a defined clustering key.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]

        return self._check_clustering_depth(cursor, fqdn)

    def _check_clustering_depth(self, cursor: SnowflakeCursorProtocol, fqdn: str) -> list[Violation]:
        try:
            cursor.execute(f"SELECT SYSTEM$CLUSTERING_DEPTH('{fqdn}')")
            depth_row = cursor.fetchone()
            if depth_row and depth_row[0] is not None:
                try:
                    depth = float(depth_row[0])
                    if depth > CLUSTERING_DEPTH_THRESHOLD:
                        return [
                            Violation(
                                self.id,
                                fqdn,
                                f"Large table has high clustering depth: {depth:.2f} (Threshold: {CLUSTERING_DEPTH_THRESHOLD})",
                                self.severity,
                                remediation_key=self.remediation_key,
                            )
                        ]
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            if self.telemetry:
                self.telemetry.debug(f"Failed to check clustering depth for {fqdn}: {e}")
        return []


class RemoteSpillageCheck(Rule):
    """PERF_003: Detect queries with BYTES_SPILLED_TO_REMOTE_STORAGE > 0."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_003",
            "Remote Spillage (Critical)",
            Severity.CRITICAL,
            rationale="Remote spillage indicates a total exhaustion of local compute resources, leading to query performance degradation of 10x or more as data moves to slow blob storage.",
            remediation="Upgrade the warehouse size to increase local storage capacity.",
            remediation_key="UPSIZE_WAREHOUSE",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = """
        SELECT WAREHOUSE_NAME, COUNT(*) as spill_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE BYTES_SPILLED_TO_REMOTE_STORAGE > 0
        AND START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        GROUP BY 1
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    row[0],
                    f"Critical: Remote Spillage events in last 24h: {row[1]}",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"RemoteSpillageCheck failed: {e}")
            return []


class LocalSpillageCheck(Rule):
    """PERF_004: Detect queries with BYTES_SPILLED_TO_LOCAL_STORAGE > 0."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_004",
            "Local Spillage (Warning)",
            Severity.HIGH,
            rationale="Local spillage happens when memory is exhausted, forcing queries to use local SSD. This increases execution time and can be resolved by query optimization or larger warehouses.",
            remediation="Consider optimizing queries or increasing warehouse size.",
            remediation_key="OPTIMIZE_SPILL_QUERY",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = """
        SELECT WAREHOUSE_NAME, COUNT(*) as spill_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE BYTES_SPILLED_TO_LOCAL_STORAGE > 0
        AND BYTES_SPILLED_TO_REMOTE_STORAGE = 0 -- Isolate local-only spill
        AND START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        GROUP BY 1
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    row[0],
                    f"Performance: Local Spillage events in last 24h: {row[1]}",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"LocalSpillageCheck failed: {e}")
            return []


class QueryQueuingDetectionCheck(Rule):
    """PERF_002: Flag warehouses with sustained query queuing (WAF: signal under-provisioned warehouse)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_002",
            "Query Queuing Detection",
            Severity.MEDIUM,
            rationale="Sustained queuing indicates the warehouse may be under-provisioned; WAF recommends monitoring queued_overload_time.",
            remediation="Consider up-sizing the warehouse or splitting workload across multiple warehouses.",
            remediation_key="REDUCE_QUEUING",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = """
        SELECT WAREHOUSE_NAME, SUM(COALESCE(QUEUED_OVERLOAD_TIME, 0)) / 1000 AS QUEUED_SEC
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME
        HAVING SUM(COALESCE(QUEUED_OVERLOAD_TIME, 0)) > 60000
        ORDER BY QUEUED_SEC DESC
        LIMIT 20
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    row[0],
                    f"Sustained query queuing in last 7 days: {row[1]:.0f}s total queued time; consider up-sizing.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"QueryQueuingDetectionCheck failed: {e}")
            return []


class DynamicTableLagCheck(Rule):
    """PERF_010: Flag dynamic tables consistently exceeding TARGET_LAG (WAF: monitor lag and refresh metrics)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_010",
            "Dynamic Table Lag Check",
            Severity.MEDIUM,
            rationale="DTs that regularly exceed target lag delay downstream consumers; WAF recommends monitoring and adjusting lag or warehouse sizing.",
            remediation="Increase warehouse size for the dynamic table refresh or relax TARGET_LAG if acceptable.",
            remediation_key="DYNAMIC_TABLE_LAG",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = """
        SELECT DATABASE_NAME, SCHEMA_NAME, NAME, COUNT(*) AS OVER_LAG_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
        WHERE STATE = 'SUCCEEDED'
        AND REFRESH_END_TIME > COMPLETION_TARGET
        AND DATA_TIMESTAMP >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY DATABASE_NAME, SCHEMA_NAME, NAME
        HAVING COUNT(*) >= 2
        ORDER BY OVER_LAG_COUNT DESC
        LIMIT 50
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}.{row[2]}",
                    f"Dynamic table exceeded TARGET_LAG in {row[3]} refresh(es) in last 7 days; adjust warehouse or TARGET_LAG.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"DynamicTableLagCheck failed: {e}")
            return []


class ClusteringKeyQualityCheck(Rule):
    """PERF_011: Flag cluster key anti-patterns: >4 expressions, MOD usage, high-cardinality strings (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_011",
            "Clustering Key Quality",
            Severity.MEDIUM,
            rationale="WAF: Do not define a cluster key with more than four expressions; avoid MOD(); high-cardinality strings hurt pruning.",
            remediation="Reduce clustering expressions to ≤4; avoid MOD(); use date/numeric columns or low-cardinality codes.",
            remediation_key="CLUSTERING_KEY_QUALITY",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = (
            """
        SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, CLUSTERING_KEY
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE DELETED IS NULL AND TABLE_TYPE = 'BASE TABLE'
        AND CLUSTERING_KEY IS NOT NULL AND TRIM(CLUSTERING_KEY) != ''
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
            + """
        LIMIT 500
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                fq = f"{row[0]}.{row[1]}.{row[2]}"
                key = (row[3] or "").upper()
                if not key:
                    continue
                msg_parts = []
                # Count expressions (comma-separated, but watch for function args)
                expr_count = key.count(",") + 1
                if expr_count > 4:
                    msg_parts.append(f"more than 4 expressions ({expr_count})")
                if "MOD(" in key:
                    msg_parts.append("uses MOD() (anti-pattern)")
                if msg_parts:
                    violations.append(
                        Violation(
                            self.id,
                            fq,
                            f"Clustering key anti-pattern: {'; '.join(msg_parts)}.",
                            self.severity,
                            remediation_key=self.remediation_key,
                        )
                    )
            return violations
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"ClusteringKeyQualityCheck failed: {e}")
            return []


class WarehouseWorkloadIsolationCheck(Rule):
    """PERF_012: Flag warehouses serving multiple workload types (BI + ETL) - performance anti-pattern (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_012",
            "Warehouse Workload Isolation",
            Severity.MEDIUM,
            rationale="Directing all users and processes to a single large warehouse is a common performance anti-pattern; WAF recommends workload isolation.",
            remediation="Use separate warehouses for BI/dashboard vs ETL/batch; assign roles/warehouses by workload.",
            remediation_key="WORKLOAD_ISOLATION",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Heuristic: same warehouse running both short SELECTs (BI) and long COPY/INSERT (ETL) in last 7 days
        query = """
        SELECT WAREHOUSE_NAME,
               COUNT(DISTINCT CASE WHEN QUERY_TYPE IN ('SELECT', 'UNKNOWN') AND TOTAL_ELAPSED_TIME < 60000 THEN QUERY_ID END) AS short_selects,
               COUNT(DISTINCT CASE WHEN QUERY_TYPE IN ('INSERT', 'MERGE', 'COPY', 'UPDATE', 'DELETE') OR TOTAL_ELAPSED_TIME >= 60000 THEN QUERY_ID END) AS etl_like
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME
        HAVING short_selects >= 10 AND etl_like >= 5
        LIMIT 20
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    row[0],
                    "Warehouse serves mixed workload (short SELECTs and long/ETL queries); consider workload isolation.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"WarehouseWorkloadIsolationCheck failed: {e}")
            return []


class PoorPartitionPruningDetectionCheck(Rule):
    """PERF_005: Flag tables with consistently poor partition pruning ratio (WAF: compare partitions scanned to total)."""

    PRUNING_RATIO_THRESHOLD = 0.2  # Flag if < 20% of partitions pruned (i.e. > 80% scanned)
    MIN_PARTITIONS_TOTAL = 10

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_005",
            "Poor Partition Pruning Detection",
            Severity.MEDIUM,
            rationale="WAF: Large scanned count vs partitions total indicates opportunity for pruning improvement (clustering or filter pushdown).",
            remediation="Improve clustering key or query filters to increase partition pruning; consider automatic clustering or search optimization.",
            remediation_key="IMPROVE_PARTITION_PRUNING",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        min_part = self.MIN_PARTITIONS_TOTAL
        ratio = self.PRUNING_RATIO_THRESHOLD
        query = f"""
        SELECT DATABASE_NAME, SCHEMA_NAME, TABLE_NAME,
               SUM(PARTITIONS_SCANNED) AS TOTAL_SCANNED,
               SUM(PARTITIONS_PRUNED) AS TOTAL_PRUNED,
               SUM(PARTITIONS_SCANNED) + SUM(PARTITIONS_PRUNED) AS TOTAL_PARTITIONS
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_PRUNING_HISTORY
        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        {SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB}
        GROUP BY DATABASE_NAME, SCHEMA_NAME, TABLE_NAME
        HAVING (SUM(PARTITIONS_SCANNED) + SUM(PARTITIONS_PRUNED)) >= {min_part}
        AND SUM(PARTITIONS_SCANNED)::FLOAT / NULLIF(SUM(PARTITIONS_SCANNED) + SUM(PARTITIONS_PRUNED), 0) > (1 - {ratio})
        ORDER BY TOTAL_SCANNED DESC
        LIMIT 50
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}.{row[2]}",
                    f"Poor partition pruning: {row[3]:,} scanned vs {row[4]:,} pruned ({row[5]:,} total); consider clustering or filter optimization.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"PoorPartitionPruningDetectionCheck failed: {e}")
            return []


class QueryLatencySLOCheck(Rule):
    """PERF_013: Query Latency SLO - flag when P99 latency exceeds threshold (WAF: monitor P50/P90/P99)."""

    P99_THRESHOLD_SEC = 30
    LOOKBACK_DAYS = 7

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_013",
            "Query Latency SLO",
            Severity.MEDIUM,
            rationale="WAF: P99 latency indicates slowest 1% of queries; high P99 impacts user experience and may indicate undersized warehouses or inefficient queries.",
            remediation="Review long-running queries (EXPLAIN, query profile); consider larger warehouse or query optimization; set STATEMENT_TIMEOUT_IN_SECONDS to cap runaways.",
            remediation_key="QUERY_LATENCY_SLO",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = f"""
        WITH query_metrics AS (
            SELECT
                WAREHOUSE_NAME,
                QUERY_TYPE,
                EXECUTION_TIME / 1000.0 AS execution_time_sec
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -{self.LOOKBACK_DAYS}, CURRENT_TIMESTAMP())
            AND EXECUTION_STATUS = 'SUCCESS'
            AND QUERY_TYPE IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE')
            AND USER_NAME NOT IN ('SYSTEM', 'dataplane_service', 'dataplatform_admin')
            AND WAREHOUSE_NAME IS NOT NULL
        ),
        percentiles AS (
            SELECT
                WAREHOUSE_NAME,
                QUERY_TYPE,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY execution_time_sec) AS p50_sec,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY execution_time_sec) AS p90_sec,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY execution_time_sec) AS p99_sec,
                COUNT(*) AS query_count
            FROM query_metrics
            GROUP BY WAREHOUSE_NAME, QUERY_TYPE
            HAVING COUNT(*) >= 10
        )
        SELECT WAREHOUSE_NAME, QUERY_TYPE, P50_SEC, P90_SEC, P99_SEC, QUERY_COUNT
        FROM percentiles
        WHERE P99_SEC > {self.P99_THRESHOLD_SEC}
        ORDER BY P99_SEC DESC
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    f"{row[0]}|{row[1]}",
                    f"P99 latency {row[4]:.1f}s exceeds {self.P99_THRESHOLD_SEC}s (P50={row[2]:.1f}s, P90={row[3]:.1f}s, n={row[5]}) for warehouse {row[0]}, type {row[1]}.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"QueryLatencySLOCheck failed: {e}")
            return []
