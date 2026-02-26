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


def test_container_resolves_audit_repository():
    """get('AuditRepository') returns SnowparkAuditRepository (session may be None)."""
    container = AuditContainer()
    register_all(container)
    repo = container.get("AuditRepository")
    assert repo is not None
