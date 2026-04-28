from __future__ import annotations

import logging
import os
import re
from typing import Any

from snowfort_audit.domain.protocols import AISynthesizerProtocol
from snowfort_audit.domain.results import CortexSummary
from snowfort_audit.domain.rule_definitions import FindingCategory, Violation
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError

logger = logging.getLogger(__name__)

# Matches the most common FQDN-ish patterns we see in violation messages so we can
# replace them with stable opaque tokens before forwarding to a third-party LLM.
# Order matters: longest forms first so a 4-part name doesn't get partially replaced.
_FQDN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b"),  # DB.SCHEMA.TABLE.COLUMN
    re.compile(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b"),  # DB.SCHEMA.TABLE
    re.compile(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b"),  # DB.SCHEMA
)

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
    "CONTEXT: {category_breakdown}\n\n"
    "FINDINGS:\n"
    "{findings}"
)


def _category_breakdown(violations: list[Violation]) -> str:
    counts = {FindingCategory.ACTIONABLE: 0, FindingCategory.EXPECTED: 0, FindingCategory.INFORMATIONAL: 0}
    for v in violations:
        counts[v.category] = counts.get(v.category, 0) + 1
    actionable = counts[FindingCategory.ACTIONABLE]
    return (
        f"Of {len(violations)} findings: {actionable} require action, "
        f"{counts[FindingCategory.EXPECTED]} are expected behavior, "
        f"{counts[FindingCategory.INFORMATIONAL]} are informational. "
        f"Focus your analysis on the {actionable} actionable findings."
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


def _redact_message(message: str) -> str:
    """Replace fully-qualified Snowflake names in a violation message with opaque tokens.

    Stops customer schema topology and column names (which can be PII like ``PATIENT_SSN``)
    from leaking into a third-party LLM prompt. Tokens are stable per-message so the LLM
    can still reason about "which finding is which".
    """
    counter = {"n": 0}
    seen: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        original = match.group(0)
        if original not in seen:
            counter["n"] += 1
            seen[original] = f"<RESOURCE_{counter['n']}>"
        return seen[original]

    redacted = message
    for pattern in _FQDN_PATTERNS:
        redacted = pattern.sub(_replace, redacted)
    return redacted


def _cortex_disabled_by_env() -> bool:
    return os.environ.get("SNOWFORT_DISABLE_CORTEX", "").strip().lower() in {"1", "true", "yes"}


class CortexSynthesizer(AISynthesizerProtocol):
    """Uses Snowflake Cortex to synthesize audit findings.

    Violation messages are redacted before being embedded in the prompt — fully-qualified
    Snowflake names are replaced with opaque tokens (``<RESOURCE_N>``) so the LLM never
    sees customer schema topology or column names. Set ``SNOWFORT_DISABLE_CORTEX=1`` in
    the environment to hard-disable the synthesizer regardless of CLI flags.
    """

    def __init__(self, cursor: Any, model: str = "mistral-large"):
        self.cursor = cursor
        self.model = model

    def summarize(self, violations: list[Violation]) -> str:
        """Return the tl_dr string (legacy interface for CLI panel display)."""
        return self.summarize_structured(violations).tl_dr or "No significant findings."

    def summarize_structured(self, violations: list[Violation]) -> CortexSummary:
        """Return a structured CortexSummary from audit violations."""
        if _cortex_disabled_by_env():
            return CortexSummary(tl_dr="Cortex disabled by SNOWFORT_DISABLE_CORTEX environment variable.")
        if not violations:
            return CortexSummary(tl_dr="No violations found. Account is in good standing.")

        serialized = "\n".join([f"- [{v.rule_id}] {_redact_message(v.message)}" for v in violations[:50]])
        prompt = _STRUCTURED_PROMPT.format(
            findings=serialized,
            category_breakdown=_category_breakdown(violations),
        )

        try:
            self.cursor.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (self.model, prompt))
            result = self.cursor.fetchall()
            if result and result[0][0]:
                return _parse_structured_response(str(result[0][0]))
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Cortex summary failed: %s", e)
            return CortexSummary(tl_dr=f"Cortex summary unavailable: {e}")

        return CortexSummary(tl_dr="Cortex returned no result.")
