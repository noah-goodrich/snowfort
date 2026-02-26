"""Tests for account_config module."""

from pathlib import Path

from snowfort_audit.domain.account_config import (
    ACCOUNT_TOPOLOGY_MULTI_ENV,
    DEFAULT_ENVIRONMENTS,
)
from snowfort_audit.infrastructure.config_loader import (
    config_path,
    ensure_account_config,
    load_account_config,
)


def test_config_path():
    root = Path("/project")
    assert config_path(root) == Path("/project/.snowfort/config.yml")


def test_load_account_config_missing_returns_defaults(tmp_path):
    cfg = load_account_config(tmp_path)
    assert cfg["account_topology"] == ACCOUNT_TOPOLOGY_MULTI_ENV
    assert cfg["environments"] == list(DEFAULT_ENVIRONMENTS)


def test_load_account_config_with_file(tmp_path):
    config_dir = tmp_path / ".snowfort"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("account_topology: single_env_per_account\nenvironments: [DEV, PRD]\n", encoding="utf-8")
    cfg = load_account_config(tmp_path)
    assert cfg["account_topology"] == "single_env_per_account"
    assert cfg["environments"] == ["DEV", "PRD"]


def test_ensure_account_config_existing_returns_loaded(tmp_path):
    config_dir = tmp_path / ".snowfort"
    config_dir.mkdir()
    (config_dir / "config.yml").write_text(
        "account_topology: multi_env_single_account\nenvironments: [DEV]\n", encoding="utf-8"
    )
    cfg = ensure_account_config(tmp_path, prompt_fn=None)
    assert cfg["account_topology"] == "multi_env_single_account"
    assert cfg["environments"] == ["DEV"]


def test_ensure_account_config_missing_no_prompt_returns_defaults(tmp_path):
    cfg = ensure_account_config(tmp_path, prompt_fn=None)
    assert cfg["account_topology"] == ACCOUNT_TOPOLOGY_MULTI_ENV


def test_ensure_account_config_missing_with_prompt_writes_config(tmp_path):
    def prompt(_root):
        return {"account_topology": "single_env_per_account", "environments": ["DEV", "PRD"]}

    cfg = ensure_account_config(tmp_path, prompt_fn=prompt)
    assert cfg["account_topology"] == "single_env_per_account"
    assert (tmp_path / ".snowfort" / "config.yml").exists()
    assert "single_env_per_account" in (tmp_path / ".snowfort" / "config.yml").read_text()


def test_load_account_config_invalid_yaml_returns_defaults(tmp_path):
    (tmp_path / ".snowfort").mkdir()
    (tmp_path / ".snowfort" / "config.yml").write_text("not: valid: yaml: [[[", encoding="utf-8")
    cfg = load_account_config(tmp_path)
    assert cfg["account_topology"] == ACCOUNT_TOPOLOGY_MULTI_ENV
    assert cfg["environments"] == list(DEFAULT_ENVIRONMENTS)
