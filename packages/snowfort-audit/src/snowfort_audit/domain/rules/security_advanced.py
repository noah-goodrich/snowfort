from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext


from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation
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
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []


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
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []


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
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []


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
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []
