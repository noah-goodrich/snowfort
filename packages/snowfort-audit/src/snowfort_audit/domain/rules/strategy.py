from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class IsolationPivotCheck(Rule):
    """COST_012: Strategic Advisor - Recommend Isolation over Upsizing."""

    # Elephant Factor: Queries 100x larger than average are considered 'Elephants' and should be isolated.
    ELEPHANT_FACTOR = 100

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_012",
            "Isolation Pivot (Elephant Detection)",
            Severity.MEDIUM,
            rationale=(
                "Heavy queries running on warehouses dominated by light queries cause "
                "contention and skew sizing requirements."
            ),
            remediation="Move heavy queries to a dedicated warehouse instead of resizing the current one.",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Logic: Find queries that are > 100x larger than the warehouse average
        query = """
        WITH WhStats AS (
            SELECT
                WAREHOUSE_NAME,
                AVG(BYTES_SCANNED) as AVG_BYTES,
                COUNT(*) as QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
            GROUP BY 1
        )
        SELECT
            q.WAREHOUSE_NAME,
            q.QUERY_ID,
            q.BYTES_SCANNED,
            w.AVG_BYTES,
            w.QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
        JOIN WhStats w ON q.WAREHOUSE_NAME = w.WAREHOUSE_NAME
        WHERE q.START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        AND q.BYTES_SCANNED > (w.AVG_BYTES * 100) -- Elephant Factor
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name = row[0]
                query_id = row[1]
                bytes_scanned = row[2] or 0
                avg_bytes = row[3] or 1

                # Double check ratio
                ratio = bytes_scanned / max(avg_bytes, 1)

                if ratio > self.ELEPHANT_FACTOR:
                    violations.append(
                        Violation(
                            self.id,
                            query_id,
                            f"Isolation Pivot: Query '{query_id}' scanned {bytes_scanned / 1024**3:.1f}GB "
                            f"(> {ratio:.0f}x warehouse avg). Don't resize '{wh_name}' for this; "
                            f"Move this query to a dedicated warehouse.",
                            self.severity,
                        )
                    )
            return violations
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"IsolationPivotCheck failed: {e}")
            return []
