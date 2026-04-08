from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext
from datetime import datetime, timezone

from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_OBJECT_NAME_SYSTEM_AND_SNOWFORT,
    Rule,
    Severity,
    Violation,
)

# Removed Infrastructure import


class AdminExposureCheck(Rule):
    """SEC_001: List all users with ACCOUNTADMIN, SECURITYADMIN, or SYSADMIN."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_001",
            "Admin Exposure",
            Severity.CRITICAL,
            rationale="Excessive administrative privileges increase the impact of credential theft, allowing attackers to delete data or perform lateral movement across the Snowflake account.",
            remediation=(
                "Revoke admin roles from users who do not need them. "
                "Ideally keep 2-3 ACCOUNTADMINs for redundancy. "
                "Daily tasks should be done via lower-privilege roles."
            ),
            remediation_key="REVOKE_ADMIN_ROLES",
            telemetry=telemetry,
        )

    MAX_ACCOUNT_ADMINS = 3
    WARN_ACCOUNT_ADMINS = 1
    MAX_GENERIC_ADMINS = 5

    def _check_account_admin(self, count: int) -> list[Violation]:
        if count > self.MAX_ACCOUNT_ADMINS:
            return [
                self.violation(
                    "Account",
                    f"Too many ACCOUNTADMINs: {count} detected. Best practice is 2-3.",
                    self.severity,
                )
            ]
        if count <= self.WARN_ACCOUNT_ADMINS:
            return [
                Violation(
                    self.id,
                    "Account",
                    f"Too few ACCOUNTADMINs: only {count} detected. Recommend at least 2 for redundancy.",
                    Severity.MEDIUM,
                    remediation_key=self.remediation_key,
                )
            ]
        return []

    def _check_generic_admin(self, role: str, count: int) -> list[Violation]:
        if count > self.MAX_GENERIC_ADMINS:
            return [
                Violation(
                    self.id,
                    "Account",
                    f"High number of {role}s ({count}). Consider using custom functional roles.",
                    Severity.MEDIUM,
                    remediation_key=self.remediation_key,
                )
            ]
        return []

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Implementation moved from rules.py
        violations = []

        strategies = {
            "ACCOUNTADMIN": self._check_account_admin,
            "SECURITYADMIN": lambda c: self._check_generic_admin("SECURITYADMIN", c),
            "SYSADMIN": lambda c: self._check_generic_admin("SYSADMIN", c),
        }

        for role, strategy in strategies.items():
            cursor.execute(f"SHOW GRANTS OF ROLE {role}")

            # Filter for USER grantees only
            users_with_role = [
                row[3]
                for row in cursor.fetchall()  # row[3] is grantee_name
                if row[2] == "USER"  # row[2] is granted_to
            ]

            violations.extend(strategy(len(users_with_role)))

        return violations


class MFAEnforcementCheck(Rule):
    """SEC_002: Flag any user with elevated privileges who do not have MFA enabled."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_002",
            "MFA Enforcement",
            Severity.CRITICAL,
            rationale="Administrative accounts without MFA are the primary vector for Snowflake account takeovers; using single-factor authentication on sensitive roles violates security best practices.",
            remediation=(
                "Enable Duo MFA for all users with admin roles. Users can self-enroll via the "
                "Use Snowsight (Account > Users) or ALTER USER to enable MFA and manage user properties. "
                "Validation: Check 'ext_authn_duo' column in 'SHOW USERS'."
            ),
            remediation_key="ENABLE_MFA",
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
        """Flag users with elevated roles missing MFA."""
        violations = []
        try:
            admin_users = self._get_admin_users(cursor)
            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()
            violations.extend(self._check_mfa_status(users, cols, admin_users))
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"MFAEnforcementCheck failed: {e}")
        return violations

    def _get_admin_users(self, cursor: SnowflakeCursorProtocol) -> set[str]:
        elevated_roles = ["ACCOUNTADMIN", "SYSADMIN", "SECURITYADMIN"]
        admin_users = set()
        for role in elevated_roles:
            cursor.execute(f"SHOW GRANTS OF ROLE {role}")
            users = {row[3] for row in cursor.fetchall() if row[2] == "USER"}
            admin_users.update(users)
        return admin_users

    def _check_mfa_status(self, users: list, cols: dict[str, int], admin_users: set[str]) -> list[Violation]:
        violations = []

        for user in users:
            name = user[cols["name"]]
            if name not in admin_users:
                continue

            user_type = user[cols["type"]] if "type" in cols else "PERSON"
            if user_type == "SERVICE":
                continue

            if "has_mfa" in cols:
                mfa_enabled = str(user[cols["has_mfa"]]).lower() == "true"
            else:
                mfa_enabled = str(user[cols["ext_authn_duo"]]).lower() == "true"

            bypass = user[cols.get("mins_to_bypass_mfa", -1)] if "mins_to_bypass_mfa" in cols else None
            bypass_active = bypass and str(bypass) != "null" and int(bypass) > 0

            if not mfa_enabled or bypass_active:
                details = []
                if not mfa_enabled:
                    details.append("MFA disabled")
                if bypass_active:
                    details.append(f"MFA Bypass active ({bypass} mins)")

                msg = f"Admin '{name}' (Type: {user_type}) security gap: {', '.join(details)}"
                violations.append(self.violation("User", msg))
        return violations


