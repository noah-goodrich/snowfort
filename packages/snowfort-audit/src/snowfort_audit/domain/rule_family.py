"""ParameterizedRuleFamily: plain function for creating families of similar rules.

No metaclasses, no decorators hiding control flow. Each (rule_id, params) pair
produces exactly one Rule via the factory callable.

Used by:
  Session 4 — Cortex cost governance pack (COST_016–COST_033)
  Session 6 — E3/E4/E5 PolicyPresenceRule family
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from snowfort_audit.domain.rule_definitions import Rule


def ParameterizedRuleFamily(
    specs: list[tuple[str, dict[str, Any]]],
    factory: Callable[[str, dict[str, Any]], Rule],
) -> list[Rule]:
    """Create a list of Rule instances from a list of (rule_id, params) pairs.

    Plain function — no metaclasses, no decorators.

    Args:
        specs: List of (rule_id, params) pairs. Each pair maps to one Rule.
        factory: Callable(rule_id, params) -> Rule. Called once per spec.

    Returns:
        List of Rule instances in the same order as specs.

    Example::

        CORTEX_RULES = ParameterizedRuleFamily(
            specs=[
                ("COST_016", {"feature": "AI_FUNCTIONS", "view": "CORTEX_AI_FUNCTIONS_USAGE_HISTORY"}),
                ("COST_021", {"feature": "CODE_CLI",     "view": "CORTEX_CODE_CLI_USAGE_HISTORY"}),
            ],
            factory=_make_cortex_rule,
        )
    """
    return [factory(rule_id, params) for rule_id, params in specs]
