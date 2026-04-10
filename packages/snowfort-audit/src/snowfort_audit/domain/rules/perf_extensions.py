from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class CacheContentionCheck(Rule):
    """PERF_009: Detects Cache Eviction by Mixed Workloads."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_009",
            "Cache Contention (Eviction)",
            Severity.MEDIUM,
            rationale="Heavy ETL queries evict cached data needed by interactive BI queries, causing slow cold starts.",
            remediation="Isolate BI workloads to a dedicated warehouse to preserve cache locality.",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Logic: High volume of data scanned by "Batch" style queries
        # AND Low cache hit rate for "Interactive" style queries on same WH.
        # Simplification for SQL:
        # Check WHs where:
        # 1. Significant 'COPY/INSERT/MERGE' activity (ETL)
        # 2. Significant 'SELECT' activity (BI)
        # 3. SELECT Cache Hit Rate is < 20%

        # We need complex subqueries or aggregation.
        # Mocking the rule logic based on provided tests structure expectation.

        query = """
        WITH WorkloadStats AS (
            SELECT
                WAREHOUSE_NAME,
                -- BI Proxy: SELECTs
                COUNT(CASE WHEN QUERY_TYPE = 'SELECT' THEN 1 END) as BI_COUNT,
                AVG(CASE WHEN QUERY_TYPE = 'SELECT' THEN PERCENTAGE_SCANNED_FROM_CACHE ELSE NULL END) as BI_CACHE_HIT,
                -- ETL Proxy: DML
                COUNT(CASE WHEN QUERY_TYPE != 'SELECT' THEN 1 END) as ETL_COUNT,
                SUM(CASE WHEN QUERY_TYPE != 'SELECT' THEN BYTES_SCANNED ELSE 0 END) as ETL_BYTES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
            GROUP BY 1
        )
        SELECT * FROM WorkloadStats
        WHERE BI_COUNT > 100 AND ETL_COUNT > 50
        AND BI_CACHE_HIT < 0.20 -- Low cache hit for BI
        AND ETL_BYTES > 10 * 1024 * 1024 * 1024 -- Significant ETL volume
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name = row[0]
                bi_count = row[1]
                bi_hit = row[2]
                etl_count = row[3]
                etl_bytes = row[4]

                violations.append(
                    Violation(
                        self.id,
                        wh_name,
                        f"Cache Contention: BI queries ({bi_count}) have low cache hit ({bi_hit:.1%}) while "
                        f"ETL queries ({etl_count}) scan massive data ({etl_bytes / 1024**3:.0f}GB).",
                        self.severity,
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
