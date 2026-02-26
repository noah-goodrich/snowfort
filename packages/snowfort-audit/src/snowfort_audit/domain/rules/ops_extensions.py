from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class ResizeChurnCheck(Rule):
    """OPS_006: Detects frequent manual warehouse resizing (Churn)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "OPS_006",
            "Resize Churn (Stability)",
            Severity.LOW,
            rationale="Frequent manual resizing (>5/day) indicates reactive management and lack of workload isolation.",
            remediation="Use separate warehouses for different workloads instead of constantly resizing one.",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Count ALTER WAREHOUSE SET WAREHOUSE_SIZE events
        query = """
        SELECT
            WAREHOUSE_NAME,
            COUNT(*) as RESIZE_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE QUERY_TEXT ILIKE 'ALTER WAREHOUSE%SET WAREHOUSE_SIZE%'
        AND START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        GROUP BY 1
        HAVING RESIZE_COUNT > 5
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name = row[0]
                count = row[1]

                violations.append(
                    Violation(
                        self.id,
                        wh_name,
                        f"Resize Churn: Warehouse '{wh_name}' was resized {count} times in 24h.",
                        self.severity,
                    )
                )
            return violations
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"ResizeChurnCheck failed: {e}")
            return []
