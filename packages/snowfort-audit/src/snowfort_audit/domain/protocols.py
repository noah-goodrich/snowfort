from typing import Any, Protocol

from snowfort_audit._vendor.protocols import FileSystemProtocol, TelemetryPort

from .models import PricingConfig
from .results import AuditResult

__all__ = [
    "AuditRepositoryProtocol",
    "AuditResult",
    "FileSystemProtocol",
    "GovernanceProtocol",
    "ManifestRepositoryProtocol",
    "SQLValidatorProtocol",
    "SQLViolation",
    "TelemetryPort",
]


class SQLViolation(Protocol):
    """Protocol for a SQL linting violation."""

    line: int
    column: int
    code: str
    description: str

    def matches(self, pattern: str) -> bool:
        """Check if the violation description contains the pattern (case-insensitive)."""


class SQLValidatorProtocol(Protocol):
    """Protocol for a SQL validation engine."""

    def validate(self, sql: str) -> list[SQLViolation]:
        """Validate a SQL string and return violations."""


class PricingRepositoryProtocol(Protocol):
    """Protocol for fetching pricing information."""

    def get_pricing_config(self) -> PricingConfig:
        """Fetch the current pricing configuration."""


class GovernanceProtocol(Protocol):
    """Protocol for managing Snowflake governance objects (roles, grants)."""

    def provision_auditor_role(self, role: str, user: str, warehouse: str) -> None:
        """
        Provisions the auditor role with all necessary privileges.

        Args:
            role: The name of the role to create/provision (e.g. AUDITOR).
            user: The user to grant the role to.
            warehouse: The warehouse to grant usage on.
        """


class ManifestRepositoryProtocol(Protocol):
    """Protocol for loading manifest definitions."""

    def load_definitions(self, path: str) -> dict:
        """Load definitions from manifest file at path."""


class AISynthesizerProtocol(Protocol):
    """Protocol for synthesis of findings using AI."""

    def summarize(self, violations: list) -> str:
        """Provide executive summary."""


class RemediationProtocol(Protocol):
    """Protocol for generating remediation code."""

    def generate_sql_fix(self, violation: Any) -> str:
        """Generate SQL fix."""

    def generate_terraform_fix(self, violation: Any) -> str:
        """Generate Terraform fix."""


class CalculatorProtocol(Protocol):
    """Protocol for interrogating account for pricing metrics."""

    def get_inputs(self) -> dict:
        """Return pricing metrics dictionary."""


class AuditRepositoryProtocol(Protocol):
    """Protocol for fetching audit results."""

    def get_latest_audit_result(self) -> AuditResult:
        """Fetch the latest audit result containing violations and scorecard."""
