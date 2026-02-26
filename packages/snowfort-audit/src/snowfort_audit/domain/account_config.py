"""Runtime account context: topology and environment names. Pure domain defaults."""

from __future__ import annotations

from typing import Any

ACCOUNT_TOPOLOGY_MULTI_ENV = "multi_env_single_account"
ACCOUNT_TOPOLOGY_ONE_PER_ACCOUNT = "single_env_per_account"
DEFAULT_ENVIRONMENTS = ["DEV", "STG", "PRD"]


def _default_config() -> dict[str, Any]:
    return {
        "account_topology": ACCOUNT_TOPOLOGY_MULTI_ENV,
        "environments": list(DEFAULT_ENVIRONMENTS),
    }