class NetworkPerimeterCheck(Rule):
    """SEC_003: Flag Account/Users bypassing Network Policies."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_003",
            "Network Perimeter",
            Severity.CRITICAL,
            rationale="Open network surfaces or missing IP restrictions allow attackers to use stolen credentials from anywhere in the world, circumscribing physical security controls.",
            remediation=(
                "Ensure an Account-level Network Policy is set. "
                "Audit User-level policies for unauthorized 0.0.0.0/0 allowlists."
            ),
            remediation_key="FIX_NETWORK_POLICY",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        violations = []
        violations.extend(self._check_account(cursor))
        violations.extend(self._check_users(cursor))
        return violations

    def _check_account(self, cursor: SnowflakeCursorProtocol) -> list[Violation]:
        try:
            # 1. Check Account Level
            cursor.execute("SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN ACCOUNT")
            res = cursor.fetchone()
            if not res or res[1] == "":
                return [self.violation("Account", "No Account-level Network Policy set")]

            # Deep Inspection
            policy_name = res[1]
            return self._describe_and_check_policy(cursor, "Account", policy_name)
        except Exception as e:
            if self.telemetry:
                self.telemetry.debug(f"Failed to check account network policy: {e}")
        return []

    def _describe_and_check_policy(
        self, cursor: SnowflakeCursorProtocol, resource_type: str, policy_name: str
    ) -> list[Violation]:
        """Runs DESCRIBE NETWORK POLICY and checks for 0.0.0.0/0."""
        try:
            cursor.execute(f"DESCRIBE NETWORK POLICY {policy_name}")
            rows = cursor.fetchall()
            # Columns: name, value, default, level, description
            for row in rows:
                if row[0].upper() == "ALLOWED_IP_LIST":
                    allow_list = row[1]
                    if "0.0.0.0/0" in allow_list:
                        return [
                            self.violation(
                                f"{resource_type} ({policy_name})",
                                f"Network Policy '{policy_name}' contains 0.0.0.0/0 (Internet Open).",
                            )
                        ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.debug(f"Failed to describe network policy {policy_name}: {e}")
        return []

    def _check_users(self, cursor: SnowflakeCursorProtocol) -> list[Violation]:
        # ACCOUNT_USAGE.USERS does not expose NETWORK_POLICY; user-level policy check not available via this view.
        # Account-level check in _check_account is the main signal. Return no violations for user bypass.
        return []


class PublicGrantsCheck(Rule):
    """SEC_004: Flag any GRANT ... TO ROLE PUBLIC."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_004",
            "Public Grants",
            Severity.HIGH,
            rationale="Granting sensitive privileges to the PUBLIC role exposes data to every user in the account, violating the principle of least privilege and increasing lateral movement risk.",
            remediation=(
                "Revoke privileges from PUBLIC using 'REVOKE <privilege> ON <object> FROM ROLE PUBLIC'. "
                "Grant to specific custom roles instead."
            ),
            remediation_key="REVOKE_PUBLIC_GRANTS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Check for dangerous privileges granted to PUBLIC
        query = "SHOW GRANTS TO ROLE PUBLIC"
        cursor.execute(query)
        grants = cursor.fetchall()
        violations = []

        # Allowed/Benign privileges for PUBLIC (minimal)
        allowed_privileges = {"USAGE"}

        for grant in grants:
            privilege = grant[1]
            obj_type = grant[2]
            obj_name = grant[3]

            # Skip sample data and system tables
            root_db = obj_name.split(".")[0]
            if root_db in ("SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"):
                continue

            if privilege not in allowed_privileges:
                violations.append(
                    self.violation(
                        f"ROLE PUBLIC ({obj_type})",
                        f"Excessive privilege '{privilege}' on {obj_type} '{obj_name}' granted to PUBLIC.",
                    )
                )
        return violations


