from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol

import ast
import re

from snowfort_audit.domain.protocols import SQLValidatorProtocol, TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

# Removed Infrastructure import


class HardcodedEnvCheck(Rule):
    """STAT_001: Flag SQL containing hardcoded _DEV, _PROD suffixes."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_001",
            "Hardcoded Environment Check",
            Severity.LOW,
            rationale="Hardcoding environment suffixes like '_DEV' violates the principle of 'Dynamic Promotion', making code brittle and increasing the risk of running against the wrong environment.",
            remediation=(
                "Use Jinja templating (e.g., {{ env }}) or configuration variables "
                "to inject environment context dynamically."
            ),
            remediation_key="USE_DYNAMIC_ENV",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        if re.search(r"_[D|d][E|e][V|v]\b", file_content) or re.search(r"_[P|p][R|r][O|o][D|d]\b", file_content):
            return [
                Violation(
                    self.id,
                    file_path,
                    "Hardcoded environment suffix detected",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class NakedDropCheck(Rule):
    """STAT_002: Flag DROP TABLE or DROP SCHEMA statements."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_002",
            "Naked Drop Statement",
            Severity.HIGH,
            rationale="Destructive SQL statements in source control bypass declarative state management and audit trails, leading to non-repeatable environments and potential data loss.",
            remediation=(
                "Remove destructive DROP statements from version-controlled scripts. "
                "Perform deletions manually or via a dedicated decommissioning pipeline."
            ),
            remediation_key="USE_DECLARATIVE_DROP",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        if "DROP TABLE" in file_content.upper() or "DROP SCHEMA" in file_content.upper():
            return [
                Violation(
                    self.id,
                    file_path,
                    "Destructive DROP statement detected",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class SecretExposureCheck(Rule):
    """STAT_003: Flag potential secrets in SQL or YAML."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_003",
            "Secret Exposure",
            Severity.CRITICAL,
            rationale="Hardcoding credentials in scripts is the primary cause of cloud breaches; secrets should be injected at runtime from a secure vault to prevent git-leakage.",
            remediation=(
                "Use a secrets manager or reference secrets via variables/parameters. "
                "Rotate any exposed credentials immediately."
            ),
            remediation_key="USE_SECRETS_MANAGER",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        if re.search(r'(?i)(password|pwd|private_key|secret|token)\s*[:=]\s*["\'].+["\']', file_content):
            return [
                Violation(
                    self.id,
                    file_path,
                    "Potential hardcoded secret detected",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            ]
        return []


class SelectStarCheck(Rule):
    """SQL_001: Flag 'SELECT *' using SQLFluff."""

    def __init__(self, validator: SQLValidatorProtocol, telemetry: TelemetryPort | None = None):
        super().__init__(
            "SQL_001",
            "No SELECT *",
            Severity.MEDIUM,
            rationale="Selecting all columns in a columnar database forces excessive I/O and compute, significantly increasing query cost and latency while hindering partition pruning.",
            remediation="Explicitly list the columns you need.",
            remediation_key="REFAC_SELECT_STAR",
            telemetry=telemetry,
        )
        self.validator = validator

    def _extract_sql_from_python(self, file_content: str) -> list[tuple[str, int]]:
        to_validate = []
        try:
            tree = ast.parse(file_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    raw_val = node.value
                    if any(kw in raw_val.upper() for kw in ["SELECT", "CREATE"]):
                        to_validate.append((raw_val, node.lineno))
        except (SyntaxError, ValueError) as e:
            if self.telemetry:
                self.telemetry.debug(f"AST parsing failed: {e}")
        return to_validate

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        to_validate = []
        if file_path.endswith(".py"):
            to_validate = self._extract_sql_from_python(file_content)
        else:
            to_validate.append((file_content, 1))

        results = []
        for sql, base_line in to_validate:
            v_list = self.validator.validate(sql)
            for v in v_list:
                if v.code == "AM04" or v.matches("SELECT *") or v.matches("STAR"):
                    results.append(
                        Violation(
                            self.id,
                            file_path,
                            f"Line {base_line + v.line - 1}: {v.description}",
                            self.severity,
                            remediation_key=self.remediation_key,
                        )
                    )
        return results

    def check_online(self, cursor: SnowflakeCursorProtocol, _resource_name: str | None = None) -> list[Violation]:
        if not _resource_name:
            return []

        try:
            cursor.execute(f"SELECT GET_DDL('VIEW', '{_resource_name}')")
            row = cursor.fetchone()
            if row and row[0]:
                return self.check_static(row[0], _resource_name)
        except (Exception, RuntimeError) as e:
            if self.telemetry:
                self.telemetry.error(f"Failed to fetch DDL for view {_resource_name}: {e}")
        return []


class MergePatternRecommendationCheck(Rule):
    """STAT_004: Flag INSERT INTO ... SELECT that could be idempotent MERGE (WAF: idempotent loading)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_004",
            "MERGE Pattern Recommendation",
            Severity.MEDIUM,
            rationale="WAF recommends idempotent data loading with MERGE instead of simple INSERT to avoid duplicates on re-run.",
            remediation="Refactor to MERGE ... ON key = source.key WHEN MATCHED THEN UPDATE WHEN NOT MATCHED THEN INSERT.",
            remediation_key="USE_MERGE_PATTERN",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        violations = []
        # INSERT INTO tbl SELECT ... (no MERGE) in transformation SQL
        pattern = re.compile(
            r"\bINSERT\s+INTO\s+\w+[\s\S]*?SELECT\s+",
            re.IGNORECASE | re.DOTALL,
        )
        if pattern.search(file_content) and "MERGE" not in file_content.upper():
            for m in pattern.finditer(file_content):
                violations.append(
                    Violation(
                        self.id,
                        file_path,
                        "INSERT INTO ... SELECT detected; consider idempotent MERGE for transformations.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                )
                break
        return violations


class DynamicTableComplexityCheck(Rule):
    """STAT_005: Flag dynamic table definitions with >5 joined tables (WAF: keep JOIN count minimal)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_005",
            "Dynamic Table Complexity",
            Severity.MEDIUM,
            rationale="WAF: Keep the number of joined tables in a single DT definition to a minimum, ideally no more than five.",
            remediation="Split into multiple dynamic tables or simplify the query to ≤5 joins.",
            remediation_key="REDUCE_DT_JOINS",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        violations = []
        # CREATE DYNAMIC TABLE ... AS SELECT ... JOIN ... JOIN ...
        if "CREATE DYNAMIC TABLE" not in file_content.upper():
            return []
        join_count = len(re.findall(r"\bJOIN\s+", file_content, re.IGNORECASE))
        if join_count > 5:
            violations.append(
                Violation(
                    self.id,
                    file_path,
                    f"Dynamic table definition has {join_count} JOINs; WAF recommends ≤5.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            )
        return violations


class AntiPatternSQLDetectionCheck(Rule):
    """STAT_006: Flag ORDER BY without LIMIT, OR in JOIN, UNION where UNION ALL suffices (WAF/SQL_001 extension)."""

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "STAT_006",
            "Anti-Pattern SQL Detection",
            Severity.MEDIUM,
            rationale="ORDER BY without LIMIT can be expensive; OR in JOIN prevents efficient pruning; UNION deduplicates when UNION ALL may suffice.",
            remediation="Add LIMIT where appropriate; rewrite JOIN conditions to avoid OR; use UNION ALL if deduplication is not required.",
            remediation_key="REFAC_SQL_ANTIPATTERNS",
            telemetry=telemetry,
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        violations = []
        sql_upper = file_content.upper()
        # ORDER BY ... without LIMIT (heuristic: ORDER BY present, LIMIT absent in same block)
        if re.search(r"\bORDER\s+BY\s+", file_content, re.IGNORECASE):
            if "LIMIT" not in sql_upper:
                violations.append(
                    Violation(
                        self.id,
                        file_path,
                        "ORDER BY without LIMIT may cause full sort; add LIMIT if only top-N is needed.",
                        self.severity,
                        remediation_key=self.remediation_key,
                    )
                )
        # OR in JOIN predicate
        if re.search(r"\bJOIN\s+[\s\S]*?\bOR\b", file_content, re.IGNORECASE | re.DOTALL):
            violations.append(
                Violation(
                    self.id,
                    file_path,
                    "OR condition in JOIN predicate can prevent efficient pruning; consider rewriting.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            )
        # UNION when UNION ALL might suffice (we flag presence of UNION; human can confirm)
        if re.search(r"\bUNION\s+(?!ALL)\s*(\s*SELECT|\s*$)", file_content, re.IGNORECASE):
            violations.append(
                Violation(
                    self.id,
                    file_path,
                    "UNION used; use UNION ALL if deduplication is not required to reduce cost.",
                    self.severity,
                    remediation_key=self.remediation_key,
                )
            )
        return violations
