import logging
from typing import Any

import yaml

from snowfort_audit.domain.models import PricingConfig
from snowfort_audit.domain.protocols import FileSystemProtocol, PricingRepositoryProtocol

logger = logging.getLogger(__name__)


class YamlPricingRepository(PricingRepositoryProtocol):
    """Repository implementation for YAML-based pricing configuration."""

    def __init__(self, fs: FileSystemProtocol, pricing_path: str):
        self.fs = fs
        self.pricing_path = pricing_path

    def get_pricing_config(self) -> PricingConfig:
        """Loads and parses the pricing YAML file."""
        try:
            if not self.fs.exists(self.pricing_path):
                return PricingConfig()

            content = self.fs.read_text(self.pricing_path)
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                return PricingConfig()

            config_data: dict[str, Any] = data
            return PricingConfig(
                currency=config_data.get("currency", "USD"), compute_prices=config_data.get("compute", {})
            )
        except (yaml.YAMLError, OSError) as e:
            logger.error("Failed to load pricing config from %s: %s", self.pricing_path, e)
            return PricingConfig()
