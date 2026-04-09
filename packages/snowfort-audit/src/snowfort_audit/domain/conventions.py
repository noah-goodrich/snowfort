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
