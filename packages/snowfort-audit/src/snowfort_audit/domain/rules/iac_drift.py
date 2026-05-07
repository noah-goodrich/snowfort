"""IaC Drift Detection + dbt Grant Analysis rules (Directive E).

Rules:
  OPS_015 — IaC Tool Detection
  OPS_016 — IaC Drift Indicators
  GOV_025 — dbt Grant Target Validation
  GOV_026 — dbt Schema Ownership
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import (
    DbtGrantsThresholds,
    IacDriftThresholds,
    SnowfortConventions,
)
from snowfort_audit.domain.rule_definitions import (
    FindingCategory,
    Rule,
    RuleExecutionError,
    Severity,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.rules._iac import (
    DDL_DATABASE_NAME,
    DDL_QUERY_COUNT,
    DDL_QUERY_TYPE,
    DDL_USER_NAME,
    GR_QUERY_TEXT,
    QH_IAC_CACHE_WINDOW,
    SCHEMA_OWNERS_CACHE_WINDOW,
    SO_CATALOG_NAME,
    SO_SCHEMA_NAME,
    SO_SCHEMA_OWNER,
    detect_iac_tools,
    managed_tag_coverage_by_database,
    parse_grant_target_role,
    qh_ddl_non_svc_fetcher,
    qh_grant_fetcher,
    qh_iac_fetcher,
    schema_owners_fetcher,
)

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.protocols import TelemetryPort
    from snowfort_audit.domain.rule_definitions import Violation
    from snowfort_audit.domain.scan_context import ScanContext


# ---------------------------------------------------------------------------
# Threshold helpers
# ---------------------------------------------------------------------------


def _default_iac(conventions: SnowfortConventions | None) -> IacDriftThresholds:
    return (conventions.thresholds.iac_drift) if conventions else IacDriftThresholds()


def _default_dbt(conventions: SnowfortConventions | None) -> DbtGrantsThresholds:
    return (conventions.thresholds.dbt_grants) if conventions else DbtGrantsThresholds()


# ---------------------------------------------------------------------------
# OPS_015: IaC Tool Detection
# ---------------------------------------------------------------------------


class IacToolDetectionCheck(Rule):
    """OPS_015: Detect IaC tool presence via query comments, tags, and service account patterns."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: "TelemetryPort | None" = None,
    ):
        super().__init__(
            "OPS_015",
            "IaC Tool Detection",
            Severity.LOW,
            rationale=(
                "Identifying which IaC tools manage your Snowflake account is the first "
                "step toward drift detection. Tools are detected via MANAGED_BY tags, "
                "query comment patterns, and service account naming conventions."
            ),
            remediation=(
                "Adopt infrastructure-as-code for Snowflake resources. Tag managed objects "
                "with MANAGED_BY and use dedicated service accounts (e.g., SVC_TERRAFORM)."
            ),
            telemetry=telemetry,
        )
        self._thresholds = _default_iac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> "list[Violation]":
        try:
            # Fetch QUERY_HISTORY IaC comment aggregation.
            qh_rows = (
                scan_context.get_or_fetch(
                    "QUERY_HISTORY_IAC",
                    QH_IAC_CACHE_WINDOW,
                    qh_iac_fetcher(cursor, self._thresholds.iac_comment_patterns),
                )
                if scan_context
                else ()
            )

            # Get tag_refs_index from scan_context.
            tag_refs_index = scan_context.tag_refs_index if scan_context else None

            tools = detect_iac_tools(qh_rows, tag_refs_index)

            # Also check for service account naming patterns.
            svc_pattern = self._thresholds.iac_service_account_pattern
            if scan_context and scan_context.users:
                user_col = scan_context.users_cols.get("name", 0)
                for row in scan_context.users:
                    user_name = str(row[user_col])
                    if re.search(svc_pattern, user_name):
                        # Infer tool from service account name.
                        label = user_name.upper()
                        tools.setdefault(label, []).append(f"Service account {user_name} matches IaC pattern")

            if not tools:
                return [
                    self.violation(
                        "Account",
                        "No IaC tools detected. Consider adopting infrastructure-as-code "
                        "(Terraform, dbt, Permifrost, etc.) for Snowflake resource management.",
                        category=FindingCategory.INFORMATIONAL,
                    )
                ]

            # Report each detected tool as informational.
            violations: list[Violation] = []
            for tool_label, evidence in sorted(tools.items()):
                evidence_summary = "; ".join(evidence[:3])
                if len(evidence) > 3:
                    evidence_summary += f" (+{len(evidence) - 3} more)"
                violations.append(
                    self.violation(
                        "Account",
                        f"IaC tool detected: {tool_label}. Evidence: {evidence_summary}",
                        category=FindingCategory.INFORMATIONAL,
                    )
                )
            return violations

        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# OPS_016: IaC Drift Indicators
