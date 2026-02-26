"""Snowfort opinionated conventions. Pure domain data structures and merge logic."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass(frozen=True)
class WarehouseConventions:
    """Warehouse-related defaults."""

    auto_suspend_seconds: int = 1
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
class SnowfortConventions:
    """Single source of truth for Snowfort opinions. Override via pyproject.toml."""

    admin_database: str = "SNOWFORT"
    admin_role: str = "SNOWFORT"
    admin_user: str = "SVC_SNOWFORT"
    warehouse: WarehouseConventions = field(default_factory=WarehouseConventions)
    naming: NamingConventions = field(default_factory=NamingConventions)
    security: SecurityConventions = field(default_factory=SecurityConventions)
    tags: TagConventions = field(default_factory=TagConventions)


def _merge_dataclass(default: Any, overrides: dict[str, Any], cls: type) -> Any:
    """Merge override dict into a frozen dataclass instance. Returns new instance."""
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
        if isinstance(default_val, (WarehouseConventions, NamingConventions, SecurityConventions, TagConventions)):
            if isinstance(ov, dict):
                kwargs[name] = _merge_dataclass(default_val, ov, type(default_val))
            else:
                kwargs[name] = default_val
        elif isinstance(ov, list):
            kwargs[name] = tuple(ov)
        else:
            kwargs[name] = ov
    return cls(**kwargs)
