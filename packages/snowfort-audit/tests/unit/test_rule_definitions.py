"""Tests for rule_definitions."""

from snowfort_audit.domain.rule_definitions import (
    EXCLUDED_DATABASES_ALWAYS,
    EXCLUDED_DATABASES_DEFAULT,
    PILLAR_MAP,
    FindingCategory,
    Rule,
    Severity,
    Violation,
    is_excluded_db_or_warehouse_name,
    pillar_from_rule_id,
)


def test_pillar_from_rule_id_security():
    assert pillar_from_rule_id("SEC_001") == "Security"


def test_pillar_from_rule_id_other():
    assert pillar_from_rule_id("XYZ_001") == "Other"


def test_is_excluded_db():
    assert is_excluded_db_or_warehouse_name("SNOWFLAKE") is True
    assert is_excluded_db_or_warehouse_name("MY_DB") is False


def test_is_excluded_db_none_returns_false():
    assert is_excluded_db_or_warehouse_name(None) is False


def test_is_excluded_system_prefix():
    assert is_excluded_db_or_warehouse_name("SYSTEM$SOMETHING") is True


def test_pillar_from_rule_id_stat_and_sql():
    assert pillar_from_rule_id("STAT_001") == "Security"
    assert pillar_from_rule_id("SQL_001") == "Performance"


def test_rule_base_check_returns_empty():
    r = Rule("TST_001", "Test", Severity.HIGH)
    assert r.check({}, "res") == []


def test_rule_base_check_static_returns_empty():
    r = Rule("TST_001", "Test", Severity.HIGH)
    assert r.check_static("", "") == []


def test_rule_base_check_online_returns_empty():
    r = Rule("TST_001", "Test", Severity.HIGH)
    assert r.check_online(None, None) == []


def test_rule_violation_helper():
    r = Rule("SEC_001", "S", Severity.CRITICAL, remediation_key="K")
    v = r.violation("res", "msg")
    assert v.rule_id == "SEC_001" and v.message == "msg"


def test_rule_pillar_property():
    r = Rule("COST_001", "Cost Rule", Severity.HIGH)
    assert r.pillar == "Cost"


def test_rule_violation_with_override_and_instruction():
    r = Rule("REL_001", "Rel", Severity.HIGH, remediation="Default fix", remediation_key="KEY")
    v = r.violation("res", "msg", severity=Severity.CRITICAL, remediation_instruction="Custom fix")
    assert v.severity == Severity.CRITICAL
    assert v.remediation_instruction == "Custom fix"
    assert v.pillar == "Reliability"


def test_excluded_constants():
    assert "SNOWFLAKE" in EXCLUDED_DATABASES_ALWAYS
    assert "SNOWFORT" in EXCLUDED_DATABASES_DEFAULT
    assert PILLAR_MAP["SEC"] == "Security"


# ---------------------------------------------------------------------------
# AC-4: FindingCategory enum + Violation.category field
# ---------------------------------------------------------------------------


def test_finding_category_values():
    """FindingCategory has exactly three members with correct string values."""
    assert FindingCategory.ACTIONABLE.value == "ACTIONABLE"
    assert FindingCategory.EXPECTED.value == "EXPECTED"
    assert FindingCategory.INFORMATIONAL.value == "INFORMATIONAL"
    assert len(FindingCategory) == 3


def test_violation_default_category_is_actionable():
    """Violations without explicit category default to ACTIONABLE — backward compat."""
    v = Violation("SEC_001", "Account", "msg", Severity.CRITICAL)
    assert v.category == FindingCategory.ACTIONABLE


def test_violation_explicit_category():
    """Violation accepts explicit category on construction (frozen dataclass)."""
    v = Violation(
        "COST_012",
        "TABLE",
        "CDC table",
        Severity.MEDIUM,
        category=FindingCategory.EXPECTED,
    )
    assert v.category == FindingCategory.EXPECTED


def test_violation_informational_category():
    v = Violation(
        "SEC_007",
        "USER",
        "SSO-only zombie",
        Severity.LOW,
        category=FindingCategory.INFORMATIONAL,
    )
    assert v.category == FindingCategory.INFORMATIONAL


def test_rule_violation_helper_default_category():
    """Rule.violation() helper creates Violation with default ACTIONABLE category."""
    r = Rule("SEC_001", "Admin", Severity.CRITICAL)
    v = r.violation("Account", "too many admins")
    assert v.category == FindingCategory.ACTIONABLE


def test_rule_violation_helper_explicit_category():
    """Rule.violation() helper passes through explicit category."""
    r = Rule("COST_012", "HighChurn", Severity.MEDIUM)
    v = r.violation("TABLE", "CDC table", category=FindingCategory.EXPECTED)
    assert v.category == FindingCategory.EXPECTED
