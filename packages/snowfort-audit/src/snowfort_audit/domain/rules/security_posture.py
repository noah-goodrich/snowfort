"""Directive G — Security Posture rules (SEC_030–036).

Gap analysis from the Snowflake Security Scanner article review.
These rules cover Trust Center scanner status, session policies, brute-force
login detection, private link ratio, large export volumes, periodic rekeying,
and threat intelligence findings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext

from snowfort_audit.domain.conventions import SecurityPostureThresholds, SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)


def _default_security_posture(conventions: SnowfortConventions | None) -> SecurityPostureThresholds:
    """Return SecurityPostureThresholds from conventions, or defaults when conventions is None."""
    if conventions is None:
        return SecurityPostureThresholds()
    return conventions.thresholds.security_posture


# ---------------------------------------------------------------------------
# SEC_030 — Trust Center Scanner Status
# ---------------------------------------------------------------------------


class TrustCenterScannerStatusCheck(Rule):
    """SEC_030: Any Trust Center scanner package disabled (Security Essentials, CIS, Threat Intel)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_030",
            "Trust Center Scanner Status",
            Severity.HIGH,
            rationale=(
                "Snowflake Trust Center scanner packages (Security Essentials, CIS Benchmarks, "
                "Threat Intelligence) continuously evaluate account security posture. Disabled "
                "scanners create blind spots for security teams."
            ),
            remediation=(
                "Enable all scanner packages in Trust Center: "
                "CALL SNOWFLAKE.TRUST_CENTER.SET_CONFIGURATION('ENABLED', 'TRUE', '<SCANNER_NAME>', FALSE)."
            ),
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
        for view in (
            "SNOWFLAKE.LOCAL.TRUST_CENTER.SCANNER_PACKAGES",
            "SNOWFLAKE.TRUST_CENTER.SCANNER_PACKAGES",
        ):
            try:
                cursor.execute(f"SELECT * FROM {view}")  # nosec B608 -- hardcoded internal constant
                rows = cursor.fetchall()
                if not rows:
                    return [
                        Violation(
                            self.id,
                            "Account",
                            "No Trust Center scanner packages found; enable Security Essentials, CIS Benchmarks, and Threat Intelligence.",
                            self.severity,
                        )
                    ]
                violations: list[Violation] = []
                for row in rows:
                    row_str = " ".join(str(v).upper() for v in (row or []))
                    # A disabled scanner contains 'FALSE' or 'DISABLED' in its row representation
                    if "FALSE" in row_str or "DISABLED" in row_str:
                        scanner_name = str(row[0]) if row else "UNKNOWN"
                        violations.append(
                            Violation(
                                self.id,
                                scanner_name,
                                f"Trust Center scanner '{scanner_name}' is not enabled.",
                                self.severity,
                            )
                        )
                return violations
            except Exception as exc:
                if is_allowlisted_sf_error(exc):
                    return []
                err_str = str(exc).lower()
                if "does not exist" in err_str or "not authorized" in err_str:
                    continue
                raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        # Neither view accessible — graceful degradation
        return []


# ---------------------------------------------------------------------------
# SEC_031 — Session Policy Check
# ---------------------------------------------------------------------------


class SessionPolicyCheck(Rule):
    """SEC_031: No session policy in account."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_031",
            "Session Policy",
            Severity.HIGH,
            rationale=(
                "Session policies enforce idle timeout and session duration limits. Without one, "
                "sessions can persist indefinitely, increasing the risk from stolen session tokens."
            ),
            remediation=(
                "Create and apply a session policy: "
                "CREATE SESSION POLICY ... SESSION_IDLE_TIMEOUT_MINS = 30; "
                "ALTER ACCOUNT SET SESSION POLICY <policy_name>."
            ),
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
            cursor.execute("SHOW SESSION POLICIES IN ACCOUNT")
            policies = cursor.fetchall()
            if not policies:
                return [
                    Violation(
                        self.id,
                        "Account",
                        "No session policy defined in account; define and apply one to enforce idle timeout.",
                        self.severity,
                    )
                ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return []


# ---------------------------------------------------------------------------
# SEC_032 — Brute Force Detection
# ---------------------------------------------------------------------------


class BruteForceDetectionCheck(Rule):
    """SEC_032: 5+ failed logins from same user in 7d (LOGIN_HISTORY)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_032",
            "Brute Force Detection",
            Severity.HIGH,
            rationale=(
                "Repeated failed login attempts from the same user name indicate credential stuffing "
                "or brute-force attacks. Early detection enables IP blocking and password resets."
            ),
            remediation=(
                "Investigate the source IPs of failed attempts; consider blocking via network policy "
                "or rotating the affected user's credentials."
            ),
            telemetry=telemetry,
        )
        t = _default_security_posture(conventions)
        self._threshold = t.brute_force_attempts_threshold
        self._window_days = t.brute_force_window_days

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        query = (
            "SELECT USER_NAME, COUNT(*) AS fail_count"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY"
            " WHERE IS_SUCCESS = 'NO'"
            f"  AND EVENT_TIMESTAMP >= DATEADD(day, -{self._window_days}, CURRENT_TIMESTAMP())"
            f" GROUP BY USER_NAME HAVING COUNT(*) >= {self._threshold}"
            " ORDER BY fail_count DESC"
            " LIMIT 50"
        )
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    str(row[0]),
                    f"User '{row[0]}' has {row[1]} failed login attempts in the last {self._window_days} days.",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# SEC_033 — Private Link Ratio
# ---------------------------------------------------------------------------