class UserOwnershipCheck(Rule):
    """SEC_005: Flag objects (DBs, Warehouses) where OWNER is a User, not a Role."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_005",
            "User Ownership",
            Severity.MEDIUM,
            rationale="Objects owned by individual users rather than functional roles lead to 'Object Death' scenarios where resources become unmanageable if the user leaves the organization.",
            remediation=(
                "Transfer ownership to a functional role (e.g., SYSADMIN, LOADER_ROLE) using "
                "'GRANT OWNERSHIP ON <object> <name> TO ROLE <role> REVOKE CURRENT GRANTS'."
            ),
            remediation_key="TRANSFER_OWNERSHIP",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        """Check for databases/warehouses/integrations owned by users."""
        system_roles = {"SYSADMIN", "SECURITYADMIN", "ACCOUNTADMIN"}
        violations = []

        check_types = [
            ("DATABASES", "Database"),
            ("WAREHOUSES", "Warehouse"),
            ("INTEGRATIONS", "Integration"),
        ]

        for show_cmd, type_label in check_types:
            try:
                cursor.execute(f"SHOW {show_cmd}")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}

                # Owner column is usually 'owner' or index 5 for databases, but safer to use name lookup
                if "owner" not in cols:
                    continue

                for row in cursor.fetchall():
                    name = row[cols["name"]]
                    owner = row[cols["owner"]]

                    if name in ("SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA") or name.startswith("USER$"):
                        continue

                    if not owner:
                        continue

                    # Heuristic check
                    if owner not in system_roles and not owner.endswith("_ROLE") and not owner.endswith("_ADMIN"):
                        # Check if it's a known user?
                        # We assume if it isn't a role-looking name, it's a user.
                        violations.append(
                            self.violation(
                                f"{type_label}",
                                f"{type_label} '{name}' is owned by '{owner}'. Transfer to Role.",
                            )
                        )
            except Exception as e:
                if self.telemetry:
                    self.telemetry.debug(f"Failed to show {show_cmd}: {e}")
                continue

        return violations


class ServiceUserSecurityCheck(Rule):
    """SEC_006: Ensure Service Users use Key-Pair Auth, Rotated Keys, and No Password."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_006",
            "Service User Security",
            Severity.HIGH,
            rationale="Service accounts using passwords instead of RSA keys are vulnerable to credential stuffing and lack the entropy required for secure automated integrations.",
            remediation=(
                "Rotate RSA Keys regularly. Remove passwords using 'UNSET PASSWORD'. "
                "Rotate keys via Snowsight or ALTER USER ... SET RSA_PUBLIC_KEY_2 = ... ROTATE."
            ),
            remediation_key="SECURE_SERVICE_USER",
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
        violations = []
        try:
            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()

            if "type" not in cols:
                return []

            for user in users:
                user_type = user[cols["type"]]
                if user_type == "SERVICE":
                    name = user[cols["name"]]
                    has_pwd = str(user[cols["has_password"]]).lower() == "true"
                    has_key = str(user[cols["has_rsa_public_key"]]).lower() == "true"

                    if has_pwd:
                        violations.append(self.violation("User", f"Service User '{name}' has password. Use Keys only."))

                    if not has_key:
                        violations.append(
                            self.violation("User", f"Service User '{name}' missing RSA Key.", Severity.MEDIUM)
                        )

        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
        return violations


