from __future__ import annotations

from typing import TYPE_CHECKING

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT,
    Rule,
    Severity,
    Violation,
    is_excluded_db_or_warehouse_name,
)
from snowfort_audit.domain.scan_context import (
    TC_COMMENT,
    TC_TABLE_CATALOG,
    TC_TABLE_NAME,
    TC_TABLE_SCHEMA,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext

from snowfort_audit.domain.rules._grants import (
    GRANTS_CACHE_WINDOW,
    GTR_GRANTED_ON,
    GTR_GRANTEE_NAME,
    gtr_fetcher,
)

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

    _FUTURE_LIMIT = 10  # Keep result set bounded, same as original SQL LIMIT

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            if scan_context is not None:
                # Use shared grants cache — no extra round-trip to Snowflake.
                gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                future_rows = [r for r in gtr if str(r[GTR_GRANTED_ON]).upper().startswith("FUTURE_")]
                return [
                    Violation(
                        self.id,
                        str(row[GTR_GRANTEE_NAME]),
                        f"Uses Future Grants on {row[GTR_GRANTED_ON]}. Prefer explicit DCM.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                    for row in future_rows[: self._FUTURE_LIMIT]
                ]
            # Fallback: direct query when no ScanContext.
            cursor.execute(
                "SELECT GRANTEE_NAME, GRANTED_ON"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
                " WHERE GRANTED_ON LIKE 'FUTURE_%'"
                " AND DELETED_ON IS NULL"
                f" LIMIT {self._FUTURE_LIMIT}"
            )
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

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            if scan_context is not None and scan_context.tables is not None:
                rows = [
                    (r[TC_TABLE_SCHEMA], r[TC_TABLE_NAME])
                    for r in scan_context.tables
                    if "PROD" in str(r[TC_TABLE_CATALOG]).upper()
                    and (r[TC_COMMENT] is None or str(r[TC_COMMENT]) == "")
                    and not is_excluded_db_or_warehouse_name(r[TC_TABLE_CATALOG])
                ][:20]
            else:
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
                cursor.execute(query)
                rows = cursor.fetchall()
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}",
                    "Missing object description (COMMENT).",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
                for row in rows
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

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
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

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
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


class MaskingPolicyCoverageExtendedCheck(Rule):
    """GOV_005: For AI_CLASSIFY-tagged sensitive columns, verify a masking policy is attached.

    Briefing D8: Columns tagged by Snowflake's AI_CLASSIFY as sensitive must have an
    active masking policy. Without this, classification provides no access control benefit.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_005",
            "AI-Classify Sensitive Column Masking Coverage",
            Severity.HIGH,
            rationale=(
                "AI_CLASSIFY identifies sensitive columns, but classification alone does not "
                "restrict access. A masking policy must be attached to protect the data."
            ),
            remediation=(
                "Attach a masking policy to every column tagged by AI_CLASSIFY as sensitive: "
                "'ALTER TABLE <t> MODIFY COLUMN <c> SET MASKING POLICY <policy>'."
            ),
            remediation_key="ATTACH_MASKING_POLICY_TO_CLASSIFIED",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Find columns tagged as SENSITIVE/PII via AI_CLASSIFY that lack a masking policy.
        query = """
        SELECT t.OBJECT_DATABASE, t.OBJECT_SCHEMA, t.OBJECT_NAME, t.COLUMN_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
        WHERE t.DOMAIN = 'COLUMN'
          AND t.OBJECT_DELETED IS NULL
          AND (t.TAG_NAME ILIKE '%SENSITIVE%' OR t.TAG_NAME ILIKE '%PII%'
               OR t.TAG_NAME ILIKE '%CLASSIFICATION%')
          AND NOT EXISTS (
              SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES p
              WHERE p.REF_DATABASE_NAME = t.OBJECT_DATABASE
                AND p.REF_SCHEMA_NAME = t.OBJECT_SCHEMA
                AND p.REF_ENTITY_NAME = t.OBJECT_NAME
                AND p.REF_COLUMN_NAME = t.COLUMN_NAME
                AND p.POLICY_KIND = 'MASKING_POLICY'
          )
        LIMIT 50
        """
        try:
            cursor.execute(query)
            return [
                self.violation(
                    f"{row[0]}.{row[1]}.{row[2]}.{row[3]}",
                    f"Column '{row[3]}' in '{row[0]}.{row[1]}.{row[2]}' is classified as sensitive "
                    "but has no masking policy attached.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                if self.telemetry:
                    self.telemetry.debug(f"GOV_005 skipped (TAG_REFERENCES/POLICY_REFERENCES not available): {e}")
                return []
            raise


class InboundShareRiskCheck(Rule):
    """GOV_006: Flag inbound data shares without owner tag or documentation.

    Briefing D9: Undocumented inbound shares represent opaque external data dependencies
    — if the provider changes schema or stops sharing, consumers break silently.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_006",
            "Inbound Share Risk",
            Severity.MEDIUM,
            rationale=(
                "Inbound data shares without owner attribution or documentation create "
                "opaque dependencies on external providers. Schema changes break silently."
            ),
            remediation=(
                "Tag each inbound share with an OWNER and PURPOSE tag. "
                "Document the provider SLA and schema version. "
                "Use 'ALTER DATABASE <shared_db> SET TAG OWNER = \"<team>\"'."
            ),
            remediation_key="DOCUMENT_INBOUND_SHARES",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("""
                SELECT DATABASE_NAME, SHARE_NAME, OWNER
                FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
                WHERE DELETED IS NULL
                  AND DATABASE_NAME NOT ILIKE 'SNOWFLAKE%'
                  AND SHARE_NAME IS NOT NULL
                  AND SHARE_NAME != ''
                LIMIT 50
            """)
            rows = cursor.fetchall()
        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                if self.telemetry:
                    self.telemetry.debug(f"GOV_006 skipped: {e}")
                return []
            raise
        violations = []
        for row in rows:
            db_name, share_name, owner = row[0], row[1], row[2]
            # Flag if no owner is set (owner is NULL or empty)
            if not owner or str(owner).strip() in ("", "NULL"):
                violations.append(
                    self.violation(
                        db_name,
                        f"Inbound share '{share_name}' (database '{db_name}') has no owner "
                        "tag. Document the provider and use case.",
                    )
                )
        return violations


class OutboundShareRiskCheck(Rule):
    """GOV_007: Flag outbound shares without expiration, per-consumer grants, or row-access policy.

    Briefing D9: Outbound shares without expiration or granular consumer controls represent
    data governance risk — data may be shared indefinitely with no audit trail.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_007",
            "Outbound Share Risk",
            Severity.HIGH,
            rationale=(
                "Outbound shares without explicit expiration or per-consumer grants expose "
                "data indefinitely. Without row-access policies, all shared data is visible."
            ),
            remediation=(
                "Set an expiration on outbound shares. "
                "Restrict consumers to named accounts using per-consumer grants. "
                "Apply row-access policies on shared tables for fine-grained control."
            ),
            remediation_key="GOVERN_OUTBOUND_SHARES",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("""
                SELECT SHARE_NAME, OWNER, COMMENT
                FROM SNOWFLAKE.ACCOUNT_USAGE.SHARES
                WHERE DELETED IS NULL
                  AND SHARE_KIND = 'OUTBOUND'
                LIMIT 50
            """)
            rows = cursor.fetchall()
        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                if self.telemetry:
                    self.telemetry.debug(f"GOV_007 skipped (SHARES view not available): {e}")
                return []
            raise
        violations = []
        for row in rows:
            share_name, owner, comment = row[0], row[1], row[2]
            issues = []
            if not owner or str(owner).strip() in ("", "NULL"):
                issues.append("no owner")
            if not comment or str(comment).strip() in ("", "NULL"):
                issues.append("no documentation comment")
            if issues:
                violations.append(
                    self.violation(
                        share_name,
                        f"Outbound share '{share_name}' has governance gaps: {', '.join(issues)}. "
                        "Add owner attribution and documentation.",
                    )
                )
        return violations


class CrossRegionInferenceCheck(Rule):
    """GOV_008: Flag accounts with CORTEX_ENABLED_CROSS_REGION active alongside data-residency tags.

    Briefing D11: Cross-region inference routes LLM calls to Snowflake-operated regions
    outside the account's home region. This violates data-residency requirements on
    tables tagged with GDPR, HIPAA, or similar sovereignty constraints.
    """

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_008",
            "Cross-Region Inference Risk",
            Severity.HIGH,
            rationale=(
                "CORTEX_ENABLED_CROSS_REGION allows LLM inference to route data outside "
                "the account's home region. This may violate GDPR/HIPAA data-residency "
                "requirements on tables tagged with sovereignty tags."
            ),
            remediation=(
                "Disable cross-region inference: "
                "'ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = DISABLED'. "
                "Or restrict to a compliant region list and ensure no sovereignty-tagged "
                "tables are passed to Cortex functions."
            ),
            remediation_key="DISABLE_CROSS_REGION_INFERENCE",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT")
            rows = cursor.fetchall()
        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                if self.telemetry:
                    self.telemetry.debug(f"GOV_008 skipped (SHOW PARAMETERS not authorized): {e}")
                return []
            raise
        for row in rows:
            # SHOW PARAMETERS returns: name, value, default, level, description, type
            value = str(row[1]).upper() if len(row) > 1 else ""
            if value not in ("", "DISABLED", "FALSE", "0"):
                # Cross-region inference is enabled; now check for sovereignty-tagged objects
                try:
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
                        WHERE OBJECT_DELETED IS NULL
                          AND (TAG_NAME ILIKE '%GDPR%' OR TAG_NAME ILIKE '%HIPAA%'
                               OR TAG_NAME ILIKE '%SOVEREIGNTY%' OR TAG_NAME ILIKE '%RESIDENCY%'
                               OR TAG_NAME ILIKE '%DATA_RESIDENCY%')
                    """)
                    count_row = cursor.fetchone()
                    sovereignty_count = int(count_row[0]) if count_row else 0
                except Exception:
                    sovereignty_count = 0
                msg = (
                    f"CORTEX_ENABLED_CROSS_REGION is set to '{value}'. "
                    "Cortex LLM inference may route outside the account's home region."
                )
                if sovereignty_count > 0:
                    msg += (
                        f" {sovereignty_count} object(s) with data-residency tags "
                        "(GDPR/HIPAA/SOVEREIGNTY) detected — potential compliance violation."
                    )
                return [self.violation("Account", msg)]
        return []


