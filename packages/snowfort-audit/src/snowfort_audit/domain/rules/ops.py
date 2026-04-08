from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import WarehouseSpec
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class SLOThrottlerCheck(Rule):
    """OPS_005: Detect warehouses significantly faster than SLO (Oversized)."""

    def __init__(
        self, evaluator: FinancialEvaluator, target_p95_ms: int = 60000, telemetry: TelemetryPort | None = None
    ):  # Default 60s
        super().__init__(
            "OPS_005",
            "SLO Efficiency (Throttler)",
            Severity.LOW,
            rationale=(
                "Query performance that significantly exceeds SLO requirements indicates over-provisioned "
                "compute resources. While fast queries are good, paying for 'too much speed' wastes capital "
                "that could be allocated to high-value data initiatives elsewhere."
            ),
            remediation="Downsize the warehouse to reduce credits while maintaining acceptable performance.",
            telemetry=telemetry,
        )
        self.evaluator = evaluator
        self.target_p95_ms = target_p95_ms

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Identify warehouses where p95 is very low (< 20% of SLO)
        query = """
        SELECT
            WAREHOUSE_NAME,
            APPROX_PERCENTILE(EXECUTION_TIME, 0.95) as P95_MS,
            WAREHOUSE_SIZE,
            COUNT(*) as QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        AND EXECUTION_TIME > 0
        GROUP BY 1, 3
        HAVING QUERY_COUNT > 100 -- Significant sample
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name = row[0]
                p95_ms = row[1]
                wh_size = row[2]

                # Logic: If p95 < 20% of SLO, we are "Too Fast"
                if wh_size and wh_size.upper() != "X-SMALL" and p95_ms < (self.target_p95_ms * 0.2):
                    # Recommendation: Downsize
                    sizes = ["X-SMALL", "SMALL", "MEDIUM", "LARGE", "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"]
                    try:
                        # Suggest 1 step down
                        curr_idx = sizes.index(wh_size.upper())
                        target_size = sizes[max(0, curr_idx - 1)]

                        savings = self.evaluator.calculate_cost_delta(
                            WarehouseSpec(wh_size, "STANDARD"), WarehouseSpec(target_size, "STANDARD"), 1.0
                        )  # 1 hr sample

                        msg = (
                            f"Oversized: Warehouse '{wh_name}' p95 ({p95_ms:.0f}ms) "
                            f"<< SLO ({self.target_p95_ms}ms). Downsize to {target_size}. "
                            f"Projected Savings: {FinancialEvaluator.format_currency(savings)}/hr."
                        )

                        violations.append(Violation(self.id, wh_name, msg, self.severity))
                    except ValueError:
                        pass

            return violations
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"SLOThrottlerCheck failed: {e}")
            return []
