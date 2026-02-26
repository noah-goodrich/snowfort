from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import SQL_EXCLUDE_SYSTEM_AND_SNOWFORT, Rule, Severity, Violation

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

# Removed Infrastructure import


class FutureGrantsAntiPatternCheck(Rule):
    """GOV_001: Flag usage of GRANT ... ON FUTURE SCHEMAS/TABLES."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_001",
            "Future Grants Anti-Pattern",
            Severity.MEDIUM,
            rationale="Future grants create security black boxes where access is automatically provisioned without audit trails, increasing the risk of unauthorized lateral movement.",
            remediation="Replace FUTURE GRANTS with explicit grants managed by an orchestrator or DCM tool.",
            remediation_key="SECURE_GRANTS",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # FUTURE_GRANTS are in a separate view usually, or GRANTS_TO_ROLES with specific flag
        query = """
        SELECT GRANTEE_NAME, GRANTED_ON
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE GRANTED_ON LIKE 'FUTURE_%'
        AND DELETED_ON IS NULL
        LIMIT 10
        """
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    row[0],
                    f"Uses Future Grants on {row[1]}. Prefer explicit DCM.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []


class ObjectDocumentationCheck(Rule):
    """GOV_002: Flag Production Tables/Views with missing comments."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_002",
            "Documentation Coverage",
            Severity.LOW,
            rationale="Missing metadata increases the cost of data discovery and leads to misuse of sensitive information, impacting both productivity and compliance.",
            remediation="Add comments to production objects using 'COMMENT ON TABLE ... IS ...'",
            remediation_key="FIX_DOCUMENTATION",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = (
            """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE TABLE_CATALOG LIKE '%_PROD%'
        AND DELETED IS NULL
        AND (COMMENT IS NULL OR COMMENT = '')
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
            + """
        LIMIT 20
        """
        )
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}",
                    "Missing object description (COMMENT).",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []


class AccountBudgetEnforcement(Rule):
    """GOV_003: Ensures a Snowflake Account Budget is active."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_003",
            "Account Budget Enforcement",
            Severity.CRITICAL,
            rationale="Without an account-level budget, a single runaway query or poorly configured pipeline can exhaust your entire credit allocation before manual detection.",
            remediation="Create an account-level budget in Snowsight or via SQL: 'CREATE BUDGET account_budget WITH TARGET_AMOUNT = ...'",
            remediation_key="CREATE_ACCOUNT_BUDGET",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Check for active budgets in ACCOUNT_USAGE
        query = """
        SELECT COUNT(*)
        FROM SNOWFLAKE.ACCOUNT_USAGE.BUDGETS
        WHERE DELETED_ON IS NULL
        """
        try:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            if count == 0:
                return [
                    Violation(
                        self.id,
                        "Account",
                        "No active Snowflake Budgets found.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                ]
            return []
        except Exception:
            # Fallback check for BUDGET_ALERTS if BUDGETS view is unavailable
            try:
                cursor.execute("SELECT COUNT(*) FROM SNOWFLAKE.BC_USAGE.BUDGET_ALERTS")
                count = cursor.fetchone()[0]
                if count == 0:
                    return [
                        Violation(
                            self.id,
                            "Account",
                            "No Snowflake Budgets found via BC_USAGE.",
                            self.severity,
                            remediation_key=self.remediation_key,
                        )
                    ]
                return []
            except Exception:
                return [
                    Violation(
                        self.id,
                        "Account",
                        "Snowflake Budgets feature not found or not accessible.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                ]


class SensitiveDataClassificationCoverageCheck(Rule):
    """GOV_004: Flag columns that likely contain PII but lack classification tags (WAF: classify/tag sensitive datasets).
    TODO: Consider Cortex (or similar) with a structured prompt for smarter PII vs metadata classification
    to reduce false positives on names like METRIC_NAME, TABLE_NAME, CONFIGURATION_NAME in system/catalog context.
    """

    # Heuristic column name patterns that often indicate PII/sensitive data.
    # Use specific name patterns (not %NAME% alone) to avoid false positives on METRIC_NAME, TABLE_NAME, etc.
    PII_COLUMN_PATTERNS = (
        "%EMAIL%",
        "%SSN%",
        "%SOCIAL%",
        "%PHONE%",
        "%TELEPHONE%",
        "%ADDRESS%",
        "%DOB%",
        "%BIRTH_DATE%",
        "%CREDIT_CARD%",
        "%CARD_NUMBER%",
        "%SALARY%",
        "%WAGE%",
        "%FIRST_NAME%",
        "%LAST_NAME%",
        "%FULL_NAME%",
        "%PERSON_NAME%",
        "%CUSTOMER_NAME%",
        "%EMPLOYEE_NAME%",
        "%PATIENT_NAME%",
        "%USER_NAME%",
        "%PATIENT%",
        "%HEALTH%",
    )

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_004",
            "Sensitive Data Classification Coverage",
            Severity.MEDIUM,
            rationale="Untagged PII columns prevent automated masking and drift detection; WAF recommends classifying and tagging sensitive datasets.",
            remediation="Apply a classification tag (e.g., PII, SENSITIVE) to columns that store personal or sensitive data; use Snowflake classification or manual tagging.",
            remediation_key="CLASSIFY_SENSITIVE_COLUMNS",
            telemetry=telemetry,
        )

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Find columns whose names match PII heuristics but have no sensitivity tag in TAG_REFERENCES.
        # Exclude system/tool DBs so we only flag user data; avoid noise from SNOWFLAKE catalog columns.
        query = (
            """
        SELECT c.TABLE_CATALOG, c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS c
        WHERE c.DELETED IS NULL
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT.replace("TABLE_CATALOG", "c.TABLE_CATALOG")
            + """
        AND (
            c.COLUMN_NAME ILIKE '%EMAIL%' OR c.COLUMN_NAME ILIKE '%SSN%' OR c.COLUMN_NAME ILIKE '%PHONE%'
            OR c.COLUMN_NAME ILIKE '%ADDRESS%' OR c.COLUMN_NAME ILIKE '%DOB%' OR c.COLUMN_NAME ILIKE '%BIRTH_DATE%'
            OR c.COLUMN_NAME ILIKE '%CREDIT_CARD%' OR c.COLUMN_NAME ILIKE '%CARD_NUMBER%'
            OR c.COLUMN_NAME ILIKE '%SALARY%' OR c.COLUMN_NAME ILIKE '%PATIENT%'
            OR c.COLUMN_NAME ILIKE '%FIRST_NAME%' OR c.COLUMN_NAME ILIKE '%LAST_NAME%' OR c.COLUMN_NAME ILIKE '%FULL_NAME%'
            OR c.COLUMN_NAME ILIKE '%PERSON_NAME%' OR c.COLUMN_NAME ILIKE '%CUSTOMER_NAME%' OR c.COLUMN_NAME ILIKE '%EMPLOYEE_NAME%'
            OR c.COLUMN_NAME ILIKE '%PATIENT_NAME%' OR c.COLUMN_NAME ILIKE '%USER_NAME%'
        )
        AND NOT EXISTS (
            SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
            WHERE t.DOMAIN = 'COLUMN' AND t.OBJECT_NAME = c.TABLE_CATALOG || '.' || c.TABLE_SCHEMA || '.' || c.TABLE_NAME
            AND t.COLUMN_NAME = c.COLUMN_NAME
            AND (t.TAG_NAME ILIKE '%PII%' OR t.TAG_NAME ILIKE '%SENSITIVE%' OR t.TAG_NAME ILIKE '%CLASSIFICATION%')
            AND t.OBJECT_DELETED IS NULL
        )
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            return [
                self.violation(
                    f"{row[0]}.{row[1]}.{row[2]}.{row[3]}",
                    "Column name suggests PII/sensitive data but has no classification tag.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"SensitiveDataClassificationCoverageCheck failed: {e}")
            return []
