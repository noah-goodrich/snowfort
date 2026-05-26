"""Tests for DI container resolution."""

from unittest.mock import MagicMock

from snowfort_audit.di.container import AuditContainer
from snowfort_audit.infrastructure.wiring import register_all


def test_container_resolves_offline_scan_use_case():
    """AuditContainer.get('OfflineScanUseCase') returns an OfflineScanUseCase instance."""
    container = AuditContainer()
    register_all(container)
    use_case = container.get("OfflineScanUseCase")
    assert use_case is not None
    assert hasattr(use_case, "execute")


def test_container_get_rules_returns_list():
    """AuditContainer.get_rules() returns a non-empty list of rules."""
    container = AuditContainer()
    register_all(container)
    rules = container.get_rules()
    assert isinstance(rules, list)
    assert len(rules) > 0
    assert hasattr(rules[0], "id")


def test_container_resolves_online_scan_use_case_when_client_registered():
    """When SnowflakeClient is registered, get('OnlineScanUseCase') returns OnlineScanUseCase."""
    container = AuditContainer()
    register_all(container)
    mock_gateway = MagicMock()
    container.register_singleton("SnowflakeClient", mock_gateway)
    use_case = container.get("OnlineScanUseCase")
    assert use_case is not None
    assert hasattr(use_case, "execute")


def test_container_excludes_default_disabled_rules_by_default():
    """Default get_rules() excludes rules marked default_disabled (SEC_008 is one)."""
    container = AuditContainer()
    register_all(container)
    rules = container.get_rules()
    rule_ids = {r.id for r in rules}
    assert "SEC_008" not in rule_ids


def test_container_includes_default_disabled_rules_when_explicitly_opted_in():
    """Passing --rules SEC_008 re-enables the default-disabled rule."""
    container = AuditContainer()
    register_all(container)
    container.register_singleton("ScanRuleIds", frozenset({"SEC_008"}))
    rules = container.get_rules()
    rule_ids = {r.id for r in rules}
    assert "SEC_008" in rule_ids
