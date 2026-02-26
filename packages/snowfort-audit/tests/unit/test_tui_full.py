"""Expanded TUI tests: compose, mount logic, action_back, action_quit, _show_overview, _show_pillar."""

import asyncio
from unittest.mock import MagicMock, patch

from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation
from snowfort_audit.interface.tui import (
    _SEV_WEIGHT,
    AuditTUI,
    PillarListItem,
    _bar,
    _sev_color,
    run_interactive,
)


def _make_app(violations=None, rules=None):
    violations = violations or []
    rules = rules or []
    result = AuditResult.from_violations(violations)
    return AuditTUI(result, rules, violations)


def test_bar_edge_cases():
    assert "green" in _bar(100, 10)
    assert "red" in _bar(0, 10)
    assert "yellow" in _bar(70, 10)
    assert "yellow" in _bar(89, 10)
    assert "green" in _bar(90, 10)
    assert "red" in _bar(69, 10)


def test_sev_weight_ordering():
    assert _SEV_WEIGHT[Severity.CRITICAL] < _SEV_WEIGHT[Severity.HIGH]
    assert _SEV_WEIGHT[Severity.HIGH] < _SEV_WEIGHT[Severity.MEDIUM]
    assert _SEV_WEIGHT[Severity.MEDIUM] < _SEV_WEIGHT[Severity.LOW]


def test_sev_color_all():
    assert _sev_color(Severity.CRITICAL) == "red"
    assert _sev_color(Severity.HIGH) == "red"
    assert _sev_color(Severity.MEDIUM) == "yellow"
    assert _sev_color(Severity.LOW) == "yellow"


def test_pillar_list_item_compose():
    item = PillarListItem("Security", 95.0, "A", 0, 10)
    widgets = list(item.compose())
    assert len(widgets) == 1


def test_pillar_list_item_compose_with_failures():
    item = PillarListItem("Cost", 60.0, "D", 3, 10)
    widgets = list(item.compose())
    assert len(widgets) == 1


def test_pillar_list_item_compose_single_failure():
    item = PillarListItem("Security", 80.0, "B", 1, 10)
    widgets = list(item.compose())
    assert len(widgets) == 1


def test_audit_tui_init_empty():
    app = _make_app()
    assert app._current_view == "overview"
    assert app._violations_by_rule == {}
    assert app._rules_by_pillar == {}


def test_audit_tui_init_multi_violations():
    v1 = Violation("SEC_001", "A", "msg1", Severity.CRITICAL, pillar="Security")
    v2 = Violation("SEC_001", "B", "msg2", Severity.CRITICAL, pillar="Security")
    v3 = Violation("COST_001", "WH", "msg3", Severity.MEDIUM, pillar="Cost")
    rules = [
        Rule("SEC_001", "Admin", Severity.CRITICAL),
        Rule("COST_001", "Suspend", Severity.MEDIUM),
    ]
    app = _make_app([v1, v2, v3], rules)
    assert len(app._violations_by_rule["SEC_001"]) == 2
    assert len(app._violations_by_rule["COST_001"]) == 1
    assert "Security" in app._rules_by_pillar
    assert "Cost" in app._rules_by_pillar


def test_audit_tui_rules_unknown_pillar():
    r = Rule("UNKNOWN_001", "Custom", Severity.LOW)
    app = _make_app([], [r])
    assert "Other" in app._rules_by_pillar


def test_action_back_overview_stays():
    app = _make_app()
    app._current_view = "overview"
    asyncio.run(app.action_back())
    assert app._current_view == "overview"


def test_action_back_from_detail():
    app = _make_app()
    app._current_view = "detail"
    app._show_overview = MagicMock()
    asyncio.run(app.action_back())
    app._show_overview.assert_called_once()


def test_action_quit():
    app = _make_app()
    app.exit = MagicMock()
    asyncio.run(app.action_quit())
    app.exit.assert_called_once()


def test_compose_yields_widgets():
    app = _make_app()
    widgets = list(app.compose())
    assert len(widgets) == 4


def test_run_interactive_creates_app():
    result = AuditResult.from_violations([])
    with patch.object(AuditTUI, "run") as mock_run:
        run_interactive(result, [], [])
        mock_run.assert_called_once()


def test_run_interactive_with_violations():
    v = Violation("SEC_001", "A", "msg", Severity.CRITICAL, pillar="Security")
    result = AuditResult.from_violations([v])
    rules = [Rule("SEC_001", "Admin", Severity.CRITICAL)]
    with patch.object(AuditTUI, "run") as mock_run:
        run_interactive(result, rules, [v])
        mock_run.assert_called_once()
