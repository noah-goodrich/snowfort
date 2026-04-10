from __future__ import annotations

from typing import TYPE_CHECKING, Any

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import WarehouseSpec
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.warehouse_specs import get_warehouse_specs

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class WorkloadEfficiencyCheck(Rule):
    """PERF_006: Data-Driven Oversizing Detection (The Pincer)."""

    USAGE_RATIO_THRESHOLD = 0.2

    def __init__(self, evaluator: FinancialEvaluator, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_006",
            "Workload Efficiency (Oversized)",
            Severity.MEDIUM,
            rationale=(
                "Parallelism is the currency of Snowflake performance. If a query scans very few partitions "
                "on a large warehouse, it results in wasted throughput capacity. Right-sizing ensures you "
                "are only paying for the parallelism you actually use, without sacrificing performance."
            ),
            remediation="Downsize the warehouse or move the query to a smaller warehouse.",
            telemetry=telemetry,
        )
        self.evaluator = evaluator

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Identify oversized queries:
        query = """
        SELECT
            WAREHOUSE_NAME,
            PARTITIONS_SCANNED,
            BYTES_SCANNED,
            QUERY_ID,
            WAREHOUSE_SIZE
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE WAREHOUSE_SIZE IS NOT NULL
        AND WAREHOUSE_SIZE != 'X-SMALL'
        AND START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        AND EXECUTION_TIME < 5000 -- Fast queries only (Safety)
        LIMIT 100
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                violation = self._evaluate_efficiency(row)
                if violation:
                    violations.append(violation)
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc

    def _evaluate_efficiency(self, row: Any) -> Violation | None:
        partitions = row[1]
        bytes_scanned = row[2]
        query_id = row[3]
        wh_size = row[4]

        specs = get_warehouse_specs(wh_size)
        nodes = specs["nodes"]
        parallelism_capacity = nodes * 40
        usage_ratio = partitions / max(parallelism_capacity, 1)

        tier_satisfied = self._is_tier_satisfied(wh_size, bytes_scanned)

        if usage_ratio < self.USAGE_RATIO_THRESHOLD and not tier_satisfied:
            target_size = "X-Small"
            if bytes_scanned > 1 * 1024**3:
                target_size = "Small"

            savings = self.evaluator.calculate_cost_delta(
                WarehouseSpec(wh_size, "STANDARD"), WarehouseSpec(target_size, "STANDARD"), 1.0
            )
            msg = (
                f"Oversized: Query '{query_id}' on {wh_size} used {usage_ratio:.1%} of node parallelism "
                f"and scanned {bytes_scanned / 1024**3:.2f}GB. "
                f"Move to {target_size}. "
                f"Projected Savings: {FinancialEvaluator.format_currency(savings)}/hr."
            )
            return Violation(self.id, query_id, msg, self.severity)
        return None

    def _is_tier_satisfied(self, wh_size: str, bytes_scanned: int) -> bool:
        if wh_size in ["LARGE", "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"]:
            if bytes_scanned < 100 * 1024**3:
                return False
        elif (wh_size == "MEDIUM" and bytes_scanned < 20 * 1024**3) or (
            wh_size == "SMALL" and bytes_scanned < 1 * 1024**3
        ):
            return False
        return True


class SpillingMemoryCheck(Rule):
    """PERF_003_SMART: Detection of Undersized Warehouses via Memory Limits."""

    SPILL_RATIO_THRESHOLD = 0.2

    def __init__(self, evaluator: FinancialEvaluator, telemetry: TelemetryPort | None = None):
        super().__init__(
            "PERF_003_SMART",
            "Reliability (Undersized)",
            Severity.CRITICAL,
            rationale=(
                "Remote spillage is the single most expensive performance failure in Snowflake. It indicates "
                "that the warehouse's local SSD and RAM were both exhausted, forcing data to be written and "
                "read from slow remote storage. This results in catastrophic slowdowns and ballooning costs."
            ),
            remediation="Upsize warehouse or switch to Snowpark-Optimized for higher RAM-to-CPU ratio.",
            telemetry=telemetry,
        )
        self.evaluator = evaluator

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT
            WAREHOUSE_NAME,
            WAREHOUSE_TYPE,
            BYTES_SPILLED_TO_REMOTE_STORAGE,
            BYTES_SCANNED,
            0.1 as AVG_CPU_PLACEHOLDER,
            QUERY_ID,
            WAREHOUSE_SIZE
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE BYTES_SPILLED_TO_REMOTE_STORAGE > 0
        AND START_TIME > DATEADD('day', -1, CURRENT_TIMESTAMP())
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                violation = self._evaluate_spilling(row)
                if violation:
                    violations.append(violation)
            return violations
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"SpillingMemoryCheck failed: {e}")
            return []

    def _evaluate_spilling(self, row: Any) -> Violation | None:
        wh_type = row[1] or "STANDARD"
        spilled_remote = row[2]
        bytes_scanned = row[3]
        query_id = row[5]
        wh_size = row[6]

        target_size, target_type = self._determine_spill_target(wh_size, wh_type, spilled_remote, bytes_scanned)

        cost_impact = self.evaluator.calculate_cost_delta(
            WarehouseSpec(wh_size, wh_type), WarehouseSpec(target_size, target_type), 1.0
        )
        rec_msg = f"Upgrade to {target_size} ({target_type})"
        if wh_type != target_type:
            rec_msg = f"Switch to {target_type} {target_size} (16x RAM)"

        msg = (
            f"Undersized: Query '{query_id}' spilled {spilled_remote / 1024**3:.2f}GB (Remote). "
            f"{rec_msg}. Projected Cost: {FinancialEvaluator.format_currency(cost_impact)}/hr."
        )
        return Violation(self.id, query_id, msg, self.severity)

    def _determine_spill_target(
        self, wh_size: str, wh_type: str, spilled_remote: int, bytes_scanned: int
    ) -> tuple[str, str]:
        spill_ratio = spilled_remote / max(bytes_scanned, 1)
        target_size = wh_size
        target_type = wh_type
        is_standard = "STANDARD" in wh_type.upper()

        if is_standard and spill_ratio > self.SPILL_RATIO_THRESHOLD:
            target_type = "SNOWPARK-OPTIMIZED"
        else:
            sizes = ["X-SMALL", "SMALL", "MEDIUM", "LARGE", "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"]
            try:
                curr_idx = sizes.index(wh_size.upper())
                if curr_idx < len(sizes) - 1:
                    target_size = sizes[curr_idx + 1]
            except ValueError:
                pass
        return target_size, target_type