class ZombieUserCheck(Rule):
    """SEC_007: Flag users who haven't logged in for > 90 days."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_007",
            "Zombie Users",
            Severity.HIGH,
            rationale="Inactive accounts represent an unmonitored attack surface; disabling users who haven't logged in for >90 days is a primary control for identity security.",
            remediation="Disable user: 'ALTER USER <name> SET DISABLE = TRUE'.",
            remediation_key="DISABLE_STALE_USER",
            telemetry=telemetry,
        )

    NEVER_LOGGED_IN_THRESHOLD_DAYS = 30
    INACTIVE_THRESHOLD_DAYS = 90

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        violations = []
        try:
            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()
            now = datetime.now(timezone.utc)

            def _utc(dt: datetime | None) -> datetime | None:
                if dt is None:
                    return None
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt

            for user in users:
                name = user[cols["name"]]
                last_login = _utc(user[cols["last_success_login"]])

                if not last_login:
                    # Never logged in? Maybe new. Check created_on.
                    created = _utc(user[cols["created_on"]])
                    if created and (now - created).days > self.NEVER_LOGGED_IN_THRESHOLD_DAYS:
                        violations.append(
                            Violation(self.id, name, "User created >30 days ago but never logged in.", self.severity)
                        )
                    continue

                # Check 90 days (last_login already normalized to UTC)
                if (now - last_login).days > self.INACTIVE_THRESHOLD_DAYS:
                    violations.append(
                        Violation(
                            self.id, name, f"Zombie User: Inactive for {(now - last_login).days} days.", self.severity
                        )
                    )

        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
        return violations


class ZombieRoleCheck(Rule):
    """SEC_008: Flag Roles that are Orphans (no granted users/roles) or Empty (no privileges)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_008",
            "Zombie Roles",
            Severity.LOW,
            rationale=(
                "Roles that are not granted to anyone (Orphans) or have no privileges (Empty) "
                "clutter the RBAC model and can mask real security posture."
            ),
            remediation="Drop unused roles: 'DROP ROLE <name>'.",
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
        violations = []
        system_roles = {"ACCOUNTADMIN", "SECURITYADMIN", "SYSADMIN", "USERADMIN", "PUBLIC"}

        try:
            if scan_context is not None and scan_context.roles is not None:
                name_idx = scan_context.roles_cols.get("name", 1)
                roles = [r[name_idx] for r in scan_context.roles if r[name_idx] not in system_roles]
            else:
                cursor.execute("SHOW ROLES")
                roles = [row[1] for row in cursor.fetchall() if row[1] not in system_roles]

            # Batch: replace 2N SHOW GRANTS calls with 3 ACCOUNT_USAGE queries
            # Orphan set: roles that are granted TO a role or user
            cursor.execute(
                "SELECT DISTINCT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES "
                "WHERE GRANTED_ON = 'ROLE' AND DELETED_ON IS NULL"
            )
            granted_to_role: set[str] = {str(r[0]).upper() for r in cursor.fetchall()}

            cursor.execute("SELECT DISTINCT ROLE FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS WHERE DELETED_ON IS NULL")
            granted_to_user: set[str] = {str(r[0]).upper() for r in cursor.fetchall()}
            non_orphan_roles = granted_to_role | granted_to_user

            # Empty set: roles that have at least one grant (privilege or role)
            cursor.execute(
                "SELECT DISTINCT GRANTEE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES WHERE DELETED_ON IS NULL"
            )
            roles_with_grants: set[str] = {str(r[0]).upper() for r in cursor.fetchall()}

            for role in roles:
                role_upper = role.upper()
                if role_upper not in non_orphan_roles:
                    violations.append(
                        Violation(
                            self.id,
                            role,
                            f"Role '{role}' is an Orphan (not granted to any User or Role).",
                            self.severity,
                        )
                    )
                if role_upper not in roles_with_grants:
                    violations.append(
                        Violation(
                            self.id,
                            role,
                            f"Role '{role}' is Empty (no privileges or roles assigned to it).",
                            self.severity,
                        )
                    )

        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"Rule execution failed: {e}")
        return violations


