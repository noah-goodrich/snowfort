"""Infrastructure: file-based config loaders for account config and conventions.

Moved from domain layer to avoid yaml/tomli/pathlib I/O imports in domain.
Domain modules (account_config, conventions) keep pure data structures and defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from snowfort_audit.domain.account_config import (
    ACCOUNT_TOPOLOGY_MULTI_ENV,
    DEFAULT_ENVIRONMENTS,
    _default_config,
)
from snowfort_audit.domain.conventions import (
    NamingConventions,
    SecurityConventions,
    SnowfortConventions,
    TagConventions,
    WarehouseConventions,
    _merge_dataclass,
)

try:
    import tomli
except ImportError:
    tomli = None  # type: ignore[assignment]


def config_path(project_root: Path) -> Path:
    """Path to .snowfort/config.yml under project root."""
    return project_root / ".snowfort" / "config.yml"


def load_account_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load account config from .snowfort/config.yml. Returns defaults if missing or invalid."""
    if project_root is None:
        project_root = Path.cwd()
    path = config_path(project_root)
    if not path.exists():
        return _default_config()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {
            "account_topology": data.get("account_topology", ACCOUNT_TOPOLOGY_MULTI_ENV),
            "environments": data.get("environments", DEFAULT_ENVIRONMENTS),
        }
    except Exception:
        return _default_config()


def ensure_account_config(project_root: Path | None = None, prompt_fn: Any = None) -> dict[str, Any]:
    """Load config; if missing, run prompt_fn to gather answers, write .snowfort/config.yml, return config."""
    if project_root is None:
        project_root = Path.cwd()
    path = config_path(project_root)
    if path.exists():
        return load_account_config(project_root)
    if prompt_fn is None:
        return _default_config()
    config = prompt_fn(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return config


def get_financial_overrides_from_pyproject(project_root: Path | None = None) -> dict[str, Any]:
    """Read [tool.snowfort.audit] from pyproject.toml. Returns {} if missing or invalid."""
    if project_root is None:
        project_root = Path.cwd()
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists() or not tomli:
        return {}
    try:
        data = tomli.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get("tool", {}).get("snowfort", {}).get("audit", {}) or {}


def load_conventions(project_root: Path | None = None) -> SnowfortConventions:
    """Load defaults, then overlay [tool.snowfort.conventions] from pyproject.toml."""
    defaults = SnowfortConventions(
        warehouse=WarehouseConventions(),
        naming=NamingConventions(),
        security=SecurityConventions(),
        tags=TagConventions(),
    )
    if project_root is None:
        project_root = Path.cwd()
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists() or not tomli:
        return defaults
    try:
        data = tomli.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    overrides = data.get("tool", {}).get("snowfort", {}).get("conventions", {})
    if not overrides or not isinstance(overrides, dict):
        return defaults
    return _merge_dataclass(defaults, overrides, SnowfortConventions)
