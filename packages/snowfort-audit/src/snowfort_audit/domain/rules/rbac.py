"""Directive C — RBAC Topology & Role Hierarchy rules.

SEC_001a  Admin Grant Count         — too many users with ACCOUNTADMIN/SECURITYADMIN/SYSADMIN
SEC_001b  Dormant Admin Accounts    — admin users inactive > threshold days
SEC_001c  Admin As Default Role     — users whose default_role is an admin role
SEC_001d  Legacy Identity Dup.      — duplicate bare-name / email-name admin accounts
SEC_024   Orphan Role Ratio         — fraction of custom roles with zero grants
SEC_025   God Role Detection        — roles with excessive privilege span
SEC_026   Privilege Concentration   — Gini coefficient of role privilege distribution
SEC_027   Role Flow Validation      — users directly granted DBO/DDL-layer roles
SEC_028   User Role Explosion       — users with > threshold direct role grants
SEC_029   Incomplete Dept. Roles    — functional roles with no parent business-layer role
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import RbacThresholds, SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    FindingCategory,
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.rules._grants import (
    ADMIN_ROLES,
    GRANTS_CACHE_WINDOW,
    GTR_GRANTED_ON,
    GTR_GRANTED_ON_ROLE,
    GTR_GRANTEE_NAME,
    GTR_NAME,
    GTR_PRIVILEGE,
    GTR_TABLE_CATALOG,
    GTU_GRANTEE_NAME,
    GTU_ROLE,
    admin_role_user_counts,
    admin_users_from_context,
    build_role_graph,
    gtr_fetcher,
    gtu_fetcher,
    role_privilege_counts,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import Row, ScanContext


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _default_rbac(conventions: SnowfortConventions | None) -> RbacThresholds:
    """Return the RbacThresholds from conventions, or defaults when conventions is None."""
    if conventions is None:
        return RbacThresholds()
    return conventions.thresholds.rbac


def _gini(values: list[float]) -> float:
    """Compute the Gini coefficient for a list of non-negative floats.

    Returns a float in [0, 1].  Returns 0.0 for empty or zero-sum lists.
    """
    if not values:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    n = len(values)
    sorted_vals = sorted(values)
    weighted_sum = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


# ---------------------------------------------------------------------------
# SEC_001a — Admin Grant Count
# ---------------------------------------------------------------------------


class AdminGrantCountCheck(Rule):
    """SEC_001a: Flag when too many users hold ACCOUNTADMIN/SECURITYADMIN/SYSADMIN."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_001a",
            "Admin Grant Count",
            Severity.HIGH,
            rationale=(
                "An excess of users with ACCOUNTADMIN, SECURITYADMIN, or SYSADMIN greatly increases "
                "blast radius from credential theft or insider threat. Best practice is 2-3 ACCOUNTADMINs "
                "and a small number of other admin-role holders."
            ),
            remediation=(
                "Revoke admin roles from users who do not require them. "
                "Keep 2-3 ACCOUNTADMINs; use functional roles for day-to-day operations."
            ),
            remediation_key="REVOKE_ADMIN_ROLES",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtr = (
                scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                if scan_context
                else ()
            )
            gtu = (
                scan_context.get_or_fetch("GRANTS_TO_USERS", GRANTS_CACHE_WINDOW, gtu_fetcher(cursor))
                if scan_context
                else ()
            )
            role_users = admin_role_user_counts(gtr, gtu)

            max_admins = self._thresholds.max_account_admins
            aa_count = len(role_users["ACCOUNTADMIN"])
            if aa_count > max_admins:
                violations.append(
                    self.violation(
                        "Account",
                        f"Too many ACCOUNTADMINs: {aa_count} detected (threshold: {max_admins}). "
                        "Reduce to 2-3 using functional roles for daily operations.",
                    )
                )
            elif aa_count <= 1:
                violations.append(
                    self.violation(
                        "Account",
                        f"Too few ACCOUNTADMINs: only {aa_count} detected. "
                        "Recommend at least 2 for break-glass redundancy.",
                        severity=Severity.MEDIUM,
                    )
                )

            for role in ("SECURITYADMIN", "SYSADMIN"):
                count = len(role_users[role])
                if count > max_admins * 2:
                    violations.append(
                        self.violation(
                            "Account",
                            f"High number of {role}s: {count} detected. "
                            "Consider narrower functional roles to limit privilege blast radius.",
                            severity=Severity.MEDIUM,
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_001b — Dormant Admin Accounts
# ---------------------------------------------------------------------------


class DormantAdminAccountsCheck(Rule):
    """SEC_001b: Flag admin users who have never logged in or are inactive."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_001b",
            "Dormant Admin Accounts",
            Severity.HIGH,
            rationale=(
                "Admin accounts that have never logged in or have been idle for an extended period "
                "represent unmonitored attack surface. A dormant ACCOUNTADMIN can be compromised "
                "silently; disabling unused admin accounts reduces the blast radius from credential theft."
            ),
            remediation=(
                "Disable or revoke admin roles from users who haven't logged in recently: "
                "'ALTER USER <name> SET DISABLED = TRUE' or "
                "'REVOKE ROLE ACCOUNTADMIN FROM USER <name>'."
            ),
            remediation_key="DISABLE_DORMANT_ADMIN",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)
        self._zombie_days: int = conventions.thresholds.zombie_user_days if conventions is not None else 90
        self._never_logged_in_days: int = 30

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            admin_users = admin_users_from_context(cursor, scan_context)
            sso_enforced = scan_context.sso_enforced if scan_context is not None else None

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
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

            for user in users:
                name = user[cols["name"]]
                if name not in admin_users:
                    continue

                last_login = _utc(user[cols.get("last_success_login", -1)] if "last_success_login" in cols else None)

                # Severity: CRITICAL if has_password (active credential) and SSO enforced,
                # otherwise HIGH for admins.
                has_pwd_col = cols.get("has_password")
                has_pwd = has_pwd_col is not None and str(user[has_pwd_col] or "").lower() == "true"
                sev = Severity.CRITICAL if (sso_enforced and has_pwd) else self.severity

                if last_login is None:
                    created_col = cols.get("created_on")
                    created = _utc(user[created_col]) if created_col is not None else None
                    if created and (now - created).days > self._never_logged_in_days:
                        violations.append(
                            self.violation(
                                name,
                                f"Admin user created {(now - created).days} days ago but never logged in.",
                                severity=sev,
                            )
                        )
                    continue

                inactive_days = (now - last_login).days
                if inactive_days > self._zombie_days:
                    violations.append(
                        self.violation(
                            name,
                            f"Admin user inactive for {inactive_days} days (threshold: {self._zombie_days}).",
                            severity=sev,
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_001c — Admin As Default Role
# ---------------------------------------------------------------------------


class AdminAsDefaultRoleCheck(Rule):
    """SEC_001c: Flag users whose default_role is ACCOUNTADMIN or SECURITYADMIN."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_001c",
            "Admin As Default Role",
            Severity.HIGH,
            rationale=(
                "When a user's default role is an admin role, every new session automatically "
                "inherits maximum privileges. This increases the risk of accidental destructive "
                "operations and widens the blast radius for compromised sessions."
            ),
            remediation=(
                "Change the user's default role to a functional role: "
                "'ALTER USER <name> SET DEFAULT_ROLE = <functional_role>'."
            ),
            remediation_key="CHANGE_DEFAULT_ROLE",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()

            default_role_col = cols.get("default_role")
            name_col = cols.get("name")
            if default_role_col is None or name_col is None:
                return []

            for user in users:
                name = user[name_col]
                default_role = str(user[default_role_col] or "").upper()
                if default_role in ADMIN_ROLES:
                    violations.append(
                        self.violation(
                            name,
                            f"User default_role is '{default_role}'; every session starts with admin privileges.",
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_001d — Legacy Identity Duplication
# ---------------------------------------------------------------------------


class LegacyIdentityDuplicationCheck(Rule):
    """SEC_001d: Flag duplicate bare-name / email-name admin accounts.

    Detects cases where the same person has two accounts: a legacy bare-name
    account (e.g. ALICE) and a modern email-format account (ALICE@CORP.COM).
    When both hold admin roles, the legacy account is an orphaned attack surface.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_001d",
            "Legacy Identity Duplication",
            Severity.CRITICAL,
            rationale=(
                "Duplicate admin identities (legacy bare-name + modern email-name for the same person) "
                "indicate migration debt. Legacy accounts often bypass SSO enforcement because they "
                "retain password authentication, creating a permanent credential-theft vector."
            ),
            remediation=(
                "Disable the legacy bare-name admin account after verifying the email-format account "
                "is active: 'ALTER USER <legacy> SET DISABLED = TRUE; REVOKE ROLE ... FROM USER <legacy>'."
            ),
            remediation_key="DISABLE_LEGACY_ADMIN",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            admin_users = {u.upper() for u in admin_users_from_context(cursor, scan_context)}

            if scan_context is not None and scan_context.users is not None:
                users = list(scan_context.users)
                cols = scan_context.users_cols
            else:
                cursor.execute("SHOW USERS")
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                users = cursor.fetchall()

            name_col = cols.get("name")
            login_col = cols.get("login_name")
            if name_col is None:
                return []

            # Build sets of email-format and bare-name admin accounts.
            email_stems: dict[str, str] = {}  # stem → full name
            bare_admins: dict[str, str] = {}  # stem → full name

            for user in users:
                raw_name = user[name_col]
                login = str(user[login_col] or raw_name) if login_col is not None else str(raw_name)
                upper = str(raw_name).upper()
                if upper not in admin_users:
                    continue
                if "@" in login:
                    stem = login.split("@")[0].upper()
                    email_stems[stem] = str(raw_name)
                else:
                    stem = upper
                    bare_admins[stem] = str(raw_name)

            for stem, bare_name in bare_admins.items():
                if stem in email_stems:
                    email_name = email_stems[stem]
                    violations.append(
                        self.violation(
                            bare_name,
                            f"Legacy admin account '{bare_name}' duplicates modern email-format admin "
                            f"'{email_name}'. Legacy account may bypass SSO and retain password access.",  # sensitive-output-ok: describes auth risk concept, not a credential value
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_024 — Orphan Role Ratio
# ---------------------------------------------------------------------------


class OrphanRoleRatioCheck(Rule):
    """SEC_024: Flag when the fraction of orphaned custom roles exceeds threshold.

    An orphan role has no privileges assigned to it AND is not granted to any
    user or other role.  A high orphan ratio indicates RBAC sprawl.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_024",
            "Orphan Role Ratio",
            Severity.LOW,
            rationale=(
                "Orphaned custom roles (no privileges, no grantees) accumulate over time and indicate "
                "RBAC sprawl. They add noise to audit logs and slow permission reviews without providing "
                "any access benefit. A high orphan ratio suggests the role lifecycle is not maintained."
            ),
            remediation=(
                "Review orphaned roles with: "
                "SELECT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES WHERE DELETED_ON IS NULL "
                "then cross-reference with GRANTS_TO_ROLES and GRANTS_TO_USERS. "
                "Drop roles that are truly unused: 'DROP ROLE <name>'."
            ),
            remediation_key="DROP_ORPHAN_ROLES",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtr = (
                scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                if scan_context
                else ()
            )
            gtu = (
                scan_context.get_or_fetch("GRANTS_TO_USERS", GRANTS_CACHE_WINDOW, gtu_fetcher(cursor))
                if scan_context
                else ()
            )

            # Full role catalog — needed to detect truly orphaned roles (no GTR/GTU presence).
            if scan_context is not None and scan_context.roles is not None:
                name_col = scan_context.roles_cols.get("name", 1)
                all_catalog_roles: set[str] = {str(row[name_col]).upper() for row in scan_context.roles}
            else:
                cursor.execute("SHOW ROLES")
                name_col = next(
                    (i for i, col in enumerate(cursor.description) if col[0].lower() == "name"),
                    1,
                )
                all_catalog_roles = {str(row[name_col]).upper() for row in cursor.fetchall()}

            custom_roles = {r for r in all_catalog_roles if r not in ADMIN_ROLES and r != "PUBLIC"}
            if not custom_roles:
                return []

            # Roles visible in grants data have at least one privilege or grantee.
            roles_with_grants: set[str] = {str(row[GTR_GRANTEE_NAME]).upper() for row in gtr}
            roles_with_grantees: set[str] = {str(row[GTU_ROLE]).upper() for row in gtu} | {
                str(row[GTR_NAME]).upper() for row in gtr if str(row[GTR_GRANTED_ON]).upper() == GTR_GRANTED_ON_ROLE
            }

            orphans = custom_roles - roles_with_grants - roles_with_grantees
            threshold_pct = self._thresholds.orphan_role_percent_threshold
            orphan_pct = len(orphans) / len(custom_roles) * 100

            if orphan_pct > threshold_pct:
                violations.append(
                    self.violation(
                        "Account",
                        f"Orphan role ratio is {orphan_pct:.0f}% ({len(orphans)}/{len(custom_roles)} custom roles) "
                        f"— exceeds threshold of {threshold_pct}%. "
                        "Review and drop unused roles to reduce RBAC sprawl.",
                        category=FindingCategory.INFORMATIONAL,
                    )
                )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_025 — God Role Detection
# ---------------------------------------------------------------------------


class GodRoleDetectionCheck(Rule):
    """SEC_025: Flag custom roles with excessive privilege and database span.

    Also flags any role that holds MANAGE GRANTS regardless of count thresholds.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_025",
            "God Role Detection",
            Severity.HIGH,
            rationale=(
                "Roles that span many databases and hold many privilege types are effectively "
                "'god roles': a single compromise of any user holding them gives broad data access. "
                "MANAGE GRANTS is especially dangerous because it lets the bearer self-escalate "
                "by granting themselves any privilege."
            ),
            remediation=(
                "Decompose the role into narrower, purpose-specific roles. "
                "For MANAGE GRANTS: replace with fine-grained ownership grants where possible. "
                "'REVOKE MANAGE GRANTS ON ACCOUNT FROM ROLE <name>'."
            ),
            remediation_key="DECOMPOSE_GOD_ROLE",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)

    @staticmethod
    def _aggregate_gtr(
        gtr: "tuple[Row, ...]",
    ) -> "tuple[defaultdict[str, int], defaultdict[str, set[str]], set[str]]":
        """Aggregate GTR rows into (priv_count, db_span, manage_grants_roles)."""
        priv_count: defaultdict[str, int] = defaultdict(int)
        db_span: defaultdict[str, set[str]] = defaultdict(set)
        manage_grants_roles: set[str] = set()
        for row in gtr:
            if str(row[GTR_GRANTED_ON]).upper() == GTR_GRANTED_ON_ROLE:
                continue
            role = str(row[GTR_GRANTEE_NAME]).upper()
            if role in ADMIN_ROLES:
                continue
            priv = str(row[GTR_PRIVILEGE]).upper()
            catalog = str(row[GTR_TABLE_CATALOG] or "").upper()
            priv_count[role] += 1
            if catalog:
                db_span[role].add(catalog)
            if priv == "MANAGE GRANTS":
                manage_grants_roles.add(role)
        return priv_count, db_span, manage_grants_roles

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtr = (
                scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                if scan_context
                else ()
            )

            # Aggregate per custom role: privileges and database span.
            priv_threshold = self._thresholds.god_role_privilege_threshold
            db_threshold = self._thresholds.god_role_database_span

            priv_count, db_span, manage_grants_roles = self._aggregate_gtr(gtr)

            # Flag MANAGE GRANTS holders unconditionally.
            for role in manage_grants_roles:
                violations.append(
                    self.violation(
                        role,
                        f"Role '{role}' holds MANAGE GRANTS — allows self-escalation by granting "
                        "any privilege. Remove unless strictly necessary.",
                        severity=Severity.CRITICAL,
                    )
                )

            # Flag god roles by privilege count + database span.
            for role, priv_cnt in priv_count.items():
                if role in manage_grants_roles:
                    continue  # Already flagged above.
                span = len(db_span.get(role, set()))
                if priv_cnt > priv_threshold and span > db_threshold:
                    violations.append(
                        self.violation(
                            role,
                            f"Role '{role}' has {priv_cnt} privilege grants spanning {span} databases "
                            f"(thresholds: >{priv_threshold} privs, >{db_threshold} DBs). "
                            "Decompose into narrower functional roles.",
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_026 — Privilege Concentration
# ---------------------------------------------------------------------------

_MIN_ROLES_FOR_GINI = 10


class PrivilegeConcentrationCheck(Rule):
    """SEC_026: Flag when privilege distribution across roles is highly unequal (high Gini)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_026",
            "Privilege Concentration",
            Severity.MEDIUM,
            rationale=(
                "A high Gini coefficient on role privilege counts means a small number of roles "
                "control the vast majority of privileges. This is a structural risk: compromise of "
                "any high-privilege role has outsized impact. A healthy RBAC design distributes "
                "privileges more evenly through a clear hierarchy."
            ),
            remediation=(
                "Identify the top privilege-holding roles and decompose them into "
                "purpose-specific child roles. Use the three-layer model: "
                "DBO/DDL roles → functional READ/WRITE roles → business-layer team roles."
            ),
            remediation_key="DECOMPOSE_HIGH_PRIVILEGE_ROLES",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtr = (
                scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                if scan_context
                else ()
            )

            counts = role_privilege_counts(gtr)
            # Exclude built-in admin roles from the distribution.
            custom_counts = {r: c for r, c in counts.items() if r not in ADMIN_ROLES and r != "PUBLIC"}

            if len(custom_counts) < _MIN_ROLES_FOR_GINI:
                return []

            gini = _gini([float(v) for v in custom_counts.values()])
            threshold = self._thresholds.privilege_concentration_gini_threshold

            if gini > threshold:
                top_roles = sorted(custom_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                top_str = ", ".join(f"{r}({c})" for r, c in top_roles)
                violations.append(
                    self.violation(
                        "Account",
                        f"Privilege distribution Gini coefficient is {gini:.2f} (threshold: {threshold}). "
                        f"Top roles by privilege count: {top_str}. "
                        "Decompose high-privilege roles into a layered hierarchy.",
                        category=FindingCategory.INFORMATIONAL,
                    )
                )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_027 — Role Flow Validation
# ---------------------------------------------------------------------------


class RoleFlowValidationCheck(Rule):
    """SEC_027: Flag users directly granted DBO/DDL-layer roles (layer skipping).

    A healthy three-layer model is: DBO/DDL roles → functional roles → business roles.
    Users should be granted business-layer or functional-layer roles, not DBO roles directly.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_027",
            "Role Flow Validation",
            Severity.MEDIUM,
            rationale=(
                "When users are directly granted DBO/DDL-layer roles they bypass the functional "
                "and business layers of the role hierarchy, gaining broader data-modification "
                "privileges than their job function requires."
            ),
            remediation=(
                "Remove direct user-to-DBO role grants. "
                "Assign users to functional-layer roles that inherit DBO privileges with appropriate scope."
            ),
            remediation_key="FIX_ROLE_HIERARCHY",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)
        self._dbo_pattern = re.compile(self._thresholds.dbo_role_pattern)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtu = (
                scan_context.get_or_fetch("GRANTS_TO_USERS", GRANTS_CACHE_WINDOW, gtu_fetcher(cursor))
                if scan_context
                else ()
            )

            for row in gtu:
                user = str(row[GTU_GRANTEE_NAME])
                role = str(row[GTU_ROLE])
                if self._dbo_pattern.match(role):
                    violations.append(
                        self.violation(
                            user,
                            f"User '{user}' is directly granted DBO/DDL-layer role '{role}'. "
                            "Grant a functional-layer role that inherits this privilege instead.",
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_028 — User Role Explosion
# ---------------------------------------------------------------------------


class UserRoleExplosionCheck(Rule):
    """SEC_028: Flag users with more direct role grants than the configured threshold."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_028",
            "User Role Explosion",
            Severity.LOW,
            rationale=(
                "Users with many direct role grants indicate an ad-hoc 'role soup' antipattern. "
                "Access decisions become hard to audit and the effective permission set is difficult "
                "to reason about. A business-layer role hierarchy solves this by grouping access "
                "into a single parent role."
            ),
            remediation=(
                "Consolidate the user's direct role grants into a business-layer role. "
                "Create a team/department role that inherits the individual functional roles, "
                "then grant the user that single parent role."
            ),
            remediation_key="CONSOLIDATE_ROLES",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtu = (
                scan_context.get_or_fetch("GRANTS_TO_USERS", GRANTS_CACHE_WINDOW, gtu_fetcher(cursor))
                if scan_context
                else ()
            )

            user_roles: dict[str, list[str]] = defaultdict(list)
            for row in gtu:
                user = str(row[GTU_GRANTEE_NAME])
                role = str(row[GTU_ROLE])
                user_roles[user].append(role)

            max_roles = self._thresholds.max_direct_roles_per_user
            for user, roles in user_roles.items():
                if len(roles) > max_roles:
                    violations.append(
                        self.violation(
                            user,
                            f"User '{user}' has {len(roles)} direct role grants "
                            f"(threshold: {max_roles}). Consolidate into a business-layer role.",
                            category=FindingCategory.INFORMATIONAL,
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ---------------------------------------------------------------------------
# SEC_029 — Incomplete Department Roles
# ---------------------------------------------------------------------------


class IncompleteDepartmentRolesCheck(Rule):
    """SEC_029: Flag functional roles with no parent business-layer role.

    Orphaned functional roles indicate incomplete role hierarchy: the functional
    layer exists but no business/department role consolidates access for teams.
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_029",
            "Incomplete Department Roles",
            Severity.LOW,
            rationale=(
                "Functional roles (READ/WRITE/ANALYST-suffix) that are not inherited by any "
                "business-layer role (TEAM/DEPT/BU-suffix) require individual user-level grants "
                "to provision access. This creates maintenance overhead and increases the risk "
                "of orphaned access when team membership changes."
            ),
            remediation=(
                "Create business-layer roles that inherit the relevant functional roles, "
                "then grant team members the business-layer role."
            ),
            remediation_key="ADD_BUSINESS_LAYER_ROLE",
            telemetry=telemetry,
        )
        self._thresholds = _default_rbac(conventions)
        self._functional_pattern = re.compile(self._thresholds.functional_role_pattern)
        self._business_pattern = re.compile(self._thresholds.business_role_pattern)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            gtr = (
                scan_context.get_or_fetch("GRANTS_TO_ROLES", GRANTS_CACHE_WINDOW, gtr_fetcher(cursor))
                if scan_context
                else ()
            )

            graph = build_role_graph(gtr)

            # Single pass to collect all role names visible in grant data.
            all_roles: set[str] = set()
            for row in gtr:
                all_roles.add(str(row[GTR_GRANTEE_NAME]).upper())
                if str(row[GTR_GRANTED_ON]).upper() == GTR_GRANTED_ON_ROLE:
                    all_roles.add(str(row[GTR_NAME]).upper())

            functional_roles = {r for r in all_roles if self._functional_pattern.match(r)}

            func_with_biz_parent: set[str] = set()
            for parent, children in graph.items():
                if self._business_pattern.match(parent):
                    for child in children:
                        if self._functional_pattern.match(child):
                            func_with_biz_parent.add(child.upper())

            orphaned_functional = functional_roles - func_with_biz_parent
            for role in sorted(orphaned_functional):
                violations.append(
                    self.violation(
                        role,
                        f"Functional role '{role}' has no parent business-layer role. "
                        "Wrap it in a TEAM/DEPT/BU-suffix role to simplify user provisioning.",
                        category=FindingCategory.INFORMATIONAL,
                    )
                )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations
