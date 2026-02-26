"""Tests for domain core: rule_definitions, results, models."""

from snowfort_audit.domain.results import (
    AuditResult,
    AuditScorecard,
    _pillar_deduction,
    _score_to_grade,
)
from snowfort_audit.domain.rule_definitions import (
    PILLAR_COLORS,
    PILLAR_DISPLAY_ORDER,
    Rule,
    Severity,
    Violation,
    is_excluded_db_or_warehouse_name,
    pillar_from_rule_id,
)


def test_score_to_grade_a():
    assert _score_to_grade(95) == "A"
    assert _score_to_grade(90) == "A"


def test_score_to_grade_b():
    assert _score_to_grade(85) == "B"
    assert _score_to_grade(80) == "B"


def test_score_to_grade_c():
    assert _score_to_grade(75) == "C"
    assert _score_to_grade(70) == "C"


def test_score_to_grade_d():
    assert _score_to_grade(65) == "D"
    assert _score_to_grade(60) == "D"


def test_score_to_grade_f():
    assert _score_to_grade(59) == "F"
    assert _score_to_grade(0) == "F"


def test_pillar_deduction():
    assert _pillar_deduction(1, 0, 0, 0) == 10
    assert _pillar_deduction(0, 1, 0, 0) == 5
    assert _pillar_deduction(0, 0, 1, 0) == 2
    assert _pillar_deduction(0, 0, 0, 1) == 1
    assert _pillar_deduction(1, 1, 1, 1) == 18


def test_scorecard_from_violations_empty():
    sc = AuditScorecard.from_violations([])
    assert sc.compliance_score == 100
    assert sc.grade == "A"
    assert sc.total_violations == 0


def test_scorecard_from_violations_mixed():
    vs = [
        Violation("SEC_001", "A", "m1", Severity.CRITICAL, pillar="Security"),
        Violation("COST_001", "B", "m2", Severity.MEDIUM, pillar="Cost"),
        Violation("COST_002", "C", "m3", Severity.LOW, pillar="Cost"),
    ]
    sc = AuditScorecard.from_violations(vs)
    assert sc.total_violations == 3
    assert sc.critical_count == 1
    assert sc.medium_count == 1
    assert sc.low_count == 1
    assert "Security" in sc.pillar_scores
    assert "Cost" in sc.pillar_scores


def test_scorecard_grade_property():
    sc = AuditScorecard(compliance_score=85)
    assert sc.grade == "B"


def test_audit_result_from_violations():
    v = Violation("SEC_001", "A", "msg", Severity.HIGH, pillar="Security")
    r = AuditResult.from_violations([v], metadata={"key": "val"})
    assert r.metadata == {"key": "val"}
    assert r.scorecard.total_violations == 1


def test_audit_result_to_summary_dict():
    v = Violation("SEC_001", "A", "msg", Severity.CRITICAL, pillar="Security")
    r = AuditResult.from_violations([v])
    d = r.to_summary_dict()
    assert d["TOTAL_VIOLATIONS"] == 1
    assert d["CRITICAL_COUNT"] == 1


def test_pillar_from_rule_id_known():
    assert pillar_from_rule_id("SEC_001") == "Security"
    assert pillar_from_rule_id("COST_001") == "Cost"
    assert pillar_from_rule_id("PERF_001") == "Performance"
    assert pillar_from_rule_id("OPS_001") == "Operations"
    assert pillar_from_rule_id("GOV_001") == "Governance"
    assert pillar_from_rule_id("REL_001") == "Reliability"


def test_pillar_from_rule_id_unknown():
    assert pillar_from_rule_id("FAKE_001") == "Other"


def test_is_excluded_db_snowflake():
    assert is_excluded_db_or_warehouse_name("SNOWFLAKE") is True
    assert is_excluded_db_or_warehouse_name("SNOWFORT") is True


def test_is_excluded_db_system():
    assert is_excluded_db_or_warehouse_name("SYSTEM$something") is True


def test_is_excluded_db_user():
    assert is_excluded_db_or_warehouse_name("MY_DB") is False


def test_is_excluded_db_none():
    assert is_excluded_db_or_warehouse_name(None) is False
    assert is_excluded_db_or_warehouse_name("") is False


def test_rule_init():
    r = Rule("SEC_001", "Admin Exposure", Severity.CRITICAL)
    assert r.id == "SEC_001"
    assert r.name == "Admin Exposure"
    assert r.severity == Severity.CRITICAL
    assert r.pillar == "Security"


def test_rule_violation_helper():
    r = Rule("SEC_001", "Admin", Severity.CRITICAL, remediation_key="FIX")
    v = r.violation("Account", "too many admins")
    assert v.rule_id == "SEC_001"
    assert v.resource_name == "Account"
    assert v.severity == Severity.CRITICAL
    assert v.pillar == "Security"
    assert v.remediation_key == "FIX"


def test_rule_violation_custom_severity():
    r = Rule("SEC_001", "Admin", Severity.CRITICAL)
    v = r.violation("A", "msg", severity=Severity.LOW)
    assert v.severity == Severity.LOW


def test_rule_base_check_returns_empty():
    r = Rule("SEC_001", "Admin", Severity.CRITICAL)
    assert r.check({}, "res") == []
    assert r.check_online(None) == []
    assert r.check_static("", "") == []


def test_violation_dataclass():
    v = Violation("R1", "A", "msg", Severity.HIGH, pillar="P", remediation_key="K", remediation_instruction="Fix it")
    assert v.remediation_key == "K"
    assert v.remediation_instruction == "Fix it"


def test_pillar_display_order():
    assert len(PILLAR_DISPLAY_ORDER) == 6


def test_pillar_colors():
    assert PILLAR_COLORS["Other"] == "dim"


def test_severity_values():
    assert Severity.CRITICAL.value == "CRITICAL"
    assert Severity.LOW.value == "LOW"
