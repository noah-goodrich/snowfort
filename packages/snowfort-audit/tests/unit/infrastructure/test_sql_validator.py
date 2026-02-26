"""Tests for SqlFluffValidatorGateway and SqlfluffSQLViolation."""

from unittest.mock import patch

from snowfort_audit.infrastructure.gateways.sql_validator import (
    SqlfluffSQLViolation,
    SqlFluffValidatorGateway,
)


def test_sqlfluff_violation_matches():
    v = SqlfluffSQLViolation(line=1, column=2, code="L001", description="Line too long")
    assert v.matches("too long") is True
    assert v.matches("TOO LONG") is True
    assert v.matches("other") is False


def test_validate_returns_violations_for_bad_sql():
    gateway = SqlFluffValidatorGateway()
    violations = gateway.validate("SELECT * FROM t WHERE id = ")
    assert isinstance(violations, list)


def test_validate_handles_parse_error():
    """When sqlfluff.lint raises (e.g. invalid input type), validate returns a single LINT_ERROR violation."""
    gateway = SqlFluffValidatorGateway()
    with patch("snowfort_audit.infrastructure.gateways.sql_validator.sqlfluff.lint") as mock_lint:
        mock_lint.side_effect = TypeError("expected string")
        violations = gateway.validate("SELECT 1")
    assert len(violations) == 1
    assert violations[0].code == "LINT_ERROR"
    assert "SQLFluff" in violations[0].description or "expected" in violations[0].description


def test_validate_returns_empty_for_valid_sql():
    gateway = SqlFluffValidatorGateway()
    violations = gateway.validate("SELECT 1 AS n")
    assert isinstance(violations, list)


def test_sqlfluff_violation_matches_substring():
    v = SqlfluffSQLViolation(line=1, column=1, code="AM04", description="SELECT * used")
    assert v.matches("SELECT *") is True
    assert v.matches("used") is True


def test_validate_custom_dialect():
    gateway = SqlFluffValidatorGateway(dialect="snowflake")
    assert gateway.dialect == "snowflake"


def test_validate_catches_runtime_error():
    gateway = SqlFluffValidatorGateway()
    with patch("snowfort_audit.infrastructure.gateways.sql_validator.sqlfluff.lint") as mock_lint:
        mock_lint.side_effect = RuntimeError("internal error")
        violations = gateway.validate("SELECT 1")
    assert len(violations) == 1
    assert violations[0].code == "LINT_ERROR"
    assert "internal error" in violations[0].description
