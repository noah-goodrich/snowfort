from unittest.mock import MagicMock

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.models import PricingConfig, WarehouseSpec
from snowfort_audit.infrastructure.pricing_repository import YamlPricingRepository


class TestFinancials:
    PRICE_STANDARD_ENTERPRISE = 3.50
    CREDITS_XSMALL = FinancialEvaluator.WAREHOUSE_CREDITS["X-SMALL"]
    CREDITS_LARGE = FinancialEvaluator.WAREHOUSE_CREDITS["LARGE"]
    # Calculated 1.5x manually here for test expectation verification
    CREDITS_MEDIUM_SP = FinancialEvaluator.WAREHOUSE_CREDITS["MEDIUM"] * 1.5
    CREDITS_LARGE_SP = FinancialEvaluator.WAREHOUSE_CREDITS["LARGE"] * 1.5
    COST_DELTA_DOWNSIZE = -18.0
    COST_DELTA_UPSIZE = 60.0

    def test_repository_load(self):
        mock_fs = MagicMock()
        mock_fs.exists.return_value = True
        mock_fs.read_text.return_value = """
currency: USD
compute:
  enterprise:
    standard: 3.50
"""
        repo = YamlPricingRepository(mock_fs, "pricing.yaml")
        config = repo.get_pricing_config()

        assert config.currency == "USD"
        assert config.compute_prices["enterprise"]["standard"] == self.PRICE_STANDARD_ENTERPRISE

    def test_get_credit_consumption(self):
        evaluator = FinancialEvaluator(PricingConfig())
        # Standard Warehouse Credits
        assert evaluator.get_credit_consumption("X-Small", "STANDARD") == self.CREDITS_XSMALL
        assert evaluator.get_credit_consumption("Large", "STANDARD") == self.CREDITS_LARGE

        # Snowpark Optimized (1.5x)
        assert evaluator.get_credit_consumption("Medium", "SNOWPARK-OPTIMIZED") == self.CREDITS_MEDIUM_SP
        assert evaluator.get_credit_consumption("Large", "SNOWPARK-OPTIMIZED") == self.CREDITS_LARGE_SP

    def test_calculate_cost_delta(self):
        config = PricingConfig(currency="USD", compute_prices={"enterprise": {"standard": 3.00}})
        evaluator = FinancialEvaluator(config)

        # Scenario 1: Downsizing Large (8) to Small (2) for 1 hour
        # Credits Saved: 6. Cost Saved: $18.
        current = WarehouseSpec("Large", "STANDARD")
        target = WarehouseSpec("Small", "STANDARD")
        delta = evaluator.calculate_cost_delta(current, target, 1.0)
        assert delta == self.COST_DELTA_DOWNSIZE

        # Scenario 2: Upsizing Small (2) to Medium (4) for 10 hours
        # Credits Added: 2 * 10 = 20. Cost Added: $60.
        current = WarehouseSpec("Small", "STANDARD")
        target = WarehouseSpec("Medium", "STANDARD")
        delta = evaluator.calculate_cost_delta(current, target, 10.0)
        assert delta == self.COST_DELTA_UPSIZE

    def test_format_currency(self):
        assert FinancialEvaluator.format_currency(100.0) == "$100.00"
        assert FinancialEvaluator.format_currency(12000.0) == "$12.0k"
        assert FinancialEvaluator.format_currency(1500000.0) == "$1.5M"
        assert FinancialEvaluator.format_currency(-500.0) == "-$500.00"

    def test_calculate_potential_savings(self):
        config = PricingConfig(compute_prices={"enterprise": {"standard": 3.00}})
        evaluator = FinancialEvaluator(config)
        # Reduce auto_suspend from 600s to 1s, 20 resumes/day -> positive savings
        savings = evaluator.calculate_potential_savings(
            wh_size="MEDIUM",
            current_suspend_s=600,
            optimal_suspend_s=1,
            wh_type="STANDARD",
            daily_resumes=20,
        )
        assert savings > 0
