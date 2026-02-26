"""SQL Validator implementation using SQLFluff."""

import logging
from dataclasses import dataclass

import sqlfluff

from snowfort_audit.domain.protocols import SQLValidatorProtocol, SQLViolation

logger = logging.getLogger(__name__)


@dataclass
class SqlfluffSQLViolation(SQLViolation):
    """Implementation of SQLViolation for SQLFluff."""

    line: int
    column: int
    code: str
    description: str

    def matches(self, pattern: str) -> bool:
        """Case-insensitive description match."""
        return pattern.upper() in self.description.upper()


class SqlFluffValidatorGateway(SQLValidatorProtocol):
    """Implementation of SQLValidatorProtocol using SQLFluff API."""

    def __init__(self, dialect: str = "snowflake"):
        self.dialect = dialect

    def validate(self, sql: str) -> list[SQLViolation]:
        """Validate SQL using the SQLFluff Python API."""
        try:
            # We use the lint method which returns a list of dictionaries
            lint_results = sqlfluff.lint(sql, dialect=self.dialect)

            violations: list[SQLViolation] = []
            for result in lint_results:
                violations.append(
                    SqlfluffSQLViolation(
                        line=result.get("start_line_no", 0),
                        column=result.get("start_line_pos", 0),
                        code=result.get("code", "UNKNOWN"),
                        description=result.get("description", "No description provided"),
                    )
                )
            return violations
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("SQLFluff validation failed: %s", e)
            return [
                SqlfluffSQLViolation(
                    line=1, column=1, code="LINT_ERROR", description=f"SQLFluff failed to parse SQL: {e!s}"
                )
            ]
