from __future__ import annotations

import logging
import re
from typing import Any

from snowfort_audit.domain.protocols import AISynthesizerProtocol
from snowfort_audit.domain.results import CortexSummary
from snowfort_audit.domain.rule_definitions import Violation
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError

logger = logging.getLogger(__name__)

_STRUCTURED_PROMPT = (
    "Act as a Principal Snowflake Architect. Analyze the following audit findings "
    "and respond in this exact format (no extra text):\n\n"
    "TL_DR: <one sentence summary focused on the highest-severity risk>\n"
    "TOP_RISKS:\n"
    "- <risk 1>\n"
    "- <risk 2>\n"
    "- <risk 3>\n"
    "QUICK_WINS:\n"
    "- <quick win 1>\n"
    "- <quick win 2>\n\n"
    "FINDINGS:\n"
    "{findings}"
)


def _parse_structured_response(text: str) -> CortexSummary:
    """Parse the structured Cortex response into a CortexSummary.

    Falls back gracefully: if parsing fails, tl_dr gets the full text.
    """
    tl_dr = ""
    top_risks: list[str] = []
    quick_wins: list[str] = []

    tl_dr_m = re.search(r"TL_DR:\s*(.+)", text)
    if tl_dr_m:
        tl_dr = tl_dr_m.group(1).strip()

    risks_m = re.search(r"TOP_RISKS:\s*((?:\s*-\s*.+\n?)+)", text)
    if risks_m:
        top_risks = [ln.lstrip("- ").strip() for ln in risks_m.group(1).splitlines() if ln.strip().startswith("-")]

    wins_m = re.search(r"QUICK_WINS:\s*((?:\s*-\s*.+\n?)+)", text)
    if wins_m:
        quick_wins = [ln.lstrip("- ").strip() for ln in wins_m.group(1).splitlines() if ln.strip().startswith("-")]

    if not tl_dr:
        tl_dr = text.strip()

    return CortexSummary(tl_dr=tl_dr, top_risks=top_risks, quick_wins=quick_wins)


class CortexSynthesizer(AISynthesizerProtocol):
    """Uses Snowflake Cortex to synthesize audit findings."""

    def __init__(self, cursor: Any, model: str = "mistral-large"):
        self.cursor = cursor
        self.model = model

    def summarize(self, violations: list[Violation]) -> str:
        """Return the tl_dr string (legacy interface for CLI panel display)."""
        return self.summarize_structured(violations).tl_dr or "No significant findings."

    def summarize_structured(self, violations: list[Violation]) -> CortexSummary:
        """Return a structured CortexSummary from audit violations."""
        if not violations:
            return CortexSummary(tl_dr="No violations found. Account is in good standing.")

        serialized = "\n".join([f"- [{v.rule_id}] {v.message}" for v in violations[:50]])
        prompt = _STRUCTURED_PROMPT.format(findings=serialized)
        sanitized_prompt = prompt.replace("'", "''")
        query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{self.model}', '{sanitized_prompt}')"

        try:
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            if result and result[0][0]:
                return _parse_structured_response(str(result[0][0]))
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Cortex summary failed: %s", e)
            return CortexSummary(tl_dr=f"Cortex summary unavailable: {e}")

        return CortexSummary(tl_dr="Cortex returned no result.")
