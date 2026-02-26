import logging
from typing import Any

from snowfort_audit.domain.protocols import AISynthesizerProtocol
from snowfort_audit.domain.rule_definitions import Violation
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError

logger = logging.getLogger(__name__)


class CortexSynthesizer(AISynthesizerProtocol):
    """Uses Snowflake Cortex to synthesize audit findings."""

    def __init__(self, cursor: Any, model: str = "mistral-large"):
        self.cursor = cursor
        self.model = model

    def summarize(self, violations: list[Violation]) -> str:
        if not violations:
            return "No content to summarize."

        # Optimize context window: Only send top 50 violations text
        serialized = "\n".join([f"- [{v.rule_id}] {v.message}" for v in violations[:50]])

        prompt = (
            "Act as a Principal Snowflake Architect. Analyze the following audit findings "
            "and provide a concise Executive Summary (3 bullets) focusing on Cost & Risk. "
            "Highlight the single biggest opportunity.\n\n"
            f"FINDINGS:\n{serialized}"
        )

        # Escape single quotes for SQL
        sanitized_prompt = prompt.replace("'", "''")

        query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{self.model}', '{sanitized_prompt}')"

        try:
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            if result and result[0][0]:
                return str(result[0][0])
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Cortex summary failed: %s", e)
            return f"Error using Cortex: {e}"

        return "Cortex returned no result."
