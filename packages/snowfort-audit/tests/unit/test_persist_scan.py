"""Tests for PersistScanUseCase — scan result persistence to SNOWFORT.AUDIT."""

from __future__ import annotations

from unittest.mock import MagicMock

from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.use_cases.persist_scan import PersistScanUseCase


def _mock_cursor():
    cur = MagicMock()
    cur.execute.return_value = None
    return cur


def _sample_result(n_violations: int = 3) -> tuple:
    """Build a small AuditResult with violations for testing."""
    violations = [
        Violation(
            rule_id=f"SEC_{i:03d}",
            resource_name=f"RESOURCE_{i}",
            message=f"Test violation {i}",
            severity=Severity.HIGH,
            remediation_key=f"FIX_{i}" if i % 2 == 0 else None,
        )
        for i in range(1, n_violations + 1)
    ]
    result = AuditResult.from_violations(
        violations,
        metadata={"account_id": "TEST_ACCT", "billing_model": "on_demand"},
    )

    # Build matching mock rules
    rules = []
    for i in range(1, n_violations + 1):
        rule = MagicMock()
        rule.id = f"SEC_{i:03d}"
        rule.rationale = f"Rationale for rule {i}"
        rules.append(rule)
    return result, rules


class TestPersistScanUseCase:
    def test_execute_returns_uuid(self):
        cur = _mock_cursor()
        result, rules = _sample_result()
        scan_id = PersistScanUseCase().execute(cur, result, rules)
        assert len(scan_id) == 36  # UUID format
        assert scan_id.count("-") == 4

    def test_ensures_schema_before_insert(self):
        cur = _mock_cursor()
        result, rules = _sample_result()
        PersistScanUseCase().execute(cur, result, rules)
        # First calls should be DDL (CREATE DATABASE, CREATE SCHEMA, CREATE TABLE x2)
        ddl_calls = [c for c in cur.execute.call_args_list if "CREATE" in str(c)]
        assert len(ddl_calls) == 4  # DB + schema + 2 tables

    def test_inserts_metadata_row(self):
        cur = _mock_cursor()
        result, rules = _sample_result()
        PersistScanUseCase().execute(cur, result, rules)
        # Find the INSERT INTO SCAN_METADATA call
        metadata_calls = [
            c for c in cur.execute.call_args_list
            if "SCAN_METADATA" in str(c) and "INSERT" in str(c)
        ]
        assert len(metadata_calls) == 1

    def test_inserts_violations(self):
        cur = _mock_cursor()
        result, rules = _sample_result(n_violations=5)
        PersistScanUseCase().execute(cur, result, rules)
        # Count INSERT INTO SCAN_VIOLATIONS calls
        violation_inserts = [
            c for c in cur.execute.call_args_list
            if "SCAN_VIOLATIONS" in str(c) and "INSERT" in str(c)
        ]
        assert len(violation_inserts) == 5

    def test_no_violations_skips_insert(self):
        cur = _mock_cursor()
        result = AuditResult.from_violations([])
        PersistScanUseCase().execute(cur, result, [])
        # No INSERT INTO SCAN_VIOLATIONS calls
        violation_inserts = [
            c for c in cur.execute.call_args_list
            if "SCAN_VIOLATIONS" in str(c) and "INSERT" in str(c)
        ]
        assert len(violation_inserts) == 0

    def test_violation_enrichment_fields(self):
        cur = _mock_cursor()
        result, rules = _sample_result(n_violations=1)
        PersistScanUseCase().execute(cur, result, rules)
        # Find the violation INSERT call
        violation_inserts = [
            c for c in cur.execute.call_args_list
            if "SCAN_VIOLATIONS" in str(c) and "INSERT" in str(c)
        ]
        assert len(violation_inserts) == 1
        row = violation_inserts[0][0][1]  # positional args: (sql, params)
        # row is a tuple: (scan_id, rule_id, resource, msg, sev, pillar, category, remediation_key, rationale, quick_win)
        assert row[1] == "SEC_001"  # rule_id
        assert row[2] == "RESOURCE_1"  # resource_name
        assert row[4] == "HIGH"  # severity
        assert row[8] == "Rationale for rule 1"  # rationale
        assert row[9] is False  # quick_win (odd index, no remediation_key)

