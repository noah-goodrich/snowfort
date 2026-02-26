"""Tests for TUI helper functions (tui.py).

The AuditTUI Textual app is tested via the helper functions it uses.
Full interactive TUI testing would require textual.testing which is
out of scope for the unit test suite.
"""

from snowfort_audit.domain.rule_definitions import Severity
from snowfort_audit.interface.tui import (
    PillarListItem,
    _bar,
    _sev_color,
)


class TestBar:
    def test_high_score_is_green(self):
        result = _bar(95)
        assert "[green]" in result

    def test_medium_score_is_yellow(self):
        result = _bar(75)
        assert "[yellow]" in result

    def test_low_score_is_red(self):
        result = _bar(50)
        assert "[red]" in result

    def test_zero_score(self):
        result = _bar(0)
        assert "[red]" in result
        assert "━" in result

    def test_perfect_score(self):
        result = _bar(100)
        assert "[green]" in result

    def test_custom_width(self):
        result = _bar(50, width=10)
        assert len(result) > 0

    def test_boundary_90(self):
        result = _bar(90)
        assert "[green]" in result

    def test_boundary_70(self):
        result = _bar(70)
        assert "[yellow]" in result

    def test_boundary_69(self):
        result = _bar(69)
        assert "[red]" in result


class TestSevColor:
    def test_critical_is_red(self):
        assert _sev_color(Severity.CRITICAL) == "red"

    def test_high_is_red(self):
        assert _sev_color(Severity.HIGH) == "red"

    def test_medium_is_yellow(self):
        assert _sev_color(Severity.MEDIUM) == "yellow"

    def test_low_is_yellow(self):
        assert _sev_color(Severity.LOW) == "yellow"


class TestPillarListItem:
    def test_init_stores_attributes(self):
        item = PillarListItem("Security", 85.0, "B", 3, 10)
        assert item.pillar == "Security"
        assert item.score == 85.0
        assert item.grade == "B"
        assert item.failed == 3
        assert item.total == 10

    def test_init_perfect_pillar(self):
        item = PillarListItem("Cost", 100.0, "A", 0, 5)
        assert item.failed == 0
        assert item.grade == "A"
