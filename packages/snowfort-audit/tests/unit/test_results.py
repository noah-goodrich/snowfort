"""Tests for domain/results: AuditResult, AuditScorecard, scoring model."""

from snowfort_audit.domain.results import (
    AuditResult,
    AuditScorecard,
    _pillar_deduction,
    _pillar_score,
    _score_to_grade,
)
from snowfort_audit.domain.rule_definitions import (
    PILLAR_DISPLAY_ORDER,
    FindingCategory,
    Severity,
    Violation,
    pillar_from_rule_id,
)

# ---------------------------------------------------------------------------
# _score_to_grade
# ---------------------------------------------------------------------------


def test_score_to_grade_f():
    assert _score_to_grade(0) == "F"
    assert _score_to_grade(59) == "F"
    assert _score_to_grade(60) == "D"
    assert _score_to_grade(90) == "A"


def test_score_to_grade_b_and_c():
    assert _score_to_grade(80) == "B"
    assert _score_to_grade(89) == "B"
    assert _score_to_grade(70) == "C"
    assert _score_to_grade(79) == "C"


# ---------------------------------------------------------------------------
# _pillar_deduction (raw, unbounded — still used as input to log dampening)
# ---------------------------------------------------------------------------


def test_pillar_deduction_weights():
    """Raw deduction weights: CRITICAL=10, HIGH=5, MEDIUM=2, LOW=1."""
    assert _pillar_deduction(1, 0, 0, 0) == 10
    assert _pillar_deduction(0, 1, 0, 0) == 5
    assert _pillar_deduction(0, 0, 1, 0) == 2
    assert _pillar_deduction(0, 0, 0, 1) == 1
    assert _pillar_deduction(1, 1, 1, 1) == 18


# ---------------------------------------------------------------------------
# _pillar_score (log-dampened)
# ---------------------------------------------------------------------------


def test_pillar_score_zero_violations():
    """No violations -> perfect score."""
    assert _pillar_score(0, 0, 0, 0) == 100.0


def test_pillar_score_single_low():
    """1 LOW violation -> high score (A range)."""
    s = _pillar_score(0, 0, 0, 1)
    assert 85 <= s <= 100, f"1 LOW should be A/B range, got {s}"


def test_pillar_score_single_critical():
    """1 CRITICAL -> significant drop but not floor."""
    s = _pillar_score(1, 0, 0, 0)
    assert 50 <= s <= 85, f"1 CRITICAL should drop substantially, got {s}"


def test_pillar_score_volume_dampening():
    """2602 MEDIUM violations floor the pillar (but log prevents instant zeroing
    of small counts)."""
    s_small = _pillar_score(0, 0, 3, 0)
    s_large = _pillar_score(0, 0, 2602, 0)
    assert s_small > s_large, "More violations should produce lower score"
    assert s_large < 20, f"2602 MEDIUM should floor near 0, got {s_large}"
    assert s_small > 30, f"3 MEDIUM should still be reasonable, got {s_small}"


def test_pillar_score_monotonic():
    """Score decreases monotonically with increasing violations."""
    scores = [_pillar_score(0, 0, n, 0) for n in range(0, 50)]
    for i in range(1, len(scores)):
        assert scores[i] <= scores[i - 1], f"Score should decrease: {scores[i - 1]} -> {scores[i]}"


def test_pillar_score_never_negative():
    """Score is always in [0, 100]."""
    s = _pillar_score(100, 100, 10000, 10000)
    assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# AuditScorecard.from_violations — single-pass + log-dampened
# ---------------------------------------------------------------------------


def test_audit_result_from_violations_empty():
    """Empty violations -> score 100, grade A."""
    result = AuditResult.from_violations([])
    assert result.scorecard.compliance_score == 100
    assert result.scorecard.grade == "A"
    assert result.scorecard.total_violations == 0


def test_audit_result_from_violations_with_deductions():
    """Violations reduce score; counts are correct."""
    violations = [
        Violation("C1", "R1", "msg", Severity.CRITICAL, pillar="Cost"),
        Violation("C2", "R2", "msg", Severity.CRITICAL, pillar="Cost"),
        Violation("H1", "R3", "msg", Severity.HIGH, pillar="Cost"),
    ]
    result = AuditResult.from_violations(violations)
    assert result.scorecard.total_violations == 3
    assert result.scorecard.critical_count == 2
    assert result.scorecard.high_count == 1
    assert result.scorecard.compliance_score < 100


def test_audit_scorecard_single_bad_pillar():
    """One pillar with many CRITICAL -> that pillar scores F, but overall stays
    high because other 5 canonical pillars score 100."""
    many_critical = [Violation("X", "R", "m", Severity.CRITICAL, pillar="P")] * 6
    sc = AuditScorecard.from_violations(many_critical)
    assert sc.pillar_scores.get("P", 100) < 70
    # Overall is mean of P + 6 canonical pillars (all 100) — stays high
    assert sc.compliance_score >= 75
    assert sc.grade in ("A", "B", "C")


def test_audit_scorecard_incloudcounsel_distribution():
    """INCLOUDCOUNSEL-like distribution: ~454 real violations across multiple
    pillars should produce an overall score in the 55-70 range (D/C boundary).
    This is the primary calibration test for the scoring model.
    """
    violations = (
        # Security: 5 CRITICAL, 15 HIGH, 20 MEDIUM
        [Violation("SEC_001", "R", "m", Severity.CRITICAL, pillar="Security")] * 5
        + [Violation("SEC_002", "R", "m", Severity.HIGH, pillar="Security")] * 15
        + [Violation("SEC_003", "R", "m", Severity.MEDIUM, pillar="Security")] * 20
        # Cost: 3 CRITICAL, 10 HIGH, 200 MEDIUM, 50 LOW
        + [Violation("COST_001", "R", "m", Severity.CRITICAL, pillar="Cost")] * 3
        + [Violation("COST_002", "R", "m", Severity.HIGH, pillar="Cost")] * 10
        + [Violation("COST_003", "R", "m", Severity.MEDIUM, pillar="Cost")] * 200
        + [Violation("COST_004", "R", "m", Severity.LOW, pillar="Cost")] * 50
        # Reliability: 2 CRITICAL, 5 HIGH
        + [Violation("REL_001", "R", "m", Severity.CRITICAL, pillar="Reliability")] * 2
        + [Violation("REL_002", "R", "m", Severity.HIGH, pillar="Reliability")] * 5
        # Performance: 8 HIGH, 30 MEDIUM
        + [Violation("PERF_001", "R", "m", Severity.HIGH, pillar="Performance")] * 8
        + [Violation("PERF_002", "R", "m", Severity.MEDIUM, pillar="Performance")] * 30
        # Operations: 53 MEDIUM (tagging)
        + [Violation("OPS_001", "R", "m", Severity.MEDIUM, pillar="Operations")] * 53
        # Governance: 1 CRITICAL, 4 LOW
        + [Violation("GOV_001", "R", "m", Severity.CRITICAL, pillar="Governance")] * 1
        + [Violation("GOV_002", "R", "m", Severity.LOW, pillar="Governance")] * 4
    )
    sc = AuditScorecard.from_violations(violations)
    assert 50 <= sc.compliance_score <= 70, (
        f"INCLOUDCOUNSEL-like distribution should score 50-70, got {sc.compliance_score}"
    )
    assert sc.grade in ("F", "D", "C")


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


# ---------------------------------------------------------------------------
# AC-4: Adjusted scoring — ACTIONABLE-only score + category counts
# ---------------------------------------------------------------------------


def test_adjusted_score_all_expected():
    """100 EXPECTED + 5 ACTIONABLE → adjusted_score reflects only the 5."""
    expected = [
        Violation("COST_012", "T", "CDC", Severity.MEDIUM, pillar="Cost", category=FindingCategory.EXPECTED)
    ] * 100
    actionable = [
        Violation("SEC_001", "A", "admin", Severity.CRITICAL, pillar="Security", category=FindingCategory.ACTIONABLE)
    ] * 5
    sc = AuditScorecard.from_violations(expected + actionable)
    # compliance_score reflects all 105 violations
    assert sc.total_violations == 105
    # adjusted_score only reflects the 5 ACTIONABLE ones
    assert sc.adjusted_score > sc.compliance_score, (
        f"adjusted ({sc.adjusted_score}) should be higher than raw ({sc.compliance_score}) "
        "because 100 EXPECTED violations are excluded"
    )


