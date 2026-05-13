"""Persist scan results to SNOWFORT.AUDIT tables for dashboard consumption."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from snowfort_audit.domain.rule_definitions import pillar_from_rule_id

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.results import AuditResult
    from snowfort_audit.domain.rule_definitions import Rule


_SCHEMA_DDL = [
    "CREATE DATABASE IF NOT EXISTS SNOWFORT",
    "CREATE SCHEMA IF NOT EXISTS SNOWFORT.AUDIT",
    """CREATE TABLE IF NOT EXISTS SNOWFORT.AUDIT.SCAN_METADATA (
        scan_id             VARCHAR(36)     NOT NULL,
        scanned_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        account_id          VARCHAR,
        compliance_score    FLOAT,
        grade               VARCHAR(1),
        total_violations    INT,
        critical_count      INT,
        high_count          INT,
        medium_count        INT,
        low_count           INT,
        pillar_scores       VARIANT,
        pillar_grades       VARIANT,
        billing_model       VARCHAR,
        reliable            BOOLEAN,
        total_rules         INT,
        errored_rules       INT,
        PRIMARY KEY (scan_id)
    )""",
    """CREATE TABLE IF NOT EXISTS SNOWFORT.AUDIT.SCAN_VIOLATIONS (
        scan_id             VARCHAR(36)     NOT NULL,
        rule_id             VARCHAR         NOT NULL,
        resource_name       VARCHAR,
        message             VARCHAR,
        severity            VARCHAR,
        pillar              VARCHAR,
        category            VARCHAR,
        remediation_key     VARCHAR,
        rationale           VARCHAR,
        quick_win           BOOLEAN,
        FOREIGN KEY (scan_id) REFERENCES SNOWFORT.AUDIT.SCAN_METADATA(scan_id)
    )""",
]


class PersistScanUseCase:
    """Persists an AuditResult to SNOWFORT.AUDIT tables."""

    def execute(
        self,
        cursor: SnowflakeCursorProtocol,
        result: AuditResult,
        rules: list[Rule],
    ) -> str:
        """Persist scan results. Returns the generated scan_id."""
        scan_id = str(uuid.uuid4())
        self._ensure_schema(cursor)
        self._insert_metadata(cursor, scan_id, result)
        self._insert_violations(cursor, scan_id, result, rules)
        return scan_id

    def _ensure_schema(self, cursor: SnowflakeCursorProtocol) -> None:
        """Create SNOWFORT.AUDIT schema and tables if they don't exist."""
        for ddl in _SCHEMA_DDL:
            cursor.execute(ddl)

    def _insert_metadata(
        self,
        cursor: SnowflakeCursorProtocol,
        scan_id: str,
        result: AuditResult,
    ) -> None:
        sc = result.scorecard
        metadata = getattr(result, "metadata", None) or {}
        cursor.execute(
            "INSERT INTO SNOWFORT.AUDIT.SCAN_METADATA "
            "(scan_id, account_id, compliance_score, grade, total_violations, "
            "critical_count, high_count, medium_count, low_count, "
            "pillar_scores, pillar_grades, billing_model, reliable, total_rules, errored_rules) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "PARSE_JSON(%s), PARSE_JSON(%s), %s, %s, %s, %s)",
            (
                scan_id,
                metadata.get("account_id", ""),
                sc.compliance_score,
                sc.grade,
                sc.total_violations,
                sc.critical_count,
                sc.high_count,
                sc.medium_count,
                sc.low_count,
                json.dumps(sc.pillar_scores),
                json.dumps(sc.pillar_grades),
                metadata.get("billing_model", ""),
                result.reliable,
                getattr(result, "total_rules_executed", 0),
                len(getattr(result, "errored_rules", []) or []),
            ),
        )

    def _insert_violations(
        self,
        cursor: SnowflakeCursorProtocol,
        scan_id: str,
        result: AuditResult,
        rules: list[Rule],
    ) -> None:
        if not result.violations:
            return
        rules_by_id = {r.id: r for r in rules}
        rows = []
        for v in result.violations:
            rule = rules_by_id.get(v.rule_id)
            pillar = v.pillar or pillar_from_rule_id(v.rule_id)
            category = v.category.value if v.category else "ACTIONABLE"
            rationale = (rule.rationale or "") if rule else ""
            quick_win = bool(v.remediation_key)
            rows.append((
                scan_id,
                v.rule_id,
                v.resource_name,
                v.message,
                v.severity.value,
                pillar,
                category,
                v.remediation_key or "",
                rationale,
                quick_win,
            ))
        # Insert violations individually (cursor protocol doesn't expose executemany)
        insert_sql = (
            "INSERT INTO SNOWFORT.AUDIT.SCAN_VIOLATIONS "
            "(scan_id, rule_id, resource_name, message, severity, pillar, "
            "category, remediation_key, rationale, quick_win) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        for row in rows:
            cursor.execute(insert_sql, row)
