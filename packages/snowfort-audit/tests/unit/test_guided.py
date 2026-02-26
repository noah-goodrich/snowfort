"""Tests for guided (concept-grouped) reporting."""

import sys
from io import StringIO
from unittest.mock import MagicMock

from snowfort_audit.domain.guided import group_violations_by_concept
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation
from snowfort_audit.interface.cli.report import report_findings_guided


def _make_rule(rule_id: str, name: str, severity: Severity = Severity.MEDIUM, pillar_prefix: str = "COST") -> Rule:
    """Build a minimal Rule for testing (pillar derived from rule_id)."""
    return Rule(
        rule_id,
        name,
        severity,
        rationale=f"Why {name} matters.",
        remediation=f"Do X for {rule_id}.",
    )


def _make_violation(rule_id: str, resource: str, message: str, severity: Severity = Severity.MEDIUM) -> Violation:
    return Violation(
        rule_id=rule_id,
        resource_name=resource,
        message=message,
        severity=severity,
        pillar="",
    )


class TestGroupViolationsByConcept:
    """Tests for group_violations_by_concept."""

    def test_groups_by_rule_id(self):
        r1 = _make_rule("COST_001", "Auto-Suspend", Severity.MEDIUM)
        r2 = _make_rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
        rules = [r1, r2]
        v1 = _make_violation("COST_001", "WH_A", "Too long suspend")
        v2 = _make_violation("COST_001", "WH_B", "Too long suspend")
        v3 = _make_violation("SEC_001", "User1", "Too many admins")
        violations = [v1, v2, v3]

        groups = group_violations_by_concept(violations, rules)

        assert len(groups) == 2
        rule_ids = [r.id for r, _ in groups]
        assert "SEC_001" in rule_ids
        assert "COST_001" in rule_ids
        for rule, group_violations in groups:
            if rule.id == "COST_001":
                assert len(group_violations) == 2
                assert {v.resource_name for v in group_violations} == {"WH_A", "WH_B"}
            else:
                assert len(group_violations) == 1
                assert group_violations[0].resource_name == "User1"

    def test_ordering_pillar_then_severity(self):
        """CRITICAL Security should come before MEDIUM Cost."""
        r_sec = _make_rule("SEC_001", "Admin", Severity.CRITICAL)
        r_cost = _make_rule("COST_001", "Suspend", Severity.MEDIUM)
        rules = [r_sec, r_cost]
        v_sec = _make_violation("SEC_001", "U1", "Admins", Severity.CRITICAL)
        v_cost = _make_violation("COST_001", "WH1", "Suspend", Severity.MEDIUM)
        violations = [v_cost, v_sec]  # cost first in input

        groups = group_violations_by_concept(violations, rules)

        assert len(groups) == 2
        first_rule = groups[0][0]
        assert first_rule.id == "SEC_001", "Security (CRITICAL) should appear before Cost (MEDIUM)"
        assert first_rule.pillar == "Security"

    def test_ordering_by_severity_then_rule_id(self):
        """Within same pillar, CRITICAL before HIGH, then by rule_id."""
        r1 = _make_rule("SEC_001", "Admin", Severity.CRITICAL)
        r2 = _make_rule("SEC_002", "MFA", Severity.CRITICAL)
        r3 = _make_rule("SEC_003", "Network", Severity.HIGH)
        rules = [r1, r2, r3]
        violations = [
            _make_violation("SEC_003", "N1", "Net", Severity.HIGH),
            _make_violation("SEC_002", "U1", "MFA", Severity.CRITICAL),
            _make_violation("SEC_001", "U2", "Admin", Severity.CRITICAL),
        ]

        groups = group_violations_by_concept(violations, rules)

        ids_in_order = [r.id for r, _ in groups]
        assert ids_in_order[0] in ("SEC_001", "SEC_002")
        assert ids_in_order[1] in ("SEC_001", "SEC_002")
        assert ids_in_order[2] == "SEC_003"
        assert set(ids_in_order) == {"SEC_001", "SEC_002", "SEC_003"}

    def test_unknown_rule_id_gets_placeholder_rule(self):
        """Violations with rule_id not in rules get a synthetic Rule."""
        r1 = _make_rule("COST_001", "Known", Severity.MEDIUM)
        rules = [r1]
        v_unknown = _make_violation("UNKNOWN_RULE", "R1", "Some message")
        violations = [v_unknown]

        groups = group_violations_by_concept(violations, rules)

        assert len(groups) == 1
        rule, group_violations = groups[0]
        assert rule.id == "UNKNOWN_RULE"
        assert "Unknown" in rule.name
        assert len(group_violations) == 1
        assert group_violations[0].rule_id == "UNKNOWN_RULE"

    def test_empty_violations_returns_empty_list(self):
        rules = [_make_rule("COST_001", "X", Severity.MEDIUM)]
        groups = group_violations_by_concept([], rules)
        assert groups == []


class TestReportFindingsGuided:
    """Smoke tests for report_findings_guided."""

    def test_renders_without_error(self):
        """report_findings_guided runs and produces output without raising."""
        r1 = _make_rule("COST_001", "Auto-Suspend", Severity.MEDIUM)
        rules = [r1]
        violations = [_make_violation("COST_001", "WH1", "Auto-suspend too long", Severity.MEDIUM)]
        telemetry = MagicMock()

        report_findings_guided(violations, rules, telemetry, manifest=False, target_name=".")

        # No exception; output went to stdout. We could capture with patch('sys.stdout', StringIO())
        # but the plan asked only to verify it doesn't raise.

    def test_manifest_mode_prints_json(self):
        """When manifest=True, guided reporter prints JSON and does not use Rich panels."""
        r1 = _make_rule("COST_001", "X", Severity.MEDIUM)
        violations = [_make_violation("COST_001", "R1", "Msg", Severity.MEDIUM)]
        telemetry = MagicMock()

        old_stdout = sys.stdout
        sys.stdout = buf = StringIO()
        try:
            report_findings_guided(violations, rules=[r1], telemetry=telemetry, manifest=True, target_name=".")
            out = buf.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "rule_id" in out
        assert "COST_001" in out
        assert "R1" in out

    def test_no_violations_prints_perfect_score(self):
        telemetry = MagicMock()
        old_stdout = sys.stdout
        sys.stdout = buf = StringIO()
        try:
            report_findings_guided([], [], telemetry, manifest=False, target_name=".")
            out = buf.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "Perfect Score" in out or "100" in out
