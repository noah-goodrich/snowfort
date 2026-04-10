from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext


from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.rules._grants import (
    GRANTS_CACHE_WINDOW,
    GTR_GRANTED_ON,
    GTR_GRANTED_TO,
    GTR_GRANTEE_NAME,
    GTR_NAME,
    GTR_PRIVILEGE,
    GTR_TABLE_CATALOG,
    gtr_fetcher,
)

# Write privileges that should never appear on read-only roles/users.
_WRITE_PRIVILEGES = frozenset({"INSERT", "UPDATE", "DELETE", "TRUNCATE", "CREATE TABLE", "CREATE VIEW", "OWNERSHIP"})
_RO_LIMIT = 50  # Max violations to surface per rule (mirrors original SQL LIMIT)


class ServiceRoleScopeCheck(Rule):
    """SEC_007_ROLE: Ensure SVC_% roles can only access 1 database."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_007_ROLE",
            "Service Role Scope",
            Severity.HIGH,
            rationale="Service roles that can access multiple databases broaden the blast radius of a compromised credential and violate least-privilege isolation.",
            remediation="Revoke USAGE on databases the role should not access. Limit each SVC_% role to a single database: REVOKE USAGE ON DATABASE <name> FROM ROLE <role>.",
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
            if scan_context is not None:
                gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                db_count: dict[str, set[str]] = defaultdict(set)
                for row in gtr:
                    grantee = str(row[GTR_GRANTEE_NAME])
                    if (
                        grantee.upper().startswith("SVC_")
                        and str(row[GTR_PRIVILEGE]).upper() == "USAGE"
                        and str(row[GTR_GRANTED_ON]).upper() == "DATABASE"
                    ):
                        catalog = str(row[GTR_TABLE_CATALOG])
                        db_count[grantee].add(catalog)
                return [
                    Violation(self.id, role, f"Service Role has access to {len(dbs)} DBs (Limit: 1)", self.severity)
                    for role, dbs in db_count.items()
                    if len(dbs) > 1
                ]
            # Fallback: direct aggregation query.
            cursor.execute(
                "SELECT GRANTEE_NAME, COUNT(DISTINCT TABLE_CATALOG) as db_count"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
                " WHERE GRANTEE_NAME LIKE 'SVC_%'"
                " AND PRIVILEGE = 'USAGE' AND GRANTED_ON = 'DATABASE'"
                " AND DELETED_ON IS NULL"
                " GROUP BY 1 HAVING db_count > 1"
            )
            return [
                Violation(self.id, row[0], f"Service Role has access to {row[1]} DBs (Limit: 1)", self.severity)
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ServiceUserScopeCheck(Rule):
    """SEC_007_USER: Ensure Service Users have direct access to only 1 database."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_007_USER",
            "Service User Scope",
            Severity.HIGH,
            rationale="Service users with direct grants on multiple databases increase lateral movement risk and make access review difficult.",
            remediation="Revoke direct USAGE on databases the user should not access. Prefer granting privileges via a single SVC_ role: REVOKE USAGE ON DATABASE <name> FROM USER <user>.",
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
        # Privilege grants to users appear in GRANTS_TO_ROLES with GRANTED_TO = 'USER'.
        try:
            if scan_context is not None:
                gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                db_count: dict[str, set[str]] = defaultdict(set)
                for row in gtr:
                    grantee = str(row[GTR_GRANTEE_NAME])
                    if (
                        str(row[GTR_GRANTED_TO]).upper() == "USER"
                        and grantee.upper().startswith("SVC_")
                        and str(row[GTR_PRIVILEGE]).upper() == "USAGE"
                        and str(row[GTR_GRANTED_ON]).upper() == "DATABASE"
                    ):
                        catalog = str(row[GTR_TABLE_CATALOG])
                        db_count[grantee].add(catalog)
                return [
                    Violation(self.id, user, f"Service User has direct access to {len(dbs)} DBs", self.severity)
                    for user, dbs in db_count.items()
                    if len(dbs) > 1
                ]
            cursor.execute(
                "SELECT GRANTEE_NAME, COUNT(DISTINCT TABLE_CATALOG) as db_count"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
                " WHERE GRANTED_TO = 'USER' AND GRANTEE_NAME LIKE 'SVC_%'"
                " AND PRIVILEGE = 'USAGE' AND GRANTED_ON = 'DATABASE'"
                " AND DELETED_ON IS NULL"
                " GROUP BY 1 HAVING db_count > 1"
            )
            return [
                Violation(self.id, row[0], f"Service User has direct access to {row[1]} DBs", self.severity)
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ReadOnlyRoleIntegrityCheck(Rule):
    """SEC_008_ROLE: Ensure %_RO roles have no write privileges."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_008_ROLE",
            "Read-Only Role Integrity",
            Severity.CRITICAL,
            rationale="Read-only roles (e.g. %_RO, %_READER) with write privileges violate the principle of least privilege and can lead to accidental or malicious data modification.",
            remediation="Revoke INSERT, UPDATE, DELETE, TRUNCATE, or OWNERSHIP from the role. Use REVOKE <privilege> ON <object> FROM ROLE <role>.",
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
            if scan_context is not None:
                gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                violations = []
                for row in gtr:
                    grantee = str(row[GTR_GRANTEE_NAME]).upper()
                    privilege = str(row[GTR_PRIVILEGE]).upper()
                    if (grantee.endswith("_RO") or grantee.endswith("_READER")) and privilege in _WRITE_PRIVILEGES:
                        violations.append(
                            Violation(
                                self.id,
                                str(row[GTR_GRANTEE_NAME]),
                                f"Read-Only Role has '{row[GTR_PRIVILEGE]}' on {row[GTR_GRANTED_ON]} {row[GTR_NAME]}",
                                self.severity,
                            )
                        )
                        if len(violations) >= _RO_LIMIT:
                            break
                return violations
            cursor.execute(
                "SELECT GRANTEE_NAME, PRIVILEGE, GRANTED_ON, NAME"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
                " WHERE (GRANTEE_NAME LIKE '%_RO' OR GRANTEE_NAME LIKE '%_READER')"
                " AND PRIVILEGE IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'CREATE TABLE', 'CREATE VIEW', 'OWNERSHIP')"
                " AND DELETED_ON IS NULL"
                f" LIMIT {_RO_LIMIT}"
            )
            return [
                Violation(self.id, row[0], f"Read-Only Role has '{row[1]}' on {row[2]} {row[3]}", self.severity)
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class ReadOnlyUserIntegrityCheck(Rule):
    """SEC_008_USER: Ensure %_RO users have no write privileges."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_008_USER",
            "Read-Only User Integrity",
            Severity.CRITICAL,
            rationale="Read-only users (e.g. %_RO, %_READER) with write privileges bypass intended access controls and can cause data integrity issues.",
            remediation="Revoke INSERT, UPDATE, DELETE, TRUNCATE, or OWNERSHIP from the user. Use REVOKE <privilege> ON <object> FROM USER <user>.",
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
        # Privilege grants to users appear in GRANTS_TO_ROLES with GRANTED_TO = 'USER'.
        try:
            if scan_context is not None:
                gtr = scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                violations = []
                for row in gtr:
                    grantee = str(row[GTR_GRANTEE_NAME]).upper()
                    privilege = str(row[GTR_PRIVILEGE]).upper()
                    if (
                        str(row[GTR_GRANTED_TO]).upper() == "USER"
                        and (grantee.endswith("_RO") or grantee.endswith("_READER"))
                        and privilege in _WRITE_PRIVILEGES
                    ):
                        violations.append(
                            Violation(
                                self.id,
                                str(row[GTR_GRANTEE_NAME]),
                                f"Read-Only User has '{row[GTR_PRIVILEGE]}' check on {row[GTR_GRANTED_ON]}",
                                self.severity,
                            )
                        )
                        if len(violations) >= _RO_LIMIT:
                            break
                return violations
            cursor.execute(
                "SELECT GRANTEE_NAME, PRIVILEGE, GRANTED_ON, NAME"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES"
                " WHERE GRANTED_TO = 'USER'"
                " AND (GRANTEE_NAME LIKE '%_RO' OR GRANTEE_NAME LIKE '%_READER')"
                " AND PRIVILEGE IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'CREATE TABLE', 'CREATE VIEW', 'OWNERSHIP')"
                " AND DELETED_ON IS NULL"
                f" LIMIT {_RO_LIMIT}"
            )
            return [
                Violation(self.id, row[0], f"Read-Only User has '{row[1]}' check on {row[2]}", self.severity)
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# Q1 2026 Feature Gap Rules (Session 6) — SEC_018 – SEC_023
# ---------------------------------------------------------------------------

_PAT_MAX_EXPIRY_DAYS = 90  # Tokens expiring beyond this window are too long-lived


class ProgrammaticAccessTokenCheck(Rule):
    """SEC_018: Flag PATs with no expiry or expiry > 90 days."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_018",
            "Programmatic Access Token Governance",
            Severity.HIGH,
            rationale="Programmatic Access Tokens (PATs) without expiration or with very long lifetimes create persistent credential risk. A compromised long-lived token grants indefinite access.",
            remediation="Set token expiry ≤ 90 days: ALTER USER <user> SET RSA_PUBLIC_KEY_2 = ... or rotate via the PAT management API. Drop tokens without expiry: DROP PROGRAMMATIC ACCESS TOKEN <name>.",
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
                "SELECT TOKEN_NAME, USER_NAME, EXPIRES_AT"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.PROGRAMMATIC_ACCESS_TOKENS"
                " WHERE DELETED_ON IS NULL"
                "  AND (EXPIRES_AT IS NULL"
                f"   OR DATEDIFF('day', CURRENT_TIMESTAMP(), EXPIRES_AT) > {_PAT_MAX_EXPIRY_DAYS})"
            )
            violations: list[Violation] = []
            for row in cursor.fetchall():
                token_name, user_name, expires_at = row[0], row[1], row[2]
                if expires_at is None:
                    detail = f"PAT '{token_name}' for user '{user_name}' has no expiration"
                else:
                    detail = f"PAT '{token_name}' for user '{user_name}' expires > {_PAT_MAX_EXPIRY_DAYS} days from now"
                violations.append(Violation(self.id, str(user_name), detail, self.severity))
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class AIRedactPolicyCoverageCheck(Rule):
    """SEC_019: Sensitive-tagged columns without an AI_REDACT masking policy."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_019",
            "AI_REDACT Policy Coverage",
            Severity.MEDIUM,
            rationale="Columns tagged as sensitive (e.g. SNOWFLAKE.CORE.SEMANTIC_CATEGORY = PII/PHI/Sensitive) should have an AI_REDACT masking policy to prevent LLM-based exfiltration via Cortex functions.",
            remediation="Apply an AI_REDACT masking policy to each flagged column: ALTER TABLE <t> MODIFY COLUMN <c> SET MASKING POLICY <ai_redact_policy>.",
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
                "SELECT tr.OBJECT_DATABASE, tr.OBJECT_SCHEMA, tr.OBJECT_NAME, tr.COLUMN_NAME"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES tr"
                " WHERE tr.TAG_NAME IN ('SEMANTIC_CATEGORY', 'PRIVACY_CATEGORY')"
                "  AND tr.OBJECT_DELETED IS NULL"
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES pr"
                "    WHERE pr.REF_DATABASE_NAME = tr.OBJECT_DATABASE"
                "      AND pr.REF_SCHEMA_NAME = tr.OBJECT_SCHEMA"
                "      AND pr.REF_ENTITY_NAME = tr.OBJECT_NAME"
                "      AND pr.REF_COLUMN_NAME = tr.COLUMN_NAME"
                "      AND (pr.POLICY_NAME ILIKE '%REDACT%' OR pr.POLICY_NAME ILIKE '%AI%')"
                "  )"
                " LIMIT 100"
            )
            return [
                Violation(
                    self.id,
                    f"{row[0]}.{row[1]}.{row[2]}.{row[3]}",
                    f"Sensitive column '{row[3]}' in {row[0]}.{row[1]}.{row[2]} has no AI_REDACT masking policy",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class AuthorizationPolicyCheck(Rule):
    """SEC_020: Warehouses lacking an authorization policy."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_020",
            "Authorization Policy Coverage",
            Severity.MEDIUM,
            rationale="Authorization policies (Q1 2026 GA) restrict which roles may use a warehouse. Warehouses without an authorization policy can be used by any role that has USAGE, bypassing fine-grained query governance.",
            remediation="Create and attach an authorization policy: CREATE AUTHORIZATION POLICY <name> ...; ALTER WAREHOUSE <wh> SET AUTHORIZATION POLICY = <name>.",
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
                "SELECT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES"
                " WHERE DELETED_ON IS NULL"
                "  AND AUTHORIZATION_POLICY IS NULL"
                " ORDER BY NAME"
                " LIMIT 50"
            )
            return [
                Violation(
                    self.id,
                    str(row[0]),
                    f"Warehouse '{row[0]}' has no authorization policy",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class TrustCenterExtensionsCheck(Rule):
    """SEC_021: Unresolved HIGH/CRITICAL findings in Snowflake Trust Center."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_021",
            "Trust Center Findings",
            Severity.HIGH,
            rationale="Snowflake Trust Center surfaces CIS Benchmark and security scanner findings. Unresolved HIGH/CRITICAL findings represent known security gaps endorsed by Snowflake's own scanning.",
            remediation="Review Trust Center findings in the Snowsight UI (Admin > Trust Center) and remediate or accept with documented justification.",
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
                "SELECT FINDING_TYPE, SEVERITY, COUNT(*) AS cnt"
                " FROM SNOWFLAKE.TRUST_CENTER.FINDINGS"
                " WHERE SEVERITY IN ('HIGH', 'CRITICAL')"
                "  AND STATUS != 'RESOLVED'"
                " GROUP BY 1, 2"
                " ORDER BY SEVERITY, FINDING_TYPE"
            )
            return [
                Violation(
                    self.id,
                    str(row[0]),
                    f"Trust Center: {row[2]} unresolved {row[1]} finding(s) of type '{row[0]}'",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class PrivateLinkOnlyEnforcementCheck(Rule):
    """SEC_022: PrivateLink configured but public endpoint not restricted."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_022",
            "PrivateLink Enforcement",
            Severity.MEDIUM,
            rationale="Accounts that have PrivateLink configured but allow public connections defeat the isolation PrivateLink provides. ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS should be TRUE.",
            remediation="Enable PrivateLink enforcement: ALTER ACCOUNT SET ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS = TRUE. Ensure all clients are migrated to the private endpoint first.",
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
            # Check if PrivateLink is configured for this account.
            cursor.execute("SELECT SYSTEM$ALLOWLIST_PRIVATELINK()")
            rows = cursor.fetchall()
            if not rows or not rows[0][0]:
                return []  # No PrivateLink configured — rule not applicable.
            # Check if enforcement parameter is set.
            cursor.execute("SHOW PARAMETERS LIKE 'ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS' IN ACCOUNT")
            params = cursor.fetchall()
            for param in params:
                # SHOW PARAMETERS returns: key, value, default, description, ...
                if str(param[1]).upper() != "TRUE":
                    return [
                        Violation(
                            self.id,
                            "ACCOUNT",
                            "PrivateLink is configured but ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS is not TRUE",
                            self.severity,
                        )
                    ]
            return []
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class SnowparkContainerServicesSecurityCheck(Rule):
    """SEC_023: SPCS services without a documentation comment."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_023",
            "Snowpark Container Services Security",
            Severity.MEDIUM,
            rationale="SPCS services run arbitrary container workloads inside Snowflake. Services without a documentation comment (owner, purpose, external access justification) create governance blind spots and complicate incident response.",
            remediation="Add a comment to each flagged service: ALTER SERVICE <db>.<schema>.<name> SET COMMENT = '<owner>: <purpose>. External access: <yes/no and reason>'.",
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
            cursor.execute("SHOW SERVICES IN ACCOUNT")
            rows = cursor.fetchall()
            if not rows:
                return []
            # SHOW SERVICES columns vary; find the comment column by name if possible.
            # Heuristic: columns are name(0), status(1), ..., comment is typically last or near-last.
            # Use description from cursor if available, otherwise check col index 9 (typical).
            col_names = [d[0].upper() for d in cursor.description] if cursor.description else []
            comment_idx = next((i for i, n in enumerate(col_names) if "COMMENT" in n), -1)
            name_idx = next((i for i, n in enumerate(col_names) if n == "NAME"), 0)
            violations: list[Violation] = []
            for row in rows:
                svc_name = str(row[name_idx])
                comment = str(row[comment_idx]).strip() if comment_idx >= 0 and row[comment_idx] else ""
                if not comment:
                    violations.append(
                        Violation(
                            self.id,
                            svc_name,
                            f"SPCS service '{svc_name}' has no documentation comment",
                            self.severity,
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
