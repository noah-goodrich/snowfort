"""Composition root: registers Infrastructure and UseCase implementations with the container.

This module is the only place that imports Infrastructure into the wiring flow.
The DI container (Interface layer) stays free of Infrastructure imports.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway
from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.infrastructure.calculator_interrogator import CalculatorInterrogator
from snowfort_audit.infrastructure.config_loader import (
    ensure_account_config,
    get_financial_overrides_from_pyproject,
    load_account_config,
    load_conventions,
)
from snowfort_audit.infrastructure.cortex_synthesizer import CortexSynthesizer
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError
from snowfort_audit.infrastructure.gateways.sql_validator import SqlFluffValidatorGateway
from snowfort_audit.infrastructure.pricing_repository import YamlPricingRepository
from snowfort_audit.infrastructure.repositories.governance import SnowflakeGovernanceRepository
from snowfort_audit.infrastructure.repositories.manifest import YamlManifestRepository
from snowfort_audit.infrastructure.repositories.snowpark_audit_repository import (
    SnowparkAuditRepository,
)
from snowfort_audit.infrastructure.rule_registry import get_all_rules, get_rules
from snowfort_audit.use_cases.bootstrap import BootstrapUseCase
from snowfort_audit.use_cases.offline_scan import OfflineScanUseCase
from snowfort_audit.use_cases.online_scan import OnlineScanUseCase

if TYPE_CHECKING:
    from snowfort_audit.di.container import AuditContainer


def register_all(container: "AuditContainer") -> None:
    """Register all Infrastructure and UseCase dependencies on the container."""
    # Protocols
    container.register_singleton("SQLValidatorProtocol", SqlFluffValidatorGateway())

    # Governance
    container.register_factory(
        "GovernanceProtocol",
        lambda: SnowflakeGovernanceRepository(container.get("SnowflakeQueryProtocol")),
    )

    # Pricing
    fs = container.get("FileSystemProtocol")
    base_path = Path(__file__).resolve().parent.parent
    pricing_path = str(base_path / "resources" / "pricing.yaml")
    pricing_repo = YamlPricingRepository(fs, pricing_path)
    container.register_singleton("PricingRepository", pricing_repo)

    # Manifest
    manifest_repo = YamlManifestRepository(fs)
    container.register_singleton("ManifestRepositoryProtocol", manifest_repo)

    # Financial evaluator
    config = pricing_repo.get_pricing_config()
    overrides = get_financial_overrides_from_pyproject()
    if overrides:
        new_prices = config.compute_prices.copy()
        if "standard_credit_price" in overrides:
            if "standard" not in new_prices:
                new_prices["standard"] = {}
            new_prices["standard"]["standard"] = float(overrides["standard_credit_price"])
        if "enterprise_credit_price" in overrides:
            if "enterprise" not in new_prices:
                new_prices["enterprise"] = {}
            new_prices["enterprise"]["standard"] = float(overrides["enterprise_credit_price"])
        config = PricingConfig(currency=config.currency, compute_prices=new_prices)
    evaluator = FinancialEvaluator(config)
    container.register_singleton("FinancialEvaluator", evaluator)

    # Use case factories (wiring builds them via container.get / container.get_rules only)
    def _make_online_scan():
        return OnlineScanUseCase(
            container.get("SnowflakeClient"),
            container.get_rules(),
            container.get("TelemetryPort"),
            conventions=load_conventions(Path.cwd()),
        )

    def _make_offline_scan():
        return OfflineScanUseCase(
            container.get("FileSystemProtocol"),
            container.get("ManifestRepositoryProtocol"),
            container.get_rules(),
            container.get("TelemetryPort"),
        )

    def _make_bootstrap():
        return BootstrapUseCase(
            container.get("GovernanceProtocol"),
            container.get("TelemetryPort"),
        )

    container.register_factory("OnlineScanUseCase", _make_online_scan)
    container.register_factory("OfflineScanUseCase", _make_offline_scan)
    container.register_factory("BootstrapUseCase", _make_bootstrap)

    # Audit repository (session resolved when factory is called)
    def _audit_repo_factory():
        try:
            session = container.get("SnowparkSession")
        except ValueError:
            session = None
        return SnowparkAuditRepository(session)

    container.register_factory("AuditRepository", _audit_repo_factory)

    # CLI / Interface-visible infra (no direct infra imports in Interface)
    container.register_singleton("CalculatorInterrogatorClass", CalculatorInterrogator)
    container.register_singleton("CortexSynthesizerClass", CortexSynthesizer)
    container.register_singleton("get_all_rules", get_all_rules)
    container.register_singleton("load_conventions", load_conventions)
    container.register_singleton("get_rules_fn", get_rules)
    container.register_singleton("ensure_account_config", ensure_account_config)
    container.register_singleton("SnowflakeGatewayFactory", SnowflakeGateway)
    container.register_singleton("ConnectionErrorType", SnowflakeConnectorError)
    container.register_singleton("load_account_config", load_account_config)
