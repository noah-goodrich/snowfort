from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

# Excluded DBs and system prefixes: filter at source in rule SQL and SHOW handling (see .cursorrules).
EXCLUDED_DATABASES_ALWAYS = frozenset(("SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"))
EXCLUDED_DATABASES_DEFAULT = EXCLUDED_DATABASES_ALWAYS | frozenset(("SNOWFORT",))
SYSTEM_OBJECT_PREFIXES = ("SYSTEM$",)
SQL_EXCLUDE_SYSTEM_DATABASES = " AND UPPER(TABLE_CATALOG) NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA')"
SQL_EXCLUDE_SYSTEM_AND_SNOWFORT = " AND UPPER(TABLE_CATALOG) NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA', 'SNOWFORT')"
SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB = (
    " AND UPPER(DATABASE_NAME) NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA', 'SNOWFORT')"
)
# For TAG_REFERENCES / POLICY_REFERENCES: OBJECT_NAME is "DB.SCHEMA.OBJECT" (e.g. MYDB.MYSCHEMA.MYTABLE).
SQL_EXCLUDE_OBJECT_NAME_SYSTEM_AND_SNOWFORT = (
    " AND UPPER(t.OBJECT_NAME) NOT LIKE 'SNOWFLAKE.%'"
    " AND UPPER(t.OBJECT_NAME) NOT LIKE 'SNOWFLAKE_SAMPLE_DATA.%'"
    " AND UPPER(t.OBJECT_NAME) NOT LIKE 'SNOWFORT.%'"
)


def is_excluded_db_or_warehouse_name(name: str | None) -> bool:
    """True if DB/warehouse name should be skipped (system or Snowfort). Use when iterating SHOW DATABASES/WAREHOUSES."""
    if not name:
        return False
    u = name.strip().upper()
    if u in EXCLUDED_DATABASES_DEFAULT:
        return True
    return any(u.startswith(p) for p in SYSTEM_OBJECT_PREFIXES)


if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.protocols import TelemetryPort

PILLAR_MAP: dict[str, str] = {
    "SEC": "Security",
    "COST": "Cost",
    "PERF": "Performance",
    "OPS": "Operations",
    "OP": "Operations",
    "GOV": "Governance",
    "STAT": "Security",
    "SQL": "Performance",
    "REL": "Reliability",
}

# Canonical order for WAF pillars in breakdown tables (all five + Governance).
# Pillars with no violations will appear with score 100 / grade A.
PILLAR_DISPLAY_ORDER: tuple[str, ...] = (
    "Security",
    "Cost",
    "Reliability",
    "Performance",
    "Operations",
    "Governance",
)

# Pillar colors for CLI/UI (Rich color names: deep blue for Security/Cost, aqua for the rest).
PILLAR_COLORS: dict[str, str] = {
    "Security": "blue",
    "Cost": "blue",
    "Reliability": "cyan",
    "Performance": "cyan",
    "Operations": "cyan",
    "Governance": "cyan",
    "Other": "dim",
}


def pillar_from_rule_id(rule_id: str) -> str:
    """Derive WAF pillar name from rule ID prefix."""
    for prefix, pillar in PILLAR_MAP.items():
        if rule_id.startswith(prefix):
            return pillar
    return "Other"


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class Violation:
    rule_id: str
    resource_name: str
    message: str
    severity: Severity
    pillar: str = ""
    remediation_key: str | None = None
    remediation_instruction: str | None = None


class Rule:
    def __init__(
        self,
        rule_id: str,
        name: str,
        severity: Severity,
        telemetry: TelemetryPort | None = None,
        rationale: str = "",
        remediation: str = "",
        remediation_key: str | None = None,
    ):
        self.id = rule_id
        self.name = name
        self.severity = severity
        self.rationale = rationale
        self.remediation = remediation
        self.remediation_key = remediation_key
        self.telemetry = telemetry

    @property
    def pillar(self) -> str:
        """WAF pillar derived from rule ID prefix."""
        return pillar_from_rule_id(self.id)

    def violation(
        self,
        resource_name: str,
        message: str,
        severity: Severity | None = None,
        remediation_instruction: str | None = None,
    ) -> Violation:
        """Helper to create a Violation with the rule's metadata."""
        return Violation(
            rule_id=self.id,
            resource_name=resource_name,
            message=message,
            severity=severity or self.severity,
            pillar=self.pillar,
            remediation_key=self.remediation_key,
            remediation_instruction=remediation_instruction or self.remediation or None,
        )

    def check(self, _resource: dict, _resource_name: str) -> list[Violation]:
        """Offline check against a dict definition."""
        return []

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        """Online check against live Snowflake connection."""
        return []

    def check_static(self, _file_content: str, _file_path: str) -> list[Violation]:
        """Static check against file content."""
        return []