# ---------------------------------------------------------------------------


class IacDriftIndicatorsCheck(Rule):
    """OPS_016: Detect drift signals for IaC-managed objects."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: "TelemetryPort | None" = None,
    ):
        super().__init__(
            "OPS_016",
            "IaC Drift Indicators",
            Severity.MEDIUM,
            rationale=(
                "Interactive changes to IaC-managed objects create drift, undermining "
                "governance confidence. Drift indicators include DDL by non-service-account "
                "users on tagged objects and coverage gaps in MANAGED_BY tagging."
            ),
            remediation=(
                "Reconcile drift by running your IaC tool (e.g., `terraform plan`, "
                "`dbt run`, `permifrost run`). Restrict DDL privileges for human users "
                "on IaC-managed objects."
            ),
            telemetry=telemetry,
        )
        self._thresholds = _default_iac(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> "list[Violation]":
        try:
            violations: list[Violation] = []

            # 1. DDL by non-service-account users (drift signal).
            violations.extend(self._check_ddl_drift(cursor, scan_context))

            # 2. MANAGED_BY tag coverage gaps.
            violations.extend(self._check_coverage_gaps(scan_context))

            return violations

        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc

    def _check_ddl_drift(
        self,
        cursor: "SnowflakeCursorProtocol",
        scan_context: "ScanContext | None",
    ) -> "list[Violation]":
        """Check for DDL statements by non-service-account users on managed databases."""
        if not scan_context:
            return []

        ddl_rows = scan_context.get_or_fetch(
            "QUERY_HISTORY_DDL_NON_SVC",
            QH_IAC_CACHE_WINDOW,
            qh_ddl_non_svc_fetcher(cursor, self._thresholds.iac_service_account_pattern),
        )

        # Get tag coverage to identify which databases are IaC-managed.
        tag_refs_index = scan_context.tag_refs_index if scan_context else None
        coverage = managed_tag_coverage_by_database(
            tag_refs_index,
            scan_context.databases if scan_context else None,
            scan_context.databases_cols if scan_context else None,
        )

        managed_dbs = {
            db.upper() for db, cov in coverage.items() if cov >= self._thresholds.managed_tag_coverage_threshold
        }

        violations: list[Violation] = []
        # Aggregate drift signals per database.
        drift_by_db: dict[str, list[tuple[str, str, int]]] = {}
        for row in ddl_rows:
            db_name = str(row[DDL_DATABASE_NAME]).upper()
            if db_name in managed_dbs:
                user = str(row[DDL_USER_NAME])
                qtype = str(row[DDL_QUERY_TYPE])
                count = int(row[DDL_QUERY_COUNT])
                drift_by_db.setdefault(db_name, []).append((user, qtype, count))

        for db_name, signals in sorted(drift_by_db.items()):
            total_ddl = sum(c for _, _, c in signals)
            users = sorted({u for u, _, _ in signals})
            violations.append(
                self.violation(
                    db_name,
                    f"Potential IaC drift: {total_ddl} DDL statement(s) by non-service-account "
                    f"user(s) ({', '.join(users[:3])}) on IaC-managed database {db_name} "
                    f"in the last {self._thresholds.drift_lookback_days} days. "
                    f"Run your IaC reconciliation tool to check for drift.",
                    category=FindingCategory.ACTIONABLE,
                )
            )

        return violations

    def _check_coverage_gaps(
        self,
        scan_context: "ScanContext | None",
    ) -> "list[Violation]":
        """Flag databases with partial MANAGED_BY tag coverage (>50% tagged but <100%)."""
        if not scan_context:
            return []

        tag_refs_index = scan_context.tag_refs_index if scan_context else None
        coverage = managed_tag_coverage_by_database(
            tag_refs_index,
            scan_context.databases if scan_context else None,
            scan_context.databases_cols if scan_context else None,
        )

        threshold = self._thresholds.managed_tag_coverage_threshold

        violations: list[Violation] = []
        for db_name, cov in sorted(coverage.items()):
            if threshold <= cov < 1.0:
                pct = f"{cov:.0%}"
                violations.append(
                    self.violation(
                        db_name,
                        f"MANAGED_BY tag coverage gap in database {db_name}: {pct} of objects "
                        f"are tagged, but some remain untagged. Objects without MANAGED_BY "
                        f"tags in a mostly-managed database may indicate unmanaged drift.",
                        severity=Severity.LOW,
                        category=FindingCategory.ACTIONABLE,
                    )
                )

        return violations


# ---------------------------------------------------------------------------
# GOV_025: dbt Grant Target Validation
# ---------------------------------------------------------------------------


class DbtGrantTargetValidationCheck(Rule):
    """GOV_025: Flag dbt grants that target business roles instead of functional roles."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: "TelemetryPort | None" = None,
    ):
        super().__init__(
            "GOV_025",
            "dbt Grant Target Validation",
            Severity.MEDIUM,
            rationale=(
                "dbt should grant privileges to functional roles (e.g., ANALYTICS_READ, "
                "TRANSFORM_WRITE), not directly to business roles (e.g., FINANCE_TEAM). "
                "Granting directly to business roles bypasses the functional-role layer "
                "and breaks least-privilege."
            ),
            remediation=(
                "Update dbt `grants:` config to target functional roles. Business roles "
                "should inherit access via the role hierarchy, not receive direct grants."
            ),
            telemetry=telemetry,
        )
        self._iac_thresholds = _default_iac(conventions)
        self._dbt_thresholds = _default_dbt(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> "list[Violation]":
        try:
            grant_rows = (
                scan_context.get_or_fetch(
                    "QUERY_HISTORY_DBT_GRANTS",
                    QH_IAC_CACHE_WINDOW,
                    qh_grant_fetcher(cursor, self._iac_thresholds.iac_comment_patterns),
                )
                if scan_context
                else ()
            )

            if not grant_rows:
                return []

            business_re = re.compile(self._dbt_thresholds.business_role_pattern)
            functional_re = re.compile(self._dbt_thresholds.functional_role_pattern)

            violations: list[Violation] = []
            flagged_roles: set[str] = set()

            for row in grant_rows:
                query_text = str(row[GR_QUERY_TEXT])
                target_role = parse_grant_target_role(query_text)
                if not target_role or target_role in flagged_roles:
                    continue

                # Flag if target matches business role pattern and NOT functional role pattern.
                if business_re.search(target_role) and not functional_re.search(target_role):
                    flagged_roles.add(target_role)
                    violations.append(
                        self.violation(
                            target_role,
                            f"dbt is granting directly to business role {target_role}. "
                            f"dbt should grant to functional roles; business roles should "
                            f"inherit via the role hierarchy.",
                            category=FindingCategory.ACTIONABLE,
                        )
                    )

            return violations

        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# GOV_026: dbt Schema Ownership
# ---------------------------------------------------------------------------


class DbtSchemaOwnershipCheck(Rule):
    """GOV_026: Flag schemas owned by dbt service account instead of a dedicated DBO role."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: "TelemetryPort | None" = None,
    ):
        super().__init__(
            "GOV_026",
            "dbt Schema Ownership",
            Severity.LOW,
            rationale=(
                "Schemas owned by a dbt service account (e.g., SVC_DBT) is an anti-pattern. "
                "Ownership should be held by a dedicated DBO/DDL role so that the service "
                "account operates with least privilege."
            ),
            remediation=(
                "Transfer schema ownership to a dedicated DBO role "
                "(e.g., `ALTER SCHEMA ... OWNER = MY_DB_DBO`). "
                "Grant the dbt service account USAGE and CREATE privileges instead."
            ),
            telemetry=telemetry,
        )
        self._dbt_thresholds = _default_dbt(conventions)

    def check_online(
        self,
        cursor: "SnowflakeCursorProtocol",
        _resource_name: str | None = None,
        *,
        scan_context: "ScanContext | None" = None,
        **_kw,
    ) -> "list[Violation]":
        try:
            schema_rows = (
                scan_context.get_or_fetch(
                    "SCHEMATA_OWNERS",
                    SCHEMA_OWNERS_CACHE_WINDOW,
                    schema_owners_fetcher(cursor),
                )
                if scan_context
                else ()
            )

            if not schema_rows:
                return []

            svc_re = re.compile(self._dbt_thresholds.dbt_service_account_pattern)
            dbo_re = re.compile(self._dbt_thresholds.dbo_role_pattern)

            violations: list[Violation] = []

            for row in schema_rows:
                catalog = str(row[SO_CATALOG_NAME])
                schema = str(row[SO_SCHEMA_NAME])
                owner = str(row[SO_SCHEMA_OWNER])

                # Skip if owner is not the dbt service account.
                if not svc_re.search(owner):
                    continue

                # Skip if owner is also a DBO role (unlikely but possible).
                if dbo_re.search(owner):
                    continue

                violations.append(
                    self.violation(
                        f"{catalog}.{schema}",
                        f"Schema {catalog}.{schema} is owned by dbt service account "
                        f"{owner}. Transfer ownership to a dedicated DBO role.",
                        category=FindingCategory.ACTIONABLE,
                    )
                )

            return violations

        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