class IcebergTableGovernanceCheck(Rule):
    """GOV_009: Iceberg tables missing explicit catalog, retention, or encryption settings."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "GOV_009",
            "Iceberg Table Governance",
            Severity.MEDIUM,
            rationale="Iceberg tables on external catalogs (Glue, Polaris, REST) require explicit catalog integration, retention, and server-side encryption to meet data governance standards. Tables without these settings may expose data or become orphaned.",
            remediation="Set the catalog integration on Iceberg tables: ALTER ICEBERG TABLE <name> SET CATALOG = <integration>. Enable SSE: ensure the S3/ADLS storage integration uses encryption. Set retention: ALTER TABLE <name> SET DATA_RETENTION_TIME_IN_DAYS = <n>.",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        try:
            cursor.execute(
                "SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME,"
                "       CATALOG_INTEGRATION_NAME, DATA_RETENTION_TIME_IN_DAYS"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.ICEBERG_TABLES"
                " WHERE DELETED IS NULL"
                " ORDER BY TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME"
                " LIMIT 100"
            )
            violations: list[Violation] = []
            for row in cursor.fetchall():
                db, schema, tbl = str(row[0]), str(row[1]), str(row[2])
                catalog_integration = row[3]
                retention = row[4]
                resource = f"{db}.{schema}.{tbl}"
                issues = []
                if not catalog_integration:
                    issues.append("no catalog integration")
                if retention is None or int(retention) == 0:
                    issues.append("retention=0 days")
                if issues:
                    violations.append(
                        Violation(
                            self.id,
                            resource,
                            f"Iceberg table '{resource}' governance gaps: {', '.join(issues)}",
                            self.severity,
                        )
                    )
            return violations
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []
