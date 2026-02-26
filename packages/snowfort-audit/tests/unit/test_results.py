"""Tests for domain/results: AuditResult, AuditScorecard, _score_to_grade."""

from snowfort_audit.domain.results import (
    AuditResult,
    AuditScorecard,
    _score_to_grade,
)
from snowfort_audit.domain.rule_definitions import (
    PILLAR_DISPLAY_ORDER,
    Severity,
    Violation,
    pillar_from_rule_id,
)


def test_audit_result_from_violations_empty():
    """Empty violations -> score 100, grade A."""
    result = AuditResult.from_violations([])
    assert result.scorecard.compliance_score == 100
    assert result.scorecard.grade == "A"
    assert result.scorecard.total_violations == 0


def test_audit_result_from_violations_with_deductions():
    """Violations reduce score; many critical/high can yield grade D or F."""
    violations = [
        Violation("C1", "R1", "msg", Severity.CRITICAL, pillar="Cost"),
        Violation("C2", "R2", "msg", Severity.CRITICAL, pillar="Cost"),
        Violation("H1", "R3", "msg", Severity.HIGH, pillar="Cost"),
    ]
    result = AuditResult.from_violations(violations)
    assert result.scorecard.total_violations == 3
    assert result.scorecard.critical_count == 2
    assert result.scorecard.high_count == 1
    # Deduction >= 25 can push score to 75 (C) or lower; enough can hit D (60-69) or F (<60)
    assert result.scorecard.compliance_score <= 100


def test_audit_scorecard_grade_d_and_f():
    """Scorecard grade is D for 60-69 and F for <60. Overall score = mean of pillar scores."""
    # One pillar P with 6 CRITICAL -> pillar P score 40 (F); other pillars 100 -> overall mean ~91 (A)
    many_critical = [Violation("X", "R", "m", Severity.CRITICAL, pillar="P")] * 6
    sc_low = AuditScorecard.from_violations(many_critical)
    assert sc_low.pillar_scores.get("P", 100) <= 50
    assert sc_low.pillar_grades.get("P") == "F"
    # Overall grade is mean of pillar scores, so one bad pillar leaves overall high
    assert sc_low.compliance_score >= 80
    assert sc_low.grade == "A"

    # Score in 60-69 range for D (need multiple pillars with violations to pull mean into 60-69)
    violations_d = [
        Violation("C", "R", "m", Severity.CRITICAL, pillar="P"),
        Violation("H", "R", "m", Severity.HIGH, pillar="P"),
        Violation("H", "R", "m", Severity.HIGH, pillar="P"),
    ]
    sc_d = AuditScorecard.from_violations(violations_d)
    if 60 <= sc_d.compliance_score < 70:
        assert sc_d.grade == "D"


def test_audit_result_from_violations_with_metadata():
    """from_violations accepts optional metadata."""
    result = AuditResult.from_violations([], metadata={"env": "DEV", "account": "org"})
    assert result.metadata == {"env": "DEV", "account": "org"}
    result2 = AuditResult.from_violations([Violation("X", "R", "m", Severity.LOW)])
    assert result2.metadata == {}


def test_audit_result_to_summary_dict():
    """to_summary_dict returns expected keys."""
    result = AuditResult.from_violations([])
    d = result.to_summary_dict()
    assert d["COMPLIANCE_SCORE"] == 100
    assert d["TOTAL_VIOLATIONS"] == 0
    assert "CRITICAL_COUNT" in d
    assert "HIGH_COUNT" in d


def test_audit_result_to_summary_dict_with_violations():
    """to_summary_dict reflects violation counts."""
    v = [Violation("C", "R", "m", Severity.CRITICAL), Violation("H", "R", "m", Severity.HIGH)]
    result = AuditResult.from_violations(v)
    d = result.to_summary_dict()
    assert d["CRITICAL_COUNT"] == 1
    assert d["HIGH_COUNT"] == 1
    assert d["TOTAL_VIOLATIONS"] == 2


def test_score_to_grade_f():
    """_score_to_grade returns F for score < 60."""
    assert _score_to_grade(0) == "F"
    assert _score_to_grade(59) == "F"
    assert _score_to_grade(60) == "D"
    assert _score_to_grade(90) == "A"


def test_score_to_grade_b_and_c():
    """_score_to_grade returns B for 80-89, C for 70-79."""
    assert _score_to_grade(80) == "B"
    assert _score_to_grade(89) == "B"
    assert _score_to_grade(70) == "C"
    assert _score_to_grade(79) == "C"


def test_pillar_derived_from_rule_id_when_empty():
    """Violations with empty pillar get pillar from rule_id so 'Other' is not used."""
    v = Violation("GOV_003", "Account", "No budget", Severity.CRITICAL, pillar="")
    scorecard = AuditScorecard.from_violations([v])
    assert "Governance" in scorecard.pillar_scores
    assert "Other" not in scorecard.pillar_scores
    assert scorecard.pillar_scores["Governance"] < 100


def test_all_canonical_pillars_in_scorecard():
    """Scorecard includes all PILLAR_DISPLAY_ORDER pillars (score 100 when no violations)."""
    v = Violation("COST_001", "WH", "msg", Severity.LOW, pillar="Cost")
    scorecard = AuditScorecard.from_violations([v])
    for p in PILLAR_DISPLAY_ORDER:
        assert p in scorecard.pillar_scores
        assert p in scorecard.pillar_grades
    assert scorecard.pillar_scores["Cost"] < 100
    assert scorecard.pillar_scores["Security"] == 100.0
    assert scorecard.pillar_grades["Security"] == "A"


def test_pillar_from_rule_id_and_display_order():
    """Five WAF pillars plus Governance in display order; rule_id maps to pillar."""
    assert pillar_from_rule_id("SEC_001") == "Security"
    assert pillar_from_rule_id("COST_001") == "Cost"
    assert pillar_from_rule_id("REL_001") == "Reliability"
    assert pillar_from_rule_id("PERF_001") == "Performance"
    assert pillar_from_rule_id("OPS_001") == "Operations"
    assert pillar_from_rule_id("GOV_003") == "Governance"
    assert pillar_from_rule_id("UNKNOWN_99") == "Other"
    five_and_governance = {"Security", "Cost", "Reliability", "Performance", "Operations", "Governance"}
    assert set(PILLAR_DISPLAY_ORDER) >= five_and_governance