class FederatedAuthenticationCheck(Rule):
    """SEC_011: Flag users with password auth who do not use federated/SSO or key-pair (WAF: modern auth)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_011",
            "Federated Authentication",
            Severity.MEDIUM,
            rationale="Static credentials increase risk of credential theft; WAF recommends SAML, Key Pair, or OAuth for all identities.",
            remediation="Adopt SSO (SAML/OAuth) for human users and key-pair or OAuth for service accounts; remove password-only auth.",
            remediation_key="ENABLE_FEDERATED_AUTH",
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
        violations = []
        try:
            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()
            idx_mfa = cols.get("has_mfa")
            idx_duo = cols.get("ext_authn_duo")
            idx_key = cols.get("has_rsa_public_key")
            idx_uid = cols.get("ext_authn_uid")
            idx_type = cols.get("type")
            for user in users:
                name = user[cols["name"]]
                user_type = str(user[idx_type] if idx_type is not None else "PERSON").upper()
                if user_type == "SERVICE":
                    continue
                has_pwd = str(user[cols["has_password"]]).lower() == "true"
                mfa_on = idx_mfa is not None and str(user[idx_mfa] or "").lower() == "true"
                ext_duo = idx_duo is not None and str(user[idx_duo] or "").lower() == "true"
                has_key = idx_key is not None and str(user[idx_key] or "").lower() == "true"
                has_sso = idx_uid is not None and bool(user[idx_uid])
                if has_pwd and not mfa_on and not ext_duo and not has_key and not has_sso:
                    violations.append(
                        self.violation("User", f"User '{name}' uses password-only auth; enable MFA/SSO or key-pair.")
                    )
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"FederatedAuthenticationCheck failed: {e}")
        return violations


class MFAAccountEnforcementCheck(Rule):
    """SEC_016: Require MFA for all users at account level (REQUIRE_MFA_FOR_ALL_USERS)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_016",
            "MFA Account Enforcement",
            Severity.CRITICAL,
            rationale="Account-level REQUIRE_MFA_FOR_ALL_USERS ensures every human user must use MFA; reduces credential theft risk.",
            remediation="ALTER ACCOUNT SET REQUIRE_MFA_FOR_ALL_USERS = TRUE;",
            remediation_key="REQUIRE_MFA_ACCOUNT",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW PARAMETERS LIKE 'REQUIRE_MFA_FOR_ALL_USERS' IN ACCOUNT")
            row = cursor.fetchone()
            if not row:
                return [
                    self.violation(
                        "Account",
                        "REQUIRE_MFA_FOR_ALL_USERS parameter not found or not set; enable MFA for all users.",
                    )
                ]
            # SHOW PARAMETERS: key, value, default, level, description
            actual = str(row[1]).strip().upper() if len(row) > 1 else ""
            if actual != "TRUE":
                return [
                    self.violation(
                        "Account",
                        f"REQUIRE_MFA_FOR_ALL_USERS is not TRUE (current: {actual}); set to TRUE to enforce MFA for all users.",
                    )
                ]
            return []
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"MFAAccountEnforcementCheck failed: {e}")
            return []


