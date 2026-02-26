from typing import Any


def get_warehouse_specs(size: str, type_str: str = "STANDARD") -> dict[str, Any]:
    """
    Returns warehouse specs: nodes, ram_gb, ram_factor (multiplier vs std).
    """
    norm_size = size.upper()
    norm_type = type_str.upper()

    # Standard RAM map (Approx GB per node)
    base_ram_per_node = 16

    # Node Map
    nodes_map = {
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

    nodes = nodes_map.get(norm_size, 1)  # Default to 1 if unknown

    # Snowpark optimization
    is_snowpark = "SNOWPARK-OPTIMIZED" in norm_type
    ram_multiplier = 16 if is_snowpark else 1

    return {"nodes": nodes, "ram_gb": nodes * base_ram_per_node * ram_multiplier, "ram_factor": ram_multiplier}
