"""ScanExecutor protocol for abstracting rule execution strategies.

Enables switching between ThreadPoolExecutor (local CLI) and Snowpark task
execution (Native App) without changing the OnlineScanUseCase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from snowfort_audit.domain.rule_definitions import Rule, Violation


class ScanExecutor(Protocol):
    """Strategy for executing audit rules against a Snowflake account.

    Implementations:
    - ThreadedScanExecutor: Uses ThreadPoolExecutor for local CLI parallel scans
    - SnowparkScanExecutor: Uses Snowpark stored procedures for Native App execution
    """

    def execute_rules(
        self,
        rules: list[Rule],
        workers: int = 1,
    ) -> list[Violation]:
        """Execute all rules and return aggregated violations.

        Args:
            rules: The audit rules to execute.
            workers: Concurrency hint (implementations may ignore if not applicable).

        Returns:
            Aggregated list of violations from all rules.
        """
        ...