def test_category_counts():
    """from_violations correctly counts actionable, expected, informational."""
    violations = [
        Violation("SEC_001", "A", "m", Severity.CRITICAL, category=FindingCategory.ACTIONABLE),
        Violation("SEC_002", "A", "m", Severity.HIGH, category=FindingCategory.ACTIONABLE),
        Violation("COST_012", "T", "m", Severity.MEDIUM, category=FindingCategory.EXPECTED),
        Violation("COST_012", "T", "m", Severity.MEDIUM, category=FindingCategory.EXPECTED),
        Violation("COST_012", "T", "m", Severity.MEDIUM, category=FindingCategory.EXPECTED),
        Violation("SEC_007", "U", "m", Severity.LOW, category=FindingCategory.INFORMATIONAL),
    ]
    sc = AuditScorecard.from_violations(violations)
    assert sc.actionable_count == 2
    assert sc.expected_count == 3
    assert sc.informational_count == 1
    assert sc.total_violations == 6


def test_default_category_identical_scores():
    """Violations without explicit category (default ACTIONABLE) produce
    identical raw and adjusted scores."""
    violations = [
        Violation("SEC_001", "A", "m", Severity.CRITICAL, pillar="Security"),
        Violation("COST_001", "W", "m", Severity.HIGH, pillar="Cost"),
    ]
    sc = AuditScorecard.from_violations(violations)
    assert sc.compliance_score == sc.adjusted_score
    assert sc.actionable_count == 2
    assert sc.expected_count == 0
    assert sc.informational_count == 0


def test_adjusted_grade():
    """adjusted_grade is derived from adjusted_score, not compliance_score."""
    # Many EXPECTED violations → low compliance_score, high adjusted_score
    expected = [
        Violation("SEC_003", "A", "pwd", Severity.HIGH, pillar="Security", category=FindingCategory.EXPECTED)
    ] * 50
    sc = AuditScorecard.from_violations(expected)
    # No ACTIONABLE violations → adjusted_score should be 100
    assert sc.adjusted_score == 100
    assert sc.adjusted_grade == "A"
    # Raw score should be significantly lower
    assert sc.compliance_score < 100


def test_empty_violations_adjusted():
    """Empty violations → adjusted_score = 100, grade A, all counts zero."""
    sc = AuditScorecard.from_violations([])
    assert sc.adjusted_score == 100
    assert sc.adjusted_grade == "A"
    assert sc.actionable_count == 0
    assert sc.expected_count == 0
    assert sc.informational_count == 0


# ---------------------------------------------------------------------------
# AC-1 (part 2): errored_rules + reliable flag on AuditResult
# ---------------------------------------------------------------------------


def test_audit_result_default_no_errored_rules():
    """Default AuditResult has empty errored_rules and is reliable."""
    result = AuditResult.from_violations([])
    assert result.errored_rules == ()
    assert result.total_rules_executed == 0
    assert result.reliable is True


def test_audit_result_with_errored_rules():
    """errored_rules and total_rules_executed are passed through from_violations."""
    result = AuditResult.from_violations(
        [],
        errored_rules=["SEC_001", "COST_012"],
        total_rules_executed=100,
    )
    assert result.errored_rules == ("SEC_001", "COST_012")
    assert result.total_rules_executed == 100


def test_audit_result_reliable_when_no_errors():
    """Scan with 100 rules and 0 errors is reliable."""
    result = AuditResult.from_violations(
        [],
        total_rules_executed=100,
    )
    assert result.reliable is True


def test_audit_result_reliable_at_five_percent_threshold():
    """Scan with exactly 5% error rate (5 of 100) is still reliable."""
    result = AuditResult.from_violations(
        [],
        errored_rules=["R1", "R2", "R3", "R4", "R5"],
        total_rules_executed=100,
    )
    assert result.reliable is True


def test_audit_result_unreliable_above_five_percent():
    """Scan with >5% error rate (6 of 100) is unreliable."""
    result = AuditResult.from_violations(
        [],
        errored_rules=["R1", "R2", "R3", "R4", "R5", "R6"],
        total_rules_executed=100,
    )
    assert result.reliable is False


def test_audit_result_reliable_with_zero_total_rules():
    """Edge case: 0 total rules executed → reliable (no denominator issue)."""
    result = AuditResult.from_violations(
        [],
        errored_rules=[],
        total_rules_executed=0,
    )
    assert result.reliable is True


def test_audit_result_errored_rules_frozen():
    """errored_rules is stored as a tuple (frozen dataclass)."""
    result = AuditResult.from_violations(
        [],
        errored_rules=["SEC_001"],
        total_rules_executed=10,
    )
    assert isinstance(result.errored_rules, tuple)
