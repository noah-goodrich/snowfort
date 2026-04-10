from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)


class WorkloadHeterogeneityCheck(Rule):
    """COST_011: Detects warehouses with mixed (Heterogeneous) workloads using Coefficient of Variation."""

    CV_THRESHOLD = 2.0

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_011",
            "Workload Heterogeneity (Mixed Uses)",
            Severity.MEDIUM,
            rationale="Warehouses handling both tiny lookups and massive scans are inefficient (Jack of all trades).",
            remediation="Split Batch and Interactive workloads to dedicated warehouses.",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT
            WAREHOUSE_NAME,
            STDDEV(BYTES_SCANNED) as STDDEV_BYTES,
            AVG(BYTES_SCANNED) as AVG_BYTES,
            STDDEV(EXECUTION_TIME) as STDDEV_TIME,
            AVG(EXECUTION_TIME) as AVG_TIME,
            COUNT(*) as QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
        AND EXECUTION_TIME > 0 AND BYTES_SCANNED > 0
        GROUP BY 1
        HAVING QUERY_COUNT > 1000
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name = row[0]
                std_bytes = float(row[1] or 0)
                avg_bytes = float(row[2] or 1)
                std_time = float(row[3] or 0)
                avg_time = float(row[4] or 1)

                cv_bytes = std_bytes / avg_bytes
                cv_time = std_time / avg_time

                if cv_bytes > self.CV_THRESHOLD or cv_time > self.CV_THRESHOLD:
                    violations.append(
                        Violation(
                            self.id,
                            wh_name,
                            f"Warehouse '{wh_name}' is a 'Jack of all trades' (CV Bytes={cv_bytes:.1f}, "
                            f"Time={cv_time:.1f}). Mixed workload detected.",
                            self.severity,
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