class PrivateLinkRatioCheck(Rule):
    """SEC_033: Private-endpoint login ratio < 80% threshold (LOGIN_HISTORY)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_033",
            "Private Link Ratio",
            Severity.MEDIUM,
            rationale=(
                "Accounts with Private Link configured should see the majority of logins through "
                "private endpoints. A low ratio indicates clients still connecting over the public "
                "internet, defeating the purpose of Private Link."
            ),
            remediation=(
                "Migrate remaining clients to the private endpoint URL. "
                "Consider enabling ENFORCE_PRIVATE_LINK_FOR_ALL_CONNECTIONS once ratio reaches 100%."
            ),
            telemetry=telemetry,
        )
        t = _default_security_posture(conventions)
        self._threshold = t.private_link_ratio_threshold

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        query = (
            "SELECT"
            "  COUNT_IF(CONNECTION_TYPE = 'PRIVATE_LINK') AS private_count,"
            "  COUNT(*) AS total_count"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY"
            " WHERE IS_SUCCESS = 'YES'"
            "  AND EVENT_TIMESTAMP >= DATEADD(day, -30, CURRENT_TIMESTAMP())"
        )
        try:
            cursor.execute(query)
            row = cursor.fetchone()
            if not row or row[1] is None or int(row[1]) == 0:
                return []
            private_count = int(row[0]) if row[0] else 0
            total_count = int(row[1])
            ratio = private_count / total_count
            if ratio < self._threshold and private_count > 0:
                pct = f"{ratio * 100:.1f}%"
                return [
                    Violation(
                        self.id,
                        "Account",
                        f"Private Link login ratio is {pct} (threshold: {self._threshold * 100:.0f}%); "
                        f"{total_count - private_count} of {total_count} successful logins used public endpoint.",
                        self.severity,
                    )
                ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return []


# ---------------------------------------------------------------------------
# SEC_034 — Large Export Volume
# ---------------------------------------------------------------------------


class LargeExportVolumeCheck(Rule):
    """SEC_034: User exported >1M rows in 7d (COPY_HISTORY)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "SEC_034",
            "Large Export Volume",
            Severity.MEDIUM,
            rationale=(
                "Unusually large data exports may indicate data exfiltration or accidental data leakage. "
                "Monitoring export volume complements parameter-based exfiltration controls."
            ),
            remediation=(
                "Review the user's COPY INTO activity; verify business justification. "
                "Consider applying row-level security or limiting COPY privileges."
            ),
            telemetry=telemetry,
        )
        t = _default_security_posture(conventions)
        self._row_threshold = t.large_export_rows_threshold
        self._window_days = t.large_export_window_days

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        query = (
            "SELECT FILE_NAME, TABLE_NAME, ROW_COUNT"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY"
            " WHERE STAGE_LOCATION IS NOT NULL"
            f"  AND LAST_LOAD_TIME >= DATEADD(day, -{self._window_days}, CURRENT_TIMESTAMP())"
            f"  AND ROW_COUNT >= {self._row_threshold}"
            " ORDER BY ROW_COUNT DESC"
            " LIMIT 20"
        )
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    str(row[1]),
                    f"Large export detected: {row[2]:,} rows from '{row[1]}' to stage (file: {row[0]}).",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ---------------------------------------------------------------------------
# SEC_035 — Periodic Rekeying
# ---------------------------------------------------------------------------


class PeriodicRekeyingCheck(Rule):
    """SEC_035: Periodic rekeying not enabled."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_035",
            "Periodic Rekeying",
            Severity.MEDIUM,
            rationale=(
                "Periodic rekeying rotates encryption keys automatically, limiting the blast radius "
                "of a compromised key. Snowflake supports this as an account-level parameter."
            ),
            remediation=(
                "Enable periodic rekeying: ALTER ACCOUNT SET PERIODIC_DATA_REKEYING = TRUE. "
                "Note: this is an Enterprise+ feature."
            ),
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
            cursor.execute("SHOW PARAMETERS LIKE 'PERIODIC_DATA_REKEYING' IN ACCOUNT")
            row = cursor.fetchone()
            if not row:
                return [
                    Violation(
                        self.id,
                        "Account",
                        "PERIODIC_DATA_REKEYING parameter not found; periodic rekeying may not be available on this edition.",
                        self.severity,
                    )
                ]
            value = str(row[1]).strip().upper() if len(row) > 1 else ""
            if value != "TRUE":
                return [
                    Violation(
                        self.id,
                        "Account",
                        f"Periodic data rekeying is not enabled (current value: {value or 'FALSE'}).",
                        self.severity,
                    )
                ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return []


# ---------------------------------------------------------------------------
# SEC_036 — Threat Intelligence Findings
# ---------------------------------------------------------------------------


class ThreatIntelligenceFindingsCheck(Rule):
    """SEC_036: Trust Center Threat Intelligence scanner has open findings."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SEC_036",
            "Threat Intelligence Findings",
            Severity.CRITICAL,
            rationale=(
                "The Threat Intelligence scanner detects known-bad IPs, compromised credentials, "
                "and suspicious access patterns. Any open finding requires immediate investigation."
            ),
            remediation=(
                "Review Trust Center > Threat Intelligence findings in Snowsight. "
                "Block flagged IPs via network policy; rotate compromised credentials immediately."
            ),
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
                "SELECT SEVERITY, COUNT(*) AS cnt"
                " FROM SNOWFLAKE.TRUST_CENTER.FINDINGS"
                " WHERE SCANNER_NAME = 'THREAT_INTELLIGENCE'"
                "  AND STATE != 'RESOLVED'"
                " GROUP BY SEVERITY"
                " ORDER BY SEVERITY"
            )
            return [
                Violation(
                    self.id,
                    "Threat Intelligence",
                    f"Trust Center Threat Intelligence: {row[1]} open {row[0]} finding(s).",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
