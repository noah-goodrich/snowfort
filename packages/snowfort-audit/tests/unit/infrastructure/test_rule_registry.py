"""Tests for rule_registry: get_all_rules, discover_custom_rules, get_rules."""

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Rule
from snowfort_audit.infrastructure.rule_registry import (
    discover_custom_rules,
    get_all_rules,
    get_rules,
)


@pytest.fixture
def evaluator():
    return MagicMock()


def test_get_all_rules_returns_non_empty(evaluator):
    """get_all_rules returns a non-empty list of Rule instances."""
    rules = get_all_rules(evaluator, telemetry=None)
    assert isinstance(rules, list)
    assert len(rules) > 0
    for r in rules:
        assert isinstance(r, Rule)
        assert r.id


def test_discover_custom_rules_nonexistent_returns_empty():
    """discover_custom_rules with non-existent folder returns []."""
    path = "/nonexistent/custom/rules/path/12345"
    result = discover_custom_rules(path, telemetry=None)
    assert result == []


def test_get_rules_without_custom_dir_returns_builtins(evaluator):
    """get_rules with custom_rules_dir=None returns builtins (and any plugins)."""
    rules = get_rules(evaluator, telemetry=None, custom_rules_dir=None)
    assert isinstance(rules, list)
    assert len(rules) > 0
    ids = [r.id for r in rules]
    # At least one well-known builtin
    assert "COST_001" in ids or any("COST" in i for i in ids) or len(ids) >= 10


def test_discover_custom_rules_loads_rule_from_py_file(tmp_path):
    """discover_custom_rules loads a Rule subclass from a .py file in the folder."""
    custom_py = tmp_path / "my_custom_rule.py"
    custom_py.write_text(
        """
from snowfort_audit.domain.rule_definitions import Rule, Severity

class MyCustomRule(Rule):
    def __init__(self):
        super().__init__(rule_id="CUSTOM_001", name="My Custom", severity=Severity.LOW)
""",
        encoding="utf-8",
    )
    telemetry = MagicMock()
    rules = discover_custom_rules(str(tmp_path), telemetry=telemetry)
    assert len(rules) == 1
    assert rules[0].id == "CUSTOM_001"
    telemetry.step.assert_called()
