from typing import Any

from snowfort_audit.domain.protocols import AuditRepositoryProtocol
from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Severity, Violation


class SnowparkAuditRepository(AuditRepositoryProtocol):
    """
    Repository for fetching audit results via Snowpark.
    Handles both active Snowpark sessions and local mock fallback.
    """

    def __init__(self, session: Any | None):
        self.session = session

    def get_latest_audit_result(self) -> AuditResult:
        """Fetch latest violations and return aggregated result."""
        violations = self._fetch_violations()
        return AuditResult.from_violations(violations)

    def _fetch_violations(self) -> list[Violation]:
        if self.session:
            rows = self.session.table("CORE.AUDIT_RESULTS").collect()
            return [
                Violation(
                    rule_id=row["RULE_ID"],
                    resource_name=row["RESOURCE_NAME"],
                    message=row["MESSAGE"],
                    severity=Severity(row["SEVERITY"]),
                    remediation_key=row.get("REMEDIATION_KEY"),
                )
                for row in rows
            ]

        # Mock data for local development
        return [
            Violation(
                rule_id="PERF_001",
                resource_name="RAW.USERS",
                message="Missing Clustering Key",
                severity=Severity.HIGH,
            ),
            Violation(
                rule_id="SEC_003",
                resource_name="ACCOUNT",
                message="Public Network Policy Found",
                severity=Severity.CRITICAL,
            ),
            Violation(
                rule_id="COST_001",
                resource_name="COMPUTE_WH",
                message="Aggressive Auto-Suspend not set",
                severity=Severity.MEDIUM,
            ),
        ]
