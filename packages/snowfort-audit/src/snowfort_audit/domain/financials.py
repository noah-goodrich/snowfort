from typing import ClassVar

from snowfort_audit.domain.models import PricingConfig, WarehouseSpec
from snowfort_audit.domain.warehouse_specs import get_warehouse_specs


class FinancialEvaluator:
    """Domain logic for pricing and cost calculations."""

    def __init__(self, config: PricingConfig):
        self.config = config

    # Credits per size mapping for reference/testing usage
    WAREHOUSE_CREDITS: ClassVar[dict[str, int]] = {
        "X-SMALL": 1,
        "SMALL": 2,
        "MEDIUM": 4,
        "LARGE": 8,
        "X-LARGE": 16,
        "2X-LARGE": 32,
        "3X-LARGE": 64,
        "4X-LARGE": 128,
        "5X-LARGE": 256,
        "6X-LARGE": 512,
    }

    def get_credit_consumption(self, size: str, type_str: str = "STANDARD") -> float:
        """Returns credits/hour for a given size and type."""
        specs = get_warehouse_specs(size, type_str)
        base_credits = float(specs["nodes"])

        # Snowpark Optimized multiplier -> 1.5x of Standard
        if "SNOWPARK-OPTIMIZED" in type_str.upper():
            return base_credits * 1.5

        return base_credits

    def calculate_cost_delta(self, current: WarehouseSpec, target: WarehouseSpec, active_hours: float) -> float:
        """
        Calculates the cost difference ($) for running target instead of current.
        Positive result means Cost Increase. Negative means Cost Savings.
        """
        # Use injected config prices
        price_per_credit = self.config.compute_prices.get("enterprise", {}).get("standard", 3.00)

        current_credits = self.get_credit_consumption(current.size, current.wh_type)
        target_credits = self.get_credit_consumption(target.size, target.wh_type)

        credit_delta = target_credits - current_credits
        return credit_delta * active_hours * float(price_per_credit)

    def calculate_potential_savings(
        self,
        wh_size: str,
        current_suspend_s: int,
        optimal_suspend_s: int = 1,
        wh_type: str = "STANDARD",
        daily_resumes: int = 20,
    ) -> float:
        """
        Estimates daily savings ($) if auto_suspend is reduced from current to optimal.
        Assumes warehouses are billed in 1s increments after the first 60s.
        """
        price_per_credit = self.config.compute_prices.get("enterprise", {}).get("standard", 3.00)
        credits_per_hour = self.get_credit_consumption(wh_size, wh_type)
        credits_per_second = credits_per_hour / 3600.0

        # Time wasted per resume (seconds)
        # Note: If current_suspend < 60, Snowflake still bills 60s for the first minute.
        # But here we focus on the tail end of the idle time.
        idle_time_saved_per_resume = max(0, current_suspend_s - optimal_suspend_s)

        daily_credits_saved = idle_time_saved_per_resume * daily_resumes * credits_per_second
        return daily_credits_saved * float(price_per_credit)

    MILLION_THRESHOLD = 1_000_000
    THOUSAND_THRESHOLD = 1_000

    @staticmethod
    def format_currency(amount: float) -> str:
        """Formats float to $1.2k string."""
        currency_symbol = "$"
        amount_abs = abs(amount)
        sign = "-" if amount < 0 else ""

        if amount_abs >= FinancialEvaluator.MILLION_THRESHOLD:
            return f"{sign}{currency_symbol}{amount_abs / FinancialEvaluator.MILLION_THRESHOLD:.1f}M"
        if amount_abs >= FinancialEvaluator.THOUSAND_THRESHOLD:
            return f"{sign}{currency_symbol}{amount_abs / FinancialEvaluator.THOUSAND_THRESHOLD:.1f}k"

        return f"{sign}{currency_symbol}{amount_abs:.2f}"
