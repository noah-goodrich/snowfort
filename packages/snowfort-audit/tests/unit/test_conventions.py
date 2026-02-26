"""Tests for conventions module."""

import pytest

from snowfort_audit.domain.conventions import (
    NamingConventions,
    SecurityConventions,
    SnowfortConventions,
    WarehouseConventions,
)
from snowfort_audit.infrastructure.config_loader import load_conventions


def test_default_conventions():
    c = SnowfortConventions()
    assert c.admin_database == "SNOWFORT"
    assert c.admin_role == "SNOWFORT"
    assert c.admin_user == "SVC_SNOWFORT"
    assert c.warehouse.auto_suspend_seconds == 1
    assert "COST_CENTER" in c.tags.required_tags


def test_warehouse_conventions_defaults():
    w = WarehouseConventions()
    assert w.auto_suspend_seconds == 1
    assert w.max_statement_timeout_seconds == 3600
    assert w.scaling_policy_mcw == "ECONOMY"


def test_naming_conventions_defaults():
    n = NamingConventions()
    assert "DEV" in n.env_prefix_pattern
    assert n.service_account_prefix == "SVC_"
    assert n.db_owner_role_suffix == "_OWNER"


def test_load_conventions_no_pyproject_returns_defaults(tmp_path):
    assert not (tmp_path / "pyproject.toml").exists()
    c = load_conventions(tmp_path)
    assert c.admin_database == "SNOWFORT"
    assert c.warehouse.auto_suspend_seconds == 1


def test_load_conventions_with_pyproject_overrides(tmp_path):
    pytest.importorskip("tomli")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.snowfort.conventions]\nadmin_database = "CUSTOM_DB"\n\n'
        "[tool.snowfort.conventions.warehouse]\nauto_suspend_seconds = 60\n",
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.admin_database == "CUSTOM_DB"
    assert c.warehouse.auto_suspend_seconds == 60


def test_load_conventions_list_converted_to_tuple(tmp_path):
    pytest.importorskip("tomli")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.snowfort.conventions.tags]\nrequired_tags = ["COST_CENTER", "OWNER", "TEAM"]\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert isinstance(c.tags.required_tags, tuple)
    assert "TEAM" in c.tags.required_tags
    assert "OWNER" in c.tags.required_tags


def test_load_conventions_none_project_root_uses_cwd():
    c = load_conventions(None)
    assert c.admin_database == "SNOWFORT"


def test_security_conventions_defaults():
    s = SecurityConventions()
    assert s.require_mfa_all_users is True
    assert s.max_account_admins == 3


def test_load_conventions_invalid_toml_returns_defaults(tmp_path):
    (tmp_path / "pyproject.toml").write_text("not valid toml {{{ ", encoding="utf-8")
    c = load_conventions(tmp_path)
    assert c.admin_database == "SNOWFORT"


def test_load_conventions_conventions_not_dict_returns_defaults(tmp_path):
    pytest.importorskip("tomli")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.snowfort]\nconventions = "string"\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.admin_database == "SNOWFORT"


def test_load_conventions_naming_override(tmp_path):
    pytest.importorskip("tomli")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.snowfort.conventions.naming]\nservice_account_prefix = "SVCX_"\n',
        encoding="utf-8",
    )
    c = load_conventions(tmp_path)
    assert c.naming.service_account_prefix == "SVCX_"
