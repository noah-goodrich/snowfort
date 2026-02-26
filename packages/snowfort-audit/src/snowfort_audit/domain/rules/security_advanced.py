from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol


from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

# Removed Infrastructure import


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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Efficient approach: Query GRANTS_TO_ROLES
        query = """
        SELECT GRANTEE_NAME, COUNT(DISTINCT TABLE_CATALOG) as db_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE GRANTEE_NAME LIKE 'SVC_%'
        AND PRIVILEGE = 'USAGE'
        AND GRANTED_ON = 'DATABASE'
        AND DELETED_ON IS NULL
        GROUP BY 1
        HAVING db_count > 1
        """
        try:
            cursor.execute(query)
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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # GRANTS_TO_USERS only has role grants; privilege grants to users appear in GRANTS_TO_ROLES with GRANTED_TO = 'USER'
        query = """
        SELECT GRANTEE_NAME, COUNT(DISTINCT TABLE_CATALOG) as db_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE GRANTED_TO = 'USER'
        AND GRANTEE_NAME LIKE 'SVC_%'
        AND PRIVILEGE = 'USAGE'
        AND GRANTED_ON = 'DATABASE'
        AND DELETED_ON IS NULL
        GROUP BY 1
        HAVING db_count > 1
        """
        try:
            cursor.execute(query)
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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        query = """
        SELECT GRANTEE_NAME, PRIVILEGE, GRANTED_ON, NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE (GRANTEE_NAME LIKE '%_RO' OR GRANTEE_NAME LIKE '%_READER')
        AND PRIVILEGE IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'CREATE TABLE', 'CREATE VIEW', 'OWNERSHIP')
        AND DELETED_ON IS NULL
        LIMIT 50
        """
        try:
            cursor.execute(query)
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

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        # Privilege grants to users appear in GRANTS_TO_ROLES with GRANTED_TO = 'USER'
        query = """
        SELECT GRANTEE_NAME, PRIVILEGE, GRANTED_ON, NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE GRANTED_TO = 'USER'
        AND (GRANTEE_NAME LIKE '%_RO' OR GRANTEE_NAME LIKE '%_READER')
        AND PRIVILEGE IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'CREATE TABLE', 'CREATE VIEW', 'OWNERSHIP')
        AND DELETED_ON IS NULL
        LIMIT 50
        """
        try:
            cursor.execute(query)
            return [
                Violation(self.id, row[0], f"Read-Only User has '{row[1]}' check on {row[2]}", self.severity)
                for row in cursor.fetchall()
            ]
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
            return []
