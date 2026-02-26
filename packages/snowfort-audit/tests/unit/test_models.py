"""Tests for domain.models."""

from snowfort_audit.domain.models import BootstrapRequestDTO, PricingConfig, WarehouseSpec


def test_pricing_config_defaults():
    p = PricingConfig()
    assert p.currency == "USD"
    assert "enterprise" in p.compute_prices


def test_warehouse_spec():
    w = WarehouseSpec("LARGE", "STANDARD")
    assert w.size == "LARGE"
    assert w.wh_type == "STANDARD"


def test_bootstrap_request_dto():
    d = BootstrapRequestDTO(admin_role="AR", auditor_role="AUD", target_warehouse="WH", target_user="U")
    assert d.admin_role == "AR"
    assert d.target_user == "U"