class CISBenchmarkScannerCheck(Rule):
    """SEC_017: Verify CIS Snowflake Benchmark scanner package is enabled in Trust Center (WAF: security posture)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_017",
            "CIS Benchmark Scanner",
            Severity.MEDIUM,
            rationale="Trust Center CIS Benchmark scanner evaluates account security against industry benchmarks; WAF recommends enabling it.",
            remediation="In Snowsight: Monitoring > Trust Center > Scanner Packages > enable CIS Snowflake Benchmarks.",
            remediation_key="ENABLE_CIS_SCANNER",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Try Trust Center views that list scanner packages (schema may be LOCAL or TRUST_CENTER)
        for view in (
            "SNOWFLAKE.LOCAL.TRUST_CENTER.SCANNER_PACKAGES",
            "SNOWFLAKE.TRUST_CENTER.SCANNER_PACKAGES",
        ):
            try:
                cursor.execute(f"SELECT * FROM {view}")
                for row in cursor.fetchall():
                    row_str = " ".join(str(v).upper() for v in (row or []))
                    if "CIS" in row_str and ("BENCHMARK" in row_str or "SNOWFLAKE" in row_str):
                        return []
                break
            except Exception as e:
                if self.telemetry:
                    err_str = str(e).lower()
                    if "does not exist" in err_str or "not authorized" in err_str or "002003" in err_str:
                        self.telemetry.debug(f"SEC_017: {view} not available: {e}")
                continue
        return [
            self.violation(
                "Account",
                "CIS Snowflake Benchmark scanner package not found or not enabled in Trust Center; enable it for security posture.",
            )
        ]


class PasswordPolicyCheck(Rule):
    """SEC_012: Verify at least one password policy exists and is applied (WAF: hardening authentication)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_012",
            "Password Policy",
            Severity.MEDIUM,
            rationale="Password policies enforce complexity and expiration; WAF recommends hardening authentication.",
            remediation="Create and apply a password policy: CREATE PASSWORD POLICY ... and assign to account or users.",
            remediation_key="APPLY_PASSWORD_POLICY",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW PASSWORD POLICIES IN ACCOUNT")
            policies = cursor.fetchall()
            if not policies:
                return [
                    self.violation(
                        "Account",
                        "No password policy defined in account; define and apply one for authentication hardening.",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"PasswordPolicyCheck failed: {e}")
            return []
        return []


class DataExfiltrationPreventionCheck(Rule):
    """SEC_013: Verify account parameters to prevent unload to inline URL and require storage integration (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_013",
            "Data Exfiltration Prevention",
            Severity.HIGH,
            rationale="Allowing unload to inline URLs or ad-hoc stages increases data exfiltration risk.",
            remediation=(
                "Set PREVENT_UNLOAD_TO_INLINE_URL = TRUE and REQUIRE_STORAGE_INTEGRATION_FOR_STAGE_OPERATIONS = TRUE "
                "in account parameters."
            ),
            remediation_key="DATA_EXFILTRATION_PARAMS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        violations = []
        params_to_check = [
            ("PREVENT_UNLOAD_TO_INLINE_URL", "TRUE", "Unload to inline URL not prevented"),
            (
                "REQUIRE_STORAGE_INTEGRATION_FOR_STAGE_OPERATIONS",
                "TRUE",
                "Stage creation without storage integration allowed",
            ),
        ]
        try:
            for param_name, expected_val, msg in params_to_check:
                cursor.execute(f"SHOW PARAMETERS LIKE '{param_name}' IN ACCOUNT")
                row = cursor.fetchone()
                if not row:
                    continue
                # SHOW PARAMETERS: key, value, default, level, description
                actual = str(row[1]).strip().upper() if len(row) > 1 else ""
                if actual != expected_val.upper():
                    violations.append(
                        self.violation("Account", f"Data exfiltration: {msg} (current value: {param_name}={actual}).")
                    )
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"DataExfiltrationPreventionCheck failed: {e}")
        return violations


class PrivateConnectivityCheck(Rule):
    """SEC_014: Check for private connectivity / network lock-down (WAF: leverage private networking)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_014",
            "Private Connectivity",
            Severity.LOW,
            rationale="WAF recommends private networking to keep traffic within a trusted network.",
            remediation="Consider Private Link or Snowflake Private Connectivity; restrict network policies to known IPs.",
            remediation_key="PRIVATE_CONNECTIVITY",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("SHOW PARAMETERS LIKE 'CLIENT_PREFETCH_THREADS' IN ACCOUNT")
            _ = cursor.fetchone()
            cursor.execute("SHOW NETWORK POLICIES")
            policies = cursor.fetchall()
            if not policies:
                return [
                    self.violation(
                        "Account",
                        "No network policy defined; consider restricting access via network policies or private connectivity.",
                    )
                ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"PrivateConnectivityCheck failed: {e}")
            return []
        return []


class DataMaskingPolicyCoverageCheck(Rule):
    """SEC_009: Find tagged-sensitive columns without masking policies (WAF: classify and apply masking)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_009",
            "Data Masking Policy Coverage",
            Severity.MEDIUM,
            rationale="Columns classified as sensitive should have masking policies; WAF recommends tag-based masking for scalability.",
            remediation="Apply a masking policy to the column or assign a tag-based masking policy that matches the column's classification tag.",
            remediation_key="APPLY_MASKING_POLICY",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT t.OBJECT_NAME, t.COLUMN_NAME, t.TAG_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
        WHERE t.DOMAIN = 'COLUMN'
        AND (t.TAG_NAME ILIKE '%PII%' OR t.TAG_NAME ILIKE '%SENSITIVE%' OR t.TAG_NAME ILIKE '%CLASSIFICATION%' OR t.TAG_NAME ILIKE '%CONFIDENTIAL%')
        AND t.OBJECT_DELETED IS NULL
        """
            + SQL_EXCLUDE_OBJECT_NAME_SYSTEM_AND_SNOWFORT
            + """
        AND NOT EXISTS (
            SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES p
            WHERE p.REF_ENTITY_DOMAIN IN ('TABLE', 'VIEW') AND p.POLICY_KIND = 'MASKING_POLICY'
            AND p.REF_ENTITY_NAME = t.OBJECT_NAME AND p.REF_COLUMN_NAME = t.COLUMN_NAME
        )
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            return [
                self.violation(
                    f"{row[0]}.{row[1]}",
                    f"Column has sensitivity tag '{row[2]}' but no masking policy applied.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"DataMaskingPolicyCoverageCheck failed: {e}")
            return []


class RowAccessPolicyCoverageCheck(Rule):
    """SEC_010: Identify tables in schemas with sensitive data that lack any RAP binding (WAF: hub-and-spoke RAP)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_010",
            "Row Access Policy Coverage",
            Severity.MEDIUM,
            rationale="Tables containing sensitive data should have row access policies; WAF recommends one policy per domain.",
            remediation="Create a row access policy and assign it to tables that hold sensitive or restricted data.",
            remediation_key="APPLY_ROW_ACCESS_POLICY",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Tables that have at least one column with a sensitivity tag but no RAP
        query = (
            """
        SELECT DISTINCT t.OBJECT_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
        WHERE t.DOMAIN = 'COLUMN'
        AND (t.TAG_NAME ILIKE '%PII%' OR t.TAG_NAME ILIKE '%SENSITIVE%' OR t.TAG_NAME ILIKE '%RESTRICTED%')
        AND t.OBJECT_DELETED IS NULL
        """
            + SQL_EXCLUDE_OBJECT_NAME_SYSTEM_AND_SNOWFORT
            + """
        AND NOT EXISTS (
            SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES p
            WHERE p.REF_ENTITY_DOMAIN IN ('TABLE', 'VIEW') AND p.POLICY_KIND = 'ROW_ACCESS_POLICY'
            AND p.REF_ENTITY_NAME = t.OBJECT_NAME
        )
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            return [
                self.violation(
                    row[0],
                    "Table has sensitivity-tagged columns but no row access policy.",
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"RowAccessPolicyCoverageCheck failed: {e}")
            return []


class SSOCoverageCheck(Rule):
    """SEC_015: In SSO-enabled accounts, flag users not using SSO (WAF: reduce password-based auth surface)."""

    SSO_MAJORITY_THRESHOLD = 0.5  # Treat account as SSO-enabled if >= 50% of users have ext_authn_uid

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_015",
            "SSO Coverage",
            Severity.MEDIUM,
            rationale="In SSO-enabled organizations, users created outside SSO bypass central identity and may pose a security risk.",
            remediation="Migrate non-SSO users to SSO or ensure they use key-pair auth and MFA; disable password-only logins where possible.",
            remediation_key="ENFORCE_SSO",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        try:
            cursor.execute("""
                SELECT NAME, LOGIN_NAME, EXT_AUTHN_UID
                FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
                WHERE DELETED_ON IS NULL
                AND DISABLED = FALSE
                AND LOGIN_NAME NOT LIKE '%SF$SERVICE%'
            """)
            rows = cursor.fetchall()
            if not rows:
                return []
            sso_users = sum(1 for r in rows if r[2] and str(r[2]).strip())
            total = len(rows)
            if total == 0 or sso_users / total < self.SSO_MAJORITY_THRESHOLD:
                return []
            non_sso = [r for r in rows if not r[2] or not str(r[2]).strip()]
            return [
                self.violation(
                    row[0],
                    f"User created outside SSO (login: {row[1]}); account appears SSO-enabled ({sso_users}/{total} users use SSO).",
                )
                for row in non_sso[:30]
            ]
        except Exception as e:
            if self.telemetry:
                self.telemetry.error(f"SSOCoverageCheck failed: {e}")
            return []
