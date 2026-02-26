import unittest
from unittest.mock import MagicMock, patch

from snowfort_audit.domain.rule_definitions import Rule, Severity
from snowfort_audit.infrastructure.rule_registry import get_rules


class MockRule(Rule):
    def __init__(self):
        super().__init__(rule_id="MOCK_001", name="Mock Rule", severity=Severity.LOW)

    def check_online(self, _cursor, _resource_name=None) -> list:
        return []


def mock_plugin_function() -> list:
    return [MockRule()]


class TestPluginLoading(unittest.TestCase):
    @patch("snowfort_audit.infrastructure.rule_registry.entry_points")
    def test_plugin_loading_function(self, mock_entry_points):
        # Setup mock entry point
        mock_ep = MagicMock()
        mock_ep.load.return_value = mock_plugin_function
        mock_ep.name = "test_plugin"

        # entry_points returns a list (or iterable)
        mock_entry_points.return_value = [mock_ep]

        mock_evaluator = MagicMock()

        rules = get_rules(mock_evaluator)

        # Check if our mock rule is in the list
        found = any(r.id == "MOCK_001" for r in rules)
        assert found, "Mock rule should be loaded from plugin"

    @patch("snowfort_audit.infrastructure.rule_registry.entry_points")
    def test_plugin_loading_class(self, mock_entry_points):
        # Setup mock entry point returning a Class
        mock_ep = MagicMock()
        mock_ep.load.return_value = MockRule
        mock_ep.name = "test_plugin_class"

        mock_entry_points.value = [mock_ep]  # Using .value for some versions of entry_points? No, it's a mock.
        mock_entry_points.return_value = [mock_ep]

        mock_evaluator = MagicMock()

        rules = get_rules(mock_evaluator)

        # In get_rules, get_all_rules is called which might fail if evaluator is a mock and it tries to use it.
        # But we just care if find Mock Rule.
        found = any(isinstance(r, MockRule) for r in rules)
        assert found, "Mock rule class should be instantiated and loaded"
