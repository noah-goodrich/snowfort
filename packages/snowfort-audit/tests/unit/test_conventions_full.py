"""Comprehensive tests for domain/conventions.py: dataclasses, _merge_dataclass, load_conventions."""

from unittest.mock import patch

from snowfort_audit.domain.conventions import (
    NamingConventions,
    SecurityConventions,
    SnowfortConventions,
    TagConventions,
    WarehouseConventions,
    _merge_dataclass,
)
from snowfort_audit.infrastructure.config_loader import load_conventions


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


def test_security_conventions_defaults():
    s = SecurityConventions()
    assert s.require_mfa_all_users is True
    assert s.require_network_policy is True
    assert s.max_account_admins == 3
    assert s.min_account_admins == 2


def test_tag_conventions_defaults():
    t = TagConventions()
    assert "COST_CENTER" in t.required_tags
    assert "MANAGED_BY" in t.iac_tags


def test_snowfort_conventions_defaults():
    c = SnowfortConventions()
    assert c.admin_database == "SNOWFORT"
    assert c.admin_role == "SNOWFORT"
    assert c.admin_user == "SVC_SNOWFORT"
    assert isinstance(c.warehouse, WarehouseConventions)
    assert isinstance(c.naming, NamingConventions)
    assert isinstance(c.security, SecurityConventions)
    assert isinstance(c.tags, TagConventions)


def test_merge_dataclass_empty_overrides():
    w = WarehouseConventions()
    merged = _merge_dataclass(w, {}, WarehouseConventions)
    assert merged == w


def test_merge_dataclass_scalar_override():
    w = WarehouseConventions()
    merged = _merge_dataclass(w, {"auto_suspend_seconds": 60}, WarehouseConventions)
    assert merged.auto_suspend_seconds == 60
    assert merged.max_statement_timeout_seconds == 3600


def test_merge_dataclass_nested_override():
    c = SnowfortConventions()
    merged = _merge_dataclass(
        c,
        {"warehouse": {"auto_suspend_seconds": 120}, "admin_database": "MY_DB"},
        SnowfortConventions,
    )
    assert merged.warehouse.auto_suspend_seconds == 120
    assert merged.admin_database == "MY_DB"
    assert merged.warehouse.max_statement_timeout_seconds == 3600


def test_merge_dataclass_list_to_tuple():
    c = SnowfortConventions()
    merged = _merge_dataclass(
        c,
        {"tags": {"required_tags": ["A", "B"]}},
        SnowfortConventions,
    )
    assert merged.tags.required_tags == ("A", "B")


def test_merge_dataclass_nested_non_dict_ignored():
    c = SnowfortConventions()
    merged = _merge_dataclass(c, {"warehouse": "not_a_dict"}, SnowfortConventions)
    assert merged.warehouse == WarehouseConventions()


def test_load_conventions_no_pyproject(tmp_path):
    result = load_conventions(tmp_path)
    assert isinstance(result, SnowfortConventions)
    assert result.warehouse.auto_suspend_seconds == 1


def test_load_conventions_with_overrides(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.snowfort.conventions]\nadmin_database = "MY_AUDIT"\n\n'
        "[tool.snowfort.conventions.warehouse]\nauto_suspend_seconds = 300\n",
        encoding="utf-8",
    )
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    result = load_conventions(tmp_path)
    assert result.admin_database == "MY_AUDIT"
    assert result.warehouse.auto_suspend_seconds == 300


def test_load_conventions_invalid_toml(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("invalid {{{{ toml", encoding="utf-8")
    result = load_conventions(tmp_path)
    assert isinstance(result, SnowfortConventions)


def test_load_conventions_conventions_not_dict(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.snowfort]\nconventions = "not_a_dict"\n', encoding="utf-8")
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    result = load_conventions(tmp_path)
    assert result == SnowfortConventions()


def test_load_conventions_empty_conventions_section(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.snowfort.conventions]\n", encoding="utf-8")
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    result = load_conventions(tmp_path)
    assert result == SnowfortConventions()


def test_load_conventions_none_project_root():
    result = load_conventions(None)
    assert isinstance(result, SnowfortConventions)


def test_load_conventions_with_security_overrides(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[tool.snowfort.conventions.security]\nrequire_mfa_all_users = false\nmax_account_admins = 5\n",
        encoding="utf-8",
    )
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    result = load_conventions(tmp_path)
    assert result.security.require_mfa_all_users is False
    assert result.security.max_account_admins == 5


def test_load_conventions_with_naming_overrides(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.snowfort.conventions.naming]\nservice_account_prefix = "APP_"\n',
        encoding="utf-8",
    )
    try:
        import tomli  # noqa: F401
    except ImportError:
        return
    result = load_conventions(tmp_path)
    assert result.naming.service_account_prefix == "APP_"


def test_load_conventions_tomli_not_available(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.snowfort.conventions]\nadmin_database = "X"\n', encoding="utf-8")
    with patch("snowfort_audit.infrastructure.config_loader.tomli", None):
        result = load_conventions(tmp_path)
    assert result == SnowfortConventions()
