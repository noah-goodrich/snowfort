"""Snowfort opinionated conventions. Pure domain data structures and merge logic."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any


@dataclass(frozen=True)
class WarehouseConventions:
    """Warehouse-related defaults."""

    auto_suspend_seconds: int = 30
    max_statement_timeout_seconds: int = 3600
    scaling_policy_mcw: str = "ECONOMY"


@dataclass(frozen=True)
class NamingConventions:
    """Naming patterns for objects."""

    env_prefix_pattern: str = r"^(DEV|STG|PRD)_"
    warehouse_pattern: str = r"^(DEV|STG|PRD)_\w+_(XSMALL|SMALL|MEDIUM|LARGE|XLARGE|XXLARGE|XXXLARGE)$"
    service_account_prefix: str = "SVC_"
    db_owner_role_suffix: str = "_OWNER"


@dataclass(frozen=True)
class SecurityConventions:
    """Security and auth defaults."""

    require_mfa_all_users: bool = True
    require_network_policy: bool = True
    max_account_admins: int = 3
    min_account_admins: int = 2
    # Fraction of non-SERVICE users with ext_authn_uid required to flip sso_enforced=True.
    sso_threshold: float = 0.5


@dataclass(frozen=True)
class TagConventions:
    """Tag keys expected for governance and IaC."""

    required_tags: tuple[str, ...] = ("COST_CENTER", "OWNER", "ENVIRONMENT")
    iac_tags: tuple[str, ...] = ("MANAGED_BY",)


@dataclass(frozen=True)
class HighChurnThresholds:
    """Thresholds for the high-churn permanent-table rule (COST_012)."""

    rows_per_day_threshold: int = 1_000_000
    # Glob-style patterns for table names to exclude (e.g. CDC staging tables).
    exclude_name_patterns: tuple[str, ...] = ()
    # Regex: tables whose schema name matches are routed to category=EXPECTED with a
    # transient-conversion remediation instead of ACTIONABLE. Matches common CDC tooling.
    cdc_schema_pattern: str = r"(?i)(staging|raw|cdc|fivetran|airbyte|stitch|hevo)"


@dataclass(frozen=True)
class MandatoryTaggingThresholds:
    """Thresholds for the mandatory-tagging rule (OPS_001)."""

    # Glob-style patterns for warehouse names to exclude from tagging requirements.
    exclude_warehouse_patterns: tuple[str, ...] = ("COMPUTE_SERVICE_WH_*",)


@dataclass(frozen=True)
class NetworkPerimeterThresholds:
    """Thresholds for network-perimeter and zombie-user rules (SEC_003, SEC_007)."""

    # When True, SSO is confirmed enforced — downgrade severity of SSO-adjacent rules.
    sso_downgrade: bool = False


@dataclass(frozen=True)
class WarehouseSizingThresholds:
    """Thresholds for warehouse utilization / consolidation / sizing rules (Directive B)."""

    # P50 running-load ratio below which a warehouse is considered underutilized.
    utilization_underused_p50: float = 0.10
    # P50 queued-load ratio above which a warehouse is considered overloaded.
    utilization_overloaded_p50_queue: float = 0.20
    # P50 query duration (seconds) below which queries are classified as short / interactive.
    workload_split_short_p50_seconds: float = 5.0
    # P50 query duration (seconds) above which queries are classified as long / batch.
    workload_split_long_p50_seconds: float = 60.0
    # Warehouses with zero queries in this many days are flagged as dormant.
    dormant_days: int = 30
    # Default lookback window (days) for sizing analysis.
    lookback_days: int = 30
    # PERF_021: P95/P50 query duration ratio above which a warehouse is flagged.
    duration_anomaly_ratio: float = 10.0
    # PERF_023: P75 inter-query gap > auto_suspend × this ratio → already aggressive.
    auto_suspend_aggressive_ratio: float = 10.0
    # COST_034: combined P50 utilization of two warehouses must be below this to flag.
    consolidation_combined_p50_max: float = 0.60
    # COST_035: Snowflake credit price used for dollar-denominated savings projections.
    credit_price_per_hour: float = 3.0


@dataclass(frozen=True)
class StorageThresholds:
    """Thresholds for storage-optimization rules (Directive B)."""

    cold_table_min_bytes: int = 107_374_182_400  # 100 GB
    cold_table_max_queries_per_week: int = 1
    clone_stale_days: int = 90
    clone_max_per_schema: int = 5
    excessive_retention_min_bytes: int = 1_099_511_627_776  # 1 TB
    excessive_retention_min_days: int = 7


@dataclass(frozen=True)
class RbacThresholds:
    """Thresholds for RBAC topology rules (Directive C)."""

    max_account_admins: int = 3
    god_role_privilege_threshold: int = 50
    god_role_database_span: int = 3
    privilege_concentration_gini_threshold: float = 0.80
    max_direct_roles_per_user: int = 10
    orphan_role_percent_threshold: int = 20
    # Regex patterns for role hierarchy layers (configurable, not hard-coded).
    dbo_role_pattern: str = r"(?i).*_(OWNER|DBO|DDL)$"
    functional_role_pattern: str = r"(?i).*_(READ|WRITE|TRANSFORM|ANALYST)$"
    business_role_pattern: str = r"(?i).*_(TEAM|DEPT|BU)$"


@dataclass(frozen=True)
class ColumnPatternDef:
    """A single column-name pattern and the sensitivity category it represents."""

    pattern: str
    category: str


@dataclass(frozen=True)
class SensitiveDataThresholds:
    """Thresholds and patterns for sensitive data detection (Directive D, GOV_030–034)."""

    # Column-name patterns that suggest sensitive data (case-insensitive substring match).
    column_patterns: tuple[ColumnPatternDef, ...] = (
        ColumnPatternDef(r"(?i)(^|_)ssn(_|$)", "PII_SSN"),
        ColumnPatternDef(r"(?i)(^|_)email(_|$)", "PII_EMAIL"),
        ColumnPatternDef(r"(?i)(^|_)phone(_|$)", "PII_PHONE"),
        ColumnPatternDef(r"(?i)(^|_)(dob|date_of_birth|birth_date)(_|$)", "PII_DOB"),
        ColumnPatternDef(r"(?i)(^|_)salary(_|$)", "PII_SALARY"),
        ColumnPatternDef(r"(?i)(^|_)(credit_card|card_number|cc_num)(_|$)", "PCI_CARD"),
        ColumnPatternDef(r"(?i)(^|_)passport(_|$)", "PII_PASSPORT"),
        ColumnPatternDef(r"(?i)(^|_)(password|passwd|pwd)(_|$)", "SECRET_PASSWORD"),
        ColumnPatternDef(r"(?i)(^|_)(address|addr)(_|$)", "PII_ADDRESS"),
        ColumnPatternDef(r"(?i)(^|_)(ip_addr|ip_address|ipaddr)(_|$)", "PII_IP"),
    )
    # Minimum number of sensitive columns in a table to trigger GOV_030 (unmasked).
    min_sensitive_columns_unmasked: int = 1
    # Minimum number of sensitive columns in a table to trigger GOV_031 (untagged).
    min_sensitive_columns_untagged: int = 1
    # Row-access policy absent: minimum sensitive column count to trigger GOV_032.
    min_sensitive_columns_no_row_policy: int = 3
    # GOV_033: maximum number of distinct roles that may SELECT from a sensitive table.
    max_roles_accessing_sensitive_table: int = 10
    # GOV_034: sample-based content scanning (opt-in, disabled by default).
    enable_content_sampling: bool = False
    # Number of rows to sample when content scanning is enabled.
    content_sample_rows: int = 100


@dataclass(frozen=True)
class CortexThresholds:
    """Per-feature cost thresholds for Cortex governance rules (COST_016–COST_033)."""

    daily_credit_hard_limit: float = 100.0
    daily_credit_soft_limit: float = 50.0
    # Allowlisted model names. Empty tuple means any model is acceptable.
    model_allowlist_expected: tuple[str, ...] = ()
    analyst_max_requests_per_user_per_day: int = 1000
    snowflake_intelligence_max_daily_credits: float = 50.0


@dataclass(frozen=True)
class RuleThresholdConventions:
    """Rule-level thresholds. Separate from SnowfortConventions so each session
    can add its own nested block without touching core convention defaults."""

    # COST_001 B2: warehouses with auto_suspend > this are flagged HIGH (too slow to reclaim).
    warehouse_auto_suspend_max_seconds: int = 3600
    # SEC_007 B5: users with no login in this many days are considered zombie users.
    zombie_user_days: int = 90
    high_churn: HighChurnThresholds = field(default_factory=HighChurnThresholds)
    mandatory_tagging: MandatoryTaggingThresholds = field(default_factory=MandatoryTaggingThresholds)
    network_perimeter: NetworkPerimeterThresholds = field(default_factory=NetworkPerimeterThresholds)
    cortex: CortexThresholds = field(default_factory=CortexThresholds)
    warehouse_sizing: WarehouseSizingThresholds = field(default_factory=WarehouseSizingThresholds)
    storage: StorageThresholds = field(default_factory=StorageThresholds)
    rbac: RbacThresholds = field(default_factory=RbacThresholds)
    sensitive_data: SensitiveDataThresholds = field(default_factory=SensitiveDataThresholds)


@dataclass(frozen=True)
class SnowfortConventions:
    """Single source of truth for Snowfort opinions. Override via pyproject.toml."""

    admin_database: str = "SNOWFORT"
    admin_role: str = "SNOWFORT"
    admin_user: str = "SVC_SNOWFORT"
    warehouse: WarehouseConventions = field(default_factory=WarehouseConventions)
    naming: NamingConventions = field(default_factory=NamingConventions)
    security: SecurityConventions = field(default_factory=SecurityConventions)
    tags: TagConventions = field(default_factory=TagConventions)
    thresholds: RuleThresholdConventions = field(default_factory=RuleThresholdConventions)


def _merge_dataclass(default: Any, overrides: dict[str, Any], cls: type) -> Any:
    """Merge override dict into a frozen dataclass instance. Returns new instance.

    Handles arbitrary nesting: any field whose current value is a dataclass instance
    is recursively merged when the override for that field is a dict.
    """
    if not overrides:
        return default
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        name = f.name
        if name not in overrides:
            kwargs[name] = getattr(default, name)
            continue
        ov = overrides[name]
        default_val = getattr(default, name)
        if is_dataclass(default_val):
            if isinstance(ov, dict):
                kwargs[name] = _merge_dataclass(default_val, ov, type(default_val))
            else:
                kwargs[name] = default_val
        elif isinstance(ov, list):
            kwargs[name] = tuple(ov)
        else:
            kwargs[name] = ov
    return cls(**kwargs)
