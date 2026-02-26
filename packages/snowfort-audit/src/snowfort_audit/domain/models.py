from dataclasses import dataclass, field

from snowfort_audit._vendor.entity import Entity


@dataclass(frozen=True)
class PricingConfig(Entity):
    """Configuration for financial evaluations."""

    currency: str = "USD"
    # Nested mapping: tier -> type -> price
    compute_prices: dict[str, dict[str, float]] = field(
        default_factory=lambda: {"enterprise": {"standard": 3.00, "snowpark_optimized": 3.00}}
    )


@dataclass(frozen=True)
class WarehouseSpec:
    """Represents a Snowflake Warehouse configuration."""

    size: str
    wh_type: str = "STANDARD"


@dataclass(frozen=True)
class BootstrapRequestDTO(Entity):
    """Request DTO for the Bootstrap Use Case."""

    admin_role: str
    auditor_role: str
    target_warehouse: str
    target_user: str
