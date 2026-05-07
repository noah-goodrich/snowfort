from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING, cast

from snowfort_audit.domain.conventions import SecurityPostureThresholds, SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT,
    SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB,
    FindingCategory,
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
    is_excluded_db_or_warehouse_name,
)
from snowfort_audit.domain.scan_context import TR_DOMAIN, TR_OBJECT_NAME, TR_TAG_NAME, TR_TAG_VALUE

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext

# Removed Infrastructure import


def _name_matches_pattern(name: str, pattern: str) -> bool:
    """Case-insensitive glob match (supports * and ? wildcards)."""
    return fnmatch.fnmatchcase(name.upper(), pattern.upper())


class AggressiveAutoSuspendCheck(Rule):
    """COST_001: Flag Warehouses with auto_suspend > convention (default 30s unless performance benefit)."""

    AUTO_SUSPEND_LIMIT_SECONDS = 30  # fallback when conventions not injected
    AUTO_SUSPEND_MAX_SECONDS = 3600  # fallback hard cap when conventions not injected

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_001",
            "Aggressive Auto-Suspend",
            Severity.MEDIUM,
            rationale="Excessive idle time on warehouses leads to significant credit waste without providing performance benefits for most analytical workloads.",
            remediation=(
                "Set 'auto_suspend' to 1 second (Snowfort default). Set higher only if you have a documented performance benefit."
            ),
            remediation_key="FIX_SUSPEND_TIME",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def _auto_suspend_limit(self) -> int:
        if self._conventions is not None:
            return self._conventions.warehouse.auto_suspend_seconds
        return self.AUTO_SUSPEND_LIMIT_SECONDS

    def _auto_suspend_max(self) -> int:
        if self._conventions is not None:
            return self._conventions.thresholds.warehouse_auto_suspend_max_seconds
        return self.AUTO_SUSPEND_MAX_SECONDS

    def check(self, resource: dict, resource_name: str) -> list[Violation]:
        if resource.get("type", "").upper() != "WAREHOUSE":
            return []

        limit = self._auto_suspend_limit()
        auto_suspend = int(resource.get("auto_suspend", 0))
        if auto_suspend > limit:
            return [
                Violation(
                    self.id,
                    resource_name,
                    f"Auto-suspend {auto_suspend}s exceeds Snowfort convention ({limit}s).",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        """Improved check with Tag Awareness for environment detection."""
        violations = []
        try:
            env_tags = self._get_warehouse_env_tags(cursor, scan_context)
            if scan_context is not None and scan_context.warehouses is not None:
                cols = scan_context.warehouses_cols
                name_idx = cols.get("name", 0)
                warehouses = [
                    wh for wh in scan_context.warehouses if not is_excluded_db_or_warehouse_name(wh[name_idx])
                ]
            else:
                cursor.execute("SHOW WAREHOUSES")
                rows_raw = cursor.fetchall()
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                name_idx = cols.get("name", 0)
                warehouses = [wh for wh in rows_raw if not is_excluded_db_or_warehouse_name(wh[name_idx])]

            for wh in warehouses:
                violations.extend(self._check_warehouse_suspension(wh, cols, env_tags))
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations

    def _get_warehouse_env_tags(
        self, cursor: SnowflakeCursorProtocol, scan_context: ScanContext | None = None
    ) -> dict[str, str]:
        """Fetches ENVIRONMENT tags for all warehouses."""
        env_tags: dict[str, str] = {}
        try:
            if scan_context is not None and scan_context.tag_refs_index is not None:
                for (domain, obj_name), tags in scan_context.tag_refs_index.items():
                    if domain == "WAREHOUSE" and "ENVIRONMENT" in tags and tags["ENVIRONMENT"]:
                        env_tags[obj_name] = tags["ENVIRONMENT"].upper()
            elif scan_context is not None and scan_context.tag_refs is not None:
                for row in scan_context.tag_refs:
                    if (
                        str(row[TR_DOMAIN]).upper() == "WAREHOUSE"
                        and str(row[TR_TAG_NAME]).upper() == "ENVIRONMENT"
                        and row[TR_TAG_VALUE]
                    ):
                        env_tags[str(row[TR_OBJECT_NAME]).upper()] = str(row[TR_TAG_VALUE]).upper()
            else:
                tag_query = """
                SELECT OBJECT_NAME, TAG_VALUE
                FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
                WHERE DOMAIN = 'WAREHOUSE'
                AND TAG_NAME = 'ENVIRONMENT'
                AND DELETED IS NULL
                """
                cursor.execute(tag_query)
                for row in cursor.fetchall():
                    obj_name, tag_value = row[0], row[1]
                    env_tags[obj_name.upper()] = tag_value.upper()
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return env_tags
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return env_tags

    def _check_warehouse_suspension(self, wh: tuple, cols: dict[str, int], env_tags: dict[str, str]) -> list[Violation]:
        """Validates suspension settings for a single warehouse."""
        name = wh[cols["name"]]
        suspend = wh[cols["auto_suspend"]]

        # Check value
        if not suspend or str(suspend) == "null":
            return [
                Violation(
                    self.id,
                    name,
                    "Auto-suspend is NULL (Never suspends).",
                    Severity.CRITICAL,
                    remediation_key=self.remediation_key,
                )
            ]

        suspend_val = int(suspend)
        max_seconds = self._auto_suspend_max()

        if suspend_val > max_seconds:
            return [
                Violation(
                    self.id,
                    name,
                    f"Auto-suspend {suspend_val}s greatly exceeds recommended maximum ({max_seconds}s). Warehouse may idle for hours.",
                    Severity.MEDIUM,
                    remediation_key=self.remediation_key,
                )
            ]

        limit = self._auto_suspend_limit()
        if suspend_val > limit:
            return [
                Violation(
                    self.id,
                    name,
                    f"Auto-suspend {suspend_val}s exceeds Snowfort convention ({limit}s).",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class ZombieWarehouseCheck(Rule):
    """COST_002: Identify Warehouses with auto_resume=true that haven't processed a query in > 7 days."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_002",
            "Zombie Warehouses",
            Severity.HIGH,
            rationale="Unused warehouses with auto-resume enabled pose a financial risk as they can be triggered by automated scripts, incurring unnecessary minimum billing charges.",
            remediation=(
                "Drop unused warehouses or disable auto-resume: 'ALTER WAREHOUSE <name> SET AUTO_RESUME = FALSE'."
            ),
            remediation_key="DROP_ZOMBIE_WAREHOUSE",
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
        """Check for warehouses with no query activity in last 7 days."""
        query = """
        SELECT WAREHOUSE_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
        WHERE TIMESTAMP > DATEADD('day', -7, CURRENT_TIMESTAMP())
        GROUP BY 1
        """
        try:
            cursor.execute(query)
            active_warehouses = {row[0] for row in cursor.fetchall()}

            # Get all warehouses to compare (exclude system/tool)
            if scan_context is not None and scan_context.warehouses is not None:
                _wh_name_idx = scan_context.warehouses_cols.get("name", 0)
                all_warehouses = [
                    wh for wh in scan_context.warehouses if not is_excluded_db_or_warehouse_name(wh[_wh_name_idx])
                ]
            else:
                cursor.execute("SHOW WAREHOUSES")
                _wh_rows = cursor.fetchall()
                _wh_name_idx = {c[0].lower(): i for i, c in enumerate(cursor.description)}.get("name", 0)
                all_warehouses = [wh for wh in _wh_rows if not is_excluded_db_or_warehouse_name(wh[_wh_name_idx])]

            violations = []
            for wh in all_warehouses:
                name = wh[_wh_name_idx]
                if name not in active_warehouses:
                    violations.append(
                        Violation(
                            self.id,
                            name,
                            "Warehouse has no recorded events/activity in the last 7 days.",
                            self.severity,
                            remediation_key=self.remediation_key,
                        )
                    )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class CloudServicesRatioCheck(Rule):
    """COST_003: Alert if Cloud Services credits > 10% of total compute."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_003",
            "Cloud Services Ratio",
            Severity.MEDIUM,
            rationale="High cloud services ratios often indicate inefficient metadata operations or small-file problems that can be optimized to reduce non-compute overhead costs.",
            remediation=(
                "Analyze query patterns for warehouses with high Cloud Services usage. "
                "Consider optimizing queries, adjusting warehouse sizes, or reviewing data loading strategies."
            ),
            remediation_key="OPTIMIZE_CLOUD_SERVICES",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = """
        SELECT WAREHOUSE_NAME,
               SUM(CREDITS_USED_CLOUD_SERVICES) / NULLIF(SUM(CREDITS_USED), 0) * 100 as ratio
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
        GROUP BY 1
        HAVING ratio > 10
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name, ratio = row[0], row[1]
                violations.append(
                    Violation(
                        self.id,
                        wh_name,
                        f"High Cloud Services consumption: {ratio:.1f}%",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class RunawayQueryCheck(Rule):
    """COST_004: Ensure STATEMENT_TIMEOUT_IN_SECONDS is set."""

    GLOBAL_TIMEOUT_THRESHOLD_SECONDS = 3600

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_004",
            "Runaway Query Protection",
            Severity.HIGH,
            rationale="A single unoptimized query can run for up to 48 hours by default, potentially costing thousands of dollars before manual intervention is possible.",
            remediation=(
                "Set STATEMENT_TIMEOUT_IN_SECONDS to a reasonable limit (e.g., 3600 for 1 hour) "
                "on the Account or Warehouse level: ALTER ACCOUNT SET STATEMENT_TIMEOUT_IN_SECONDS = 3600; "
                "or ALTER WAREHOUSE <name> SET STATEMENT_TIMEOUT_IN_SECONDS = 900;"
            ),
            remediation_key="SET_STATEMENT_TIMEOUT",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = "SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS' IN ACCOUNT"
        cursor.execute(query)
        res = cursor.fetchone()
        if res:
            timeout_val = res[1]
            if int(timeout_val) > self.GLOBAL_TIMEOUT_THRESHOLD_SECONDS:
                return [
                    Violation(
                        self.id,
                        "Account",
                        f"Global timeout is high: {timeout_val}s",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                ]
        return []


class MultiClusterSafeguardCheck(Rule):
    """COST_005: Flag MAX_CLUSTER_COUNT > 1 if SCALING_POLICY is not ECONOMY."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_005",
            "Multi-Cluster Safeguard",
            Severity.LOW,
            rationale="Using the 'Standard' scaling policy on multi-cluster warehouses can cause secondary clusters to spin up prematurely for minor concurrency spikes, increasing costs unnecessarily.",
            remediation=("Set SCALING_POLICY = 'ECONOMY' for multi-cluster warehouses unless latency is critical."),
            remediation_key="SET_SCALING_POLICY",
            telemetry=telemetry,
        )

    def check(self, resource: dict, resource_name: str) -> list[Violation]:
        if resource.get("type", "").upper() != "WAREHOUSE":
            return []

        max_cluster = int(resource.get("max_cluster_count", 1))
        policy = resource.get("scaling_policy", "STANDARD").upper()

        if max_cluster > 1 and policy != "ECONOMY":
            return [
                Violation(
                    self.id,
                    resource_name,
                    "MCW should use ECONOMY scaling policy",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class UnderutilizedWarehouseCheck(Rule):
    """COST_006: Identify Over-Provisioned Warehouses (Low Load)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_006",
            "Underutilized Warehouse",
            Severity.LOW,  # Optimization warning
            rationale="Maintaining large warehouses for low-concurrency, small-data workloads results in high cost-per-query that can be halved by down-sizing to a more appropriate tier.",
            remediation="Reduce Warehouse Size (e.g., Large -> Medium) and monitor performance.",
            remediation_key="RIGHTSIZE_WAREHOUSE",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # WAREHOUSE_LOAD_HISTORY is latent (up to 2 hrs).
        query = """
        SELECT WAREHOUSE_NAME, AVG(AVG_RUNNING) as avg_load
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
        WHERE START_TIME > DATEADD('day', -7, CURRENT_TIMESTAMP())
        GROUP BY 1
        HAVING avg_load < 0.1 AND avg_load > 0
        """
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            violations = []
            for row in rows:
                name = row[0]
                load = round(float(row[1]), 3)
                violations.append(
                    Violation(
                        self.id,
                        name,
                        f"Avg Load ({load}) < 0.1 over last 7 days. Consider down-sizing.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class HighChurnPermanentTableCheck(Rule):
    """COST_012: Identify Permanent tables where Fail-safe bytes > 3x Active bytes."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_012",
            "High-Churn Permanent Tables",
            Severity.MEDIUM,
            rationale="Permanent tables with high churn accumulate non-configurable Fail-safe storage costs that can be avoided by using transient tables for intermediate staging data.",
            remediation=(
                "Convert the table to TRANSIENT if the data is reproducible, "
                "or optimize the load pattern to reduce churn to lower Fail-safe storage usage."
            ),
            remediation_key="CONVERT_TO_TRANSIENT",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def _exclude_name_patterns(self) -> tuple[str, ...]:
        if self._conventions is not None:
            return self._conventions.thresholds.high_churn.exclude_name_patterns
        return ()

    def _cdc_schema_pattern(self) -> str:
        if self._conventions is not None:
            return self._conventions.thresholds.high_churn.cdc_schema_pattern
        from snowfort_audit.domain.conventions import HighChurnThresholds

        return HighChurnThresholds().cdc_schema_pattern

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        """Identify Permanent tables where Fail-safe bytes > 3x Active bytes."""
        query = (
            """
        SELECT TABLE_CATALOG || '.' || TABLE_SCHEMA || '.' || TABLE_NAME,
               ACTIVE_BYTES,
               FAILSAFE_BYTES
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
        WHERE TABLE_DROPPED IS NULL
          AND ACTIVE_BYTES > 0
          AND FAILSAFE_BYTES > (3 * ACTIVE_BYTES)
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
            + """
        """
        )
        try:
            cursor.execute(query)
            exclude_patterns = self._exclude_name_patterns()
            cdc_pattern = self._cdc_schema_pattern()
            cdc_regex = re.compile(cdc_pattern) if cdc_pattern else None
            violations = []
            for row in cursor.fetchall():
                table_name, active_bytes, failsafe_bytes = str(row[0]), row[1], row[2]
                if exclude_patterns and any(_name_matches_pattern(table_name.upper(), pat) for pat in exclude_patterns):
                    continue
                # Match either database or schema portion — CDC tooling often creates its
                # own top-level database (e.g., RAW_CDC) or a canonical schema (e.g., STAGING).
                parts = table_name.split(".")
                db_part = parts[0] if parts else ""
                schema_part = parts[1] if len(parts) >= 2 else ""
                is_cdc = cdc_regex is not None and (
                    bool(cdc_regex.search(db_part)) or bool(cdc_regex.search(schema_part))
                )
                if is_cdc:
                    category = FindingCategory.EXPECTED
                    message = (
                        f"Fail-safe bytes ({failsafe_bytes}) > 3x Active bytes ({active_bytes}) on CDC-pattern schema. "
                        "Convert to TRANSIENT to eliminate fail-safe cost."
                    )
                    remediation_instruction = (
                        "Convert to TRANSIENT to eliminate fail-safe cost: "
                        "CREATE OR REPLACE TRANSIENT TABLE ... AS SELECT * FROM ..."
                    )
                else:
                    category = FindingCategory.ACTIONABLE
                    message = (
                        f"Fail-safe bytes ({failsafe_bytes}) > 3x Active bytes ({active_bytes}). High churn detected."
                    )
                    remediation_instruction = None
                violations.append(
                    Violation(
                        self.id,
                        table_name,
                        message,
                        self.severity,
                        remediation_key=self.remediation_key,
                        remediation_instruction=remediation_instruction,
                        category=category,
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class PerWarehouseStatementTimeoutCheck(Rule):
    """COST_009: Flag warehouses without a sensible STATEMENT_TIMEOUT_IN_SECONDS (WAF: per-warehouse timeout)."""

    DEFAULT_TIMEOUT_SECONDS = 172800  # 48 hours Snowflake default
    MAX_RECOMMENDED_SECONDS = 28800  # 8 hours for ETL; dashboards often 900

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_009",
            "Per-Warehouse Statement Timeout",
            Severity.MEDIUM,
            rationale="Warehouses inheriting the account default (48h) allow runaway queries; WAF recommends setting a sensible maximum per warehouse.",
            remediation="Set STATEMENT_TIMEOUT_IN_SECONDS on the warehouse (e.g., 900 for BI, 28800 for ETL).",
            remediation_key="SET_WAREHOUSE_STATEMENT_TIMEOUT",
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
            if scan_context is not None and scan_context.warehouses is not None:
                cols = scan_context.warehouses_cols
                name_idx = cols.get("name", 0)
                warehouses = [
                    wh for wh in scan_context.warehouses if not is_excluded_db_or_warehouse_name(wh[name_idx])
                ]
            else:
                cursor.execute("SHOW WAREHOUSES")
                _raw = cursor.fetchall()
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description)}
                name_idx = cols.get("name", 0)
                warehouses = [wh for wh in _raw if not is_excluded_db_or_warehouse_name(wh[name_idx])]

            # Batch: account-level default (1 query) + warehouse overrides via OBJECT_PARAMETERS (1 query)
            cursor.execute("SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS' IN ACCOUNT")
            acct_row = cursor.fetchone()
            try:
                acct_timeout = acct_row[1] if acct_row else None
                account_default = (
                    int(cast(str | int, acct_timeout))
                    if acct_timeout not in (None, "", "null")
                    else self.DEFAULT_TIMEOUT_SECONDS
                )
            except (TypeError, ValueError):
                account_default = self.DEFAULT_TIMEOUT_SECONDS

            wh_overrides: dict[str, int] = {}
            try:
                cursor.execute(
                    "SELECT OBJECT_NAME, VALUE "
                    "FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_PARAMETERS "
                    "WHERE PARAMETER_NAME = 'STATEMENT_TIMEOUT_IN_SECONDS' "
                    "AND OBJECT_TYPE = 'WAREHOUSE'"
                )
                for r in cursor.fetchall():
                    try:
                        wh_name, timeout_str = r[0], r[1]
                        wh_overrides[str(wh_name).upper()] = int(timeout_str)
                    except (TypeError, ValueError, IndexError):
                        pass
            except Exception as exc:
                # Allowlisted (view unavailable) → fall back to account default for all.
                if not is_allowlisted_sf_error(exc):
                    raise RuleExecutionError(self.id, str(exc), cause=exc) from exc

            for wh in warehouses:
                wh_name = wh[name_idx]
                timeout_sec = wh_overrides.get(wh_name.upper(), account_default)
                if timeout_sec >= self.DEFAULT_TIMEOUT_SECONDS or timeout_sec <= 0:
                    violations.append(
                        self.violation(
                            wh_name,
                            f"Warehouse has no or default statement timeout ({timeout_sec}s). Set a sensible limit.",
                        )
                    )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


class StaleTableDetectionCheck(Rule):
    """COST_007: Flag large tables not queried in >90 days (WAF: clean up unused objects)."""

    STALE_DAYS = 90
    MIN_ACTIVE_BYTES = 100_000_000  # 100 MB

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_007",
            "Stale Table Detection",
            Severity.MEDIUM,
            rationale="Large tables that are never queried incur storage cost without value; WAF recommends proactive cleanup of unused objects.",
            remediation="Archive or drop tables that are no longer needed; or confirm they are used by scheduled jobs and add to ACCESS_HISTORY monitoring.",
            remediation_key="CLEANUP_STALE_TABLES",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            f"""
        WITH recent_table_accesses AS (
            SELECT DISTINCT f.value:objectName::string AS object_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY h,
            LATERAL FLATTEN(input => h.direct_objects_accessed) f
            WHERE h.query_start_time >= DATEADD(day, -{self.STALE_DAYS}, CURRENT_TIMESTAMP())
            AND UPPER(COALESCE(f.value:objectDomain::string, '')) = 'TABLE'
        )
        SELECT m.TABLE_CATALOG, m.TABLE_SCHEMA, m.TABLE_NAME, m.ACTIVE_BYTES
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS m
        LEFT JOIN recent_table_accesses ra
            ON (m.TABLE_CATALOG || '.' || m.TABLE_SCHEMA || '.' || m.TABLE_NAME) = ra.object_name
        WHERE m.TABLE_DROPPED IS NULL
        AND m.ACTIVE_BYTES > {self.MIN_ACTIVE_BYTES}
        AND ra.object_name IS NULL
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT.replace("TABLE_CATALOG", "m.TABLE_CATALOG")
            + """
        ORDER BY m.ACTIVE_BYTES DESC
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, table, active_bytes = row[0], row[1], row[2], row[3]
                violations.append(
                    self.violation(
                        f"{db}.{schema}.{table}",
                        f"Table not queried in {self.STALE_DAYS}+ days with significant storage ({active_bytes:,} bytes).",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class StagingTableTypeOptimizationCheck(Rule):
    """COST_008: Flag permanent staging-named tables that incur fail-safe cost (WAF: use TRANSIENT/TEMP)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_008",
            "Staging Table Type Optimization",
            Severity.MEDIUM,
            rationale="Permanent tables named like staging often hold transient data; fail-safe on them increases cost; WAF recommends TRANSIENT or TEMPORARY for staging.",
            remediation="Convert to TRANSIENT or use TEMPORARY tables for staging; or rename if the table is long-lived.",
            remediation_key="USE_TRANSIENT_STAGING",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, FAILSAFE_BYTES, ACTIVE_BYTES
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
        WHERE TABLE_DROPPED IS NULL
        AND (TABLE_NAME ILIKE 'STG_%' OR TABLE_NAME ILIKE 'STAGING_%' OR TABLE_NAME ILIKE 'TMP_%' OR TABLE_NAME ILIKE 'TEMP_%')
        AND (FAILSAFE_BYTES > 0 OR ACTIVE_BYTES > 0)
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
            + """
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, table, failsafe_bytes = row[0], row[1], row[2], row[3]
                fq = f"{db}.{schema}.{table}"
                msg = "Permanent table with staging-like name has fail-safe/active storage; use TRANSIENT or TEMPORARY for staging."
                if failsafe_bytes and int(failsafe_bytes) > 0:
                    msg += f" Fail-safe bytes: {failsafe_bytes:,}."
                violations.append(self.violation(fq, msg))
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class UnusedMaterializedViewCheck(Rule):
    """COST_013: Flag materialized views that are refreshed but rarely queried (WAF: avoid unnecessary MV cost)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_013",
            "Unused Materialized View Detection",
            Severity.MEDIUM,
            rationale="Infrequently used materialized views incur refresh and storage cost; WAF recommends removing or consolidating unused MVs.",
            remediation="Drop or replace rarely-used materialized views; or ensure they are queried by downstream consumers.",
            remediation_key="REVIEW_MATERIALIZED_VIEWS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # MVs that were refreshed in last 30 days but not in direct_objects_accessed in last 30 days
        query = (
            """
        WITH recent_mv_accesses AS (
            SELECT DISTINCT f.value:objectName::string AS object_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY h,
            LATERAL FLATTEN(input => h.direct_objects_accessed) f
            WHERE h.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
        )
        SELECT DISTINCT r.DATABASE_NAME, r.SCHEMA_NAME, r.TABLE_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY r
        LEFT JOIN recent_mv_accesses ra
            ON (r.DATABASE_NAME || '.' || r.SCHEMA_NAME || '.' || r.TABLE_NAME) = ra.object_name
        WHERE r.END_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
        AND ra.object_name IS NULL
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB.replace("DATABASE_NAME", "r.DATABASE_NAME")
            + """
        LIMIT 50
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, table = row[0], row[1], row[2]
                violations.append(
                    self.violation(
                        f"{db}.{schema}.{table}",
                        "Materialized view is refreshed but not queried in last 30 days; consider dropping or consolidating.",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class DataTransferMonitoringCheck(Rule):
    """COST_045: Flag high cross-region data transfer (WAF: monitor DATA_TRANSFER_HISTORY, minimize egress)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_045",
            "Data Transfer Monitoring",
            Severity.MEDIUM,
            rationale="High data egress and cross-region transfer increase cost; WAF recommends monitoring DATA_TRANSFER_HISTORY and minimizing egress.",
            remediation="Review replication and copy usage; keep data in same region where possible; use private links to reduce egress cost.",
            remediation_key="REDUCE_DATA_EGRESS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        # Flag accounts with high recent transfer volume (last 7 days) - threshold 100 GB
        query = """
        SELECT SUM(BYTES_TRANSFERRED), COUNT(*)
        FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
        WHERE TRANSFER_TYPE IN ('REPLICATION', 'COPY', 'DATA_LOAD', 'CLASSIC_EGRESS')
        AND START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        """
        try:
            cursor.execute(query)
            row = cursor.fetchone()
            if not row or row[0] is None:
                return []
            total_bytes = int(row[0])
            threshold_gb = 100 * (1024**3)
            if total_bytes >= threshold_gb:
                return [
                    self.violation(
                        "Account",
                        f"High data transfer in last 7 days: {total_bytes / (1024**3):.1f} GB. Review replication and egress.",
                    )
                ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return []


class QASEligibilityRecommendationCheck(Rule):
    """COST_010: Recommend enabling Query Acceleration for warehouses with eligible scan-heavy queries (WAF)."""

    MIN_ELIGIBLE_SECONDS = 300  # 5 min total eligible time in window

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_010",
            "QAS Eligibility Recommendation",
            Severity.MEDIUM,
            rationale="WAF: Enable Query Acceleration on warehouse for outlier scan-heavy queries; QUERY_ACCELERATION_ELIGIBLE shows queries that could benefit.",
            remediation="ALTER WAREHOUSE <name> SET ENABLE_QUERY_ACCELERATION = TRUE; consider QUERY_ACCELERATION_MAX_SCALE_FACTOR.",
            remediation_key="ENABLE_QAS",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = f"""
        SELECT WAREHOUSE_NAME, SUM(COALESCE(ELIGIBLE_QUERY_ACCELERATION_TIME, 0)) AS TOTAL_ELIGIBLE_SEC, COUNT(*) AS ELIGIBLE_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
        GROUP BY WAREHOUSE_NAME
        HAVING SUM(COALESCE(ELIGIBLE_QUERY_ACCELERATION_TIME, 0)) >= {self.MIN_ELIGIBLE_SECONDS}
        ORDER BY TOTAL_ELIGIBLE_SEC DESC
        LIMIT 20
        """
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                wh_name, eligible_sec, eligible_count = row[0], row[1], row[2]
                violations.append(
                    self.violation(
                        wh_name,
                        f"Warehouse has {eligible_count} QAS-eligible queries ({eligible_sec:.0f}s eligible time) in last 7 days; enable ENABLE_QUERY_ACCELERATION.",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class AutomaticClusteringCostBenefitCheck(Rule):
    """COST_014: Flag tables with high automatic clustering credit consumption for cost/benefit review (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_014",
            "Automatic Clustering Cost/Benefit",
            Severity.MEDIUM,
            rationale="WAF: Overuse of clustering keys can significantly increase clustering costs; review credit consumption vs query pruning benefit.",
            remediation="Review clustering key necessity; consider reducing expressions or disabling clustering for low-value tables.",
            remediation_key="REVIEW_CLUSTERING_COST",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, SUM(CREDITS_USED) AS TOTAL_CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
        WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB
            + """
        GROUP BY DATABASE_NAME, SCHEMA_NAME, TABLE_NAME
        HAVING SUM(CREDITS_USED) > 1
        ORDER BY TOTAL_CREDITS DESC
        LIMIT 30
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, table, total_credits = row[0], row[1], row[2], row[3]
                violations.append(
                    self.violation(
                        f"{db}.{schema}.{table}",
                        f"High automatic clustering cost in last 30 days: {total_credits:.2f} credits; review cost vs pruning benefit.",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class SearchOptimizationCostBenefitCheck(Rule):
    """COST_015: Flag high search optimization credit consumption for cost/benefit review (WAF)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_015",
            "Search Optimization Cost/Benefit",
            Severity.MEDIUM,
            rationale="WAF: Excessive indexed columns, especially on high-churn tables, can make SOS maintenance costs substantial.",
            remediation="Review search optimization usage; remove indexes on rarely-queried columns or high-churn tables.",
            remediation_key="REVIEW_SEARCH_OPTIMIZATION_COST",
            telemetry=telemetry,
        )

    def check_online(
        self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None, **_kw
    ) -> list[Violation]:
        query = (
            """
        SELECT DATABASE_NAME, SCHEMA_NAME, SUM(CREDITS_USED) AS TOTAL_CREDITS, COUNT(*) AS OPS
        FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
        WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
        """
            + SQL_EXCLUDE_SYSTEM_AND_SNOWFORT_DB
            + """
        GROUP BY DATABASE_NAME, SCHEMA_NAME
        HAVING SUM(CREDITS_USED) > 1
        ORDER BY TOTAL_CREDITS DESC
        LIMIT 30
        """
        )
        try:
            cursor.execute(query)
            violations = []
            for row in cursor.fetchall():
                db, schema, total_credits, ops = row[0], row[1], row[2], row[3]
                violations.append(
                    self.violation(
                        f"{db}.{schema}",
                        f"High search optimization cost in last 30 days: {total_credits:.2f} credits ({ops} ops); review index usage.",
                    )
                )
            return violations
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


class InactiveUserLicenseImpactCheck(Rule):
    """COST_047: Users with no login in 90d still holding active role grants (license waste)."""

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_047",
            "Inactive User License Impact",
            Severity.LOW,
            rationale=(
                "Users who have not logged in for an extended period but still hold active role "
                "grants consume license seats and increase attack surface without business value."
            ),
            remediation=(
                "Disable inactive users (ALTER USER <name> SET DISABLED = TRUE) or revoke their "
                "role grants. Consider automated lifecycle management via SCIM provisioning."
            ),
            telemetry=telemetry,
        )
        if conventions is None:
            self._inactive_days = SecurityPostureThresholds().inactive_user_days
        else:
            self._inactive_days = conventions.thresholds.security_posture.inactive_user_days

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        query = (
            "SELECT u.NAME, u.LAST_SUCCESS_LOGIN, COUNT(g.ROLE) AS grant_count"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u"
            " JOIN SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS g"
            "  ON g.GRANTEE_NAME = u.NAME AND g.DELETED_ON IS NULL"
            " WHERE u.DELETED_ON IS NULL"
            "  AND u.DISABLED = 'false'"
            "  AND u.TYPE != 'SERVICE'"
            f"  AND (u.LAST_SUCCESS_LOGIN IS NULL OR u.LAST_SUCCESS_LOGIN < DATEADD(day, -{self._inactive_days}, CURRENT_TIMESTAMP()))"
            " GROUP BY u.NAME, u.LAST_SUCCESS_LOGIN"
            " ORDER BY grant_count DESC"
            " LIMIT 50"
        )
        try:
            cursor.execute(query)
            return [
                Violation(
                    self.id,
                    str(row[0]),
                    f"User '{row[0]}' has not logged in for >{self._inactive_days} days but holds {row[2]} active role grant(s).",
                    self.severity,
                )
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
