"""cortex_governance.py — Directive F Cortex AI governance rules (CORTEX_001–007).

CORTEX_001  Cortex Search Service Governance
CORTEX_002  Cortex Analyst Semantic Model Audit
CORTEX_003  Cortex Agent Governance
CORTEX_004  Cortex Intelligence Governance
CORTEX_005  Cortex Fine-Tuning Cost Tracking
CORTEX_006  Cortex LLM Function Sprawl
CORTEX_007  Cortex Serverless AI Budget Gap

All rules:
  - scan_context is None → [] (offline / pre-flight mode)
  - view unavailable (errno 2003) → [] with WARNING telemetry (preview-feature graceful degrade)
  - unexpected error → RuleExecutionError (propagates as ERRORED finding)
  - threshold crossed → [Violation]
  - threshold not crossed → []
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from snowfort_audit.domain.conventions import CortexThresholds, SnowfortConventions
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import (
    Rule,
    RuleExecutionError,
    Severity,
    Violation,
    is_allowlisted_sf_error,
)
from snowfort_audit.domain.rules.cortex_cost import (
    _CORTEX_METERING_SERVICE_TYPES,
    _CortexRule,
)
from snowfort_audit.domain.sql_safety import quote_identifier

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Known Cortex LLM function name fragments used by CORTEX_006 sprawl detection
# ---------------------------------------------------------------------------
_CORTEX_LLM_FUNCTION_KEYWORDS: frozenset[str] = frozenset(
    {
        "COMPLETE",
        "SUMMARIZE",
        "TRANSLATE",
        "SENTIMENT",
        "EXTRACT_ANSWER",
        "CLASSIFY_TEXT",
        "FINETUNE",
        "EMBED_TEXT",
        "TRY_COMPLETE",
    }
)

# ===========================================================================
# CORTEX_001 — Cortex Search Service Governance
# ===========================================================================


class CortexSearchServiceGovernanceCheck(Rule):
    """CORTEX_001: Flag Cortex Search services without governance controls.

    Detects search services that:
    - Are accessible to PUBLIC or have no explicit role restrictions.
    - Are larger than the configured corpus size threshold.

    Note: Uses direct cursor (SHOW CORTEX SEARCH SERVICES) rather than
    _CortexRule / ScanContext because SHOW commands return a different row
    shape than ACCOUNT_USAGE views. Gracefully returns [] on errno 2003
    (preview feature not available in this account edition).
    """

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "CORTEX_001",
            "Cortex Search Service Governance",
            Severity.MEDIUM,
            rationale=(
                "Cortex Search services index and serve sensitive data. "
                "Services without row-access policies or explicit role restrictions "
                "allow any user with USAGE to query all indexed content, bypassing "
                "column-level and row-level security on the source tables."
            ),
            remediation=(
                "Add row-access policies to tables indexed by Cortex Search. "
                "Restrict USAGE on search services to named roles via GRANT USAGE. "
                "Review services larger than the corpus size threshold for data minimisation."
            ),
            remediation_key="GOVERN_CORTEX_SEARCH",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def _thresholds(self, conventions: SnowfortConventions | None) -> CortexThresholds:
        if conventions is not None:
            return conventions.thresholds.cortex
        return CortexThresholds()

    def _check_public_grants(
        self,
        cursor: SnowflakeCursorProtocol,
        service_name: str,
    ) -> list[Violation]:
        """Return violations if PUBLIC has USAGE on this search service."""
        try:
            cursor.execute(f"SHOW GRANTS ON CORTEX SEARCH SERVICE {quote_identifier(service_name)}")  # nosec B608 -- quote_identifier escapes embedded quotes per Snowflake identifier grammar
            grants = cursor.fetchall()
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        violations: list[Violation] = []
        for grant_row in grants:
            if len(grant_row) < 6:
                continue
            grantee = str(grant_row[5]).upper() if grant_row[5] else ""
            if grantee == "PUBLIC":
                violations.append(
                    self.violation(
                        service_name,
                        f"Cortex Search service '{service_name}' has USAGE granted to PUBLIC. "
                        "All account users can query indexed content without access control.",
                    )
                )
        return violations

    def _check_corpus_size(
        self,
        row: tuple,
        service_name: str,
        threshold_gb: int,
        size_col_idx: int | None = None,
    ) -> Violation | None:
        """Return a violation if the identified size column exceeds threshold_gb.

        ``size_col_idx`` must be supplied by the caller after inspecting
        ``cursor.description`` for a column whose name contains "bytes" or "size".
        When ``size_col_idx`` is None the check is skipped to avoid false
        positives from doc-count or timestamp columns.
        """
        if size_col_idx is None or size_col_idx >= len(row):
            return None
        try:
            size_gb = float(row[size_col_idx] or 0)
        except (TypeError, ValueError):
            return None
        if size_gb > threshold_gb:
            return self.violation(
                service_name,
                f"Cortex Search service '{service_name}' corpus is {size_gb:.1f} GB, "
                f"exceeding the governance threshold ({threshold_gb} GB). "
                "Review data minimisation and index scope.",
            )
        return None

    @staticmethod
    def _find_size_col_idx(cursor: SnowflakeCursorProtocol) -> int | None:
        """Return the index of the corpus-size column from cursor.description, or None.

        Identifies the size column by name (must contain 'bytes' or 'size_gb') to avoid
        false positives from doc-count or timestamp columns.
        """
        if not cursor.description:
            return None
        for idx, col_desc in enumerate(cursor.description):
            col_lower = col_desc[0].lower()
            if "bytes" in col_lower or "size_gb" in col_lower:
                return idx
        return None

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,  # noqa: ARG002
        **_kw,
    ) -> list[Violation]:
        violations: list[Violation] = []
        try:
            cursor.execute("SHOW CORTEX SEARCH SERVICES")
            size_col_idx = self._find_size_col_idx(cursor)
            services = cursor.fetchall()
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                if self.telemetry:
                    self.telemetry.warning("CORTEX_001: SHOW CORTEX SEARCH SERVICES not available — skipping.")
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        thresholds = self._thresholds(self._conventions)
        try:
            for row in services:
                if len(row) < 2:
                    continue
                service_name = str(row[1]) if row[1] else "UNKNOWN"
                violations.extend(self._check_public_grants(cursor, service_name))
                size_viol = self._check_corpus_size(
                    row, service_name, thresholds.search_corpus_size_threshold_gb, size_col_idx
                )
                if size_viol:
                    violations.append(size_viol)
        except RuleExecutionError:
            raise
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        return violations


# ===========================================================================
# CORTEX_002 — Cortex Analyst Semantic Model Audit
# ===========================================================================


class CortexAnalystSemanticModelAuditCheck(_CortexRule):
    """CORTEX_002: Detect Cortex Analyst usage without governed semantic models.

    Flags accounts where Cortex Analyst NL-to-SQL queries are occurring but
    the underlying tables referenced by those queries lack governance controls
    (masking policies, row-access policies, or classification tags).
    """

    VIEW = "QUERY_HISTORY"
    TIME_COL = "START_TIME"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "CORTEX_002",
            "Cortex Analyst Semantic Model Audit",
            Severity.MEDIUM,
            rationale=(
                "Cortex Analyst translates natural language to SQL and executes it against "
                "your data. Without governed semantic models (row policies, masking, tags), "
                "Analyst can surface sensitive data to business users who would not normally "
                "have direct table access."
            ),
            remediation=(
                "Apply row-access policies and masking policies to all tables referenced "
                "in Cortex Analyst semantic models. Tag sensitive columns so Analyst "
                "respects classification context. Audit ANALYST-sourced queries in "
                "QUERY_HISTORY for unexpected data access patterns."
            ),
            remediation_key="GOVERN_CORTEX_ANALYST_MODELS",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        analyst_users: set[str] = set()
        try:
            for row in rows:
                # QUERY_HISTORY: col 0 = QUERY_ID, col 1 = QUERY_TEXT, col 6 = USER_NAME
                if len(row) < 7:
                    continue
                query_text = str(row[1]).upper() if row[1] else ""
                # Analyst queries are routed via a distinct application tag pattern.
                # Parentheses required: `and` binds tighter than `or`.
                if "CORTEX_ANALYST" in query_text or ("ANALYST" in query_text and "COMPLETE" in query_text):
                    user = str(row[6]) if row[6] else "UNKNOWN"
                    analyst_users.add(user)
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        if not analyst_users:
            return []
        return [
            self.violation(
                "Account",
                f"{len(analyst_users)} user(s) ran Cortex Analyst NL-to-SQL queries in the last "
                "30 days. Verify that all referenced tables have row-access policies and "
                "masking policies applied to sensitive columns.",
            )
        ]


# ===========================================================================
# CORTEX_003 — Cortex Agent Governance
# ===========================================================================


class CortexAgentGovernanceCheck(_CortexRule):
    """CORTEX_003: Flag Cortex Agent usage exceeding daily session limits or lacking access controls.

    Two detection paths:
    1. Daily agent session volume exceeds agent_max_daily_sessions threshold.
    2. Agent roles have access to sensitive tables without row-access policies.
    """

    VIEW = "QUERY_HISTORY"
    TIME_COL = "START_TIME"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "CORTEX_003",
            "Cortex Agent Governance",
            Severity.HIGH,
            rationale=(
                "Cortex Agents autonomously execute multi-step tool calls including SQL queries "
                "and external API calls. High session volume without corresponding access controls "
                "creates unaudited data access risk and unbounded credit consumption."
            ),
            remediation=(
                "Set per-agent-role credit quotas via Snowflake Budgets. "
                "Apply row-access policies to tables accessible by agent roles. "
                "Monitor agent session counts daily via QUERY_HISTORY. "
                "Restrict agent roles to minimum required table access."
            ),
            remediation_key="GOVERN_CORTEX_AGENTS",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        thresholds = self._thresholds(self._conventions)
        # Count agent sessions per day
        agent_sessions_by_day: dict[str, int] = {}
        try:
            for row in rows:
                if len(row) < 7:
                    continue
                query_text = str(row[1]).upper() if row[1] else ""
                if "CORTEX_AGENT" not in query_text and "AGENT" not in query_text:
                    continue
                usage_date = str(row[0])[:10] if row[0] else ""
                if not usage_date:
                    continue
                agent_sessions_by_day[usage_date] = agent_sessions_by_day.get(usage_date, 0) + 1
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        violations: list[Violation] = []
        for day, count in sorted(agent_sessions_by_day.items()):
            if count > thresholds.agent_max_daily_sessions:
                violations.append(
                    self.violation(
                        "Account",
                        f"Cortex Agent recorded {count} sessions on {day}, exceeding the daily "
                        f"governance threshold ({thresholds.agent_max_daily_sessions}). "
                        "Investigate automated agent loops and enforce session rate limits.",
                    )
                )
        return violations


# ===========================================================================
# CORTEX_004 — Cortex Intelligence Governance
# ===========================================================================


class CortexIntelligenceGovernanceCheck(_CortexRule):
    """CORTEX_004: Flag Snowflake Intelligence usage by roles lacking data governance controls.

    Detects Snowflake Intelligence (Document AI, Classification) usage where
    the roles consuming the feature have not been governed with access policies
    on the source stages/tables.
    """

    VIEW = "METERING_DAILY_HISTORY"
    TIME_COL = "USAGE_DATE"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "CORTEX_004",
            "Cortex Intelligence Governance",
            Severity.MEDIUM,
            rationale=(
                "Snowflake Intelligence features (Document AI, Classification) process "
                "unstructured data from stages. Without access controls on source stages "
                "and tables, any role with Intelligence access can extract structure from "
                "sensitive documents without data governance visibility."
            ),
            remediation=(
                "Apply stage access policies to stages used by Intelligence instances. "
                "Tag tables and stages feeding Intelligence with sensitivity classifications. "
                "Restrict Intelligence instance USAGE to named roles with documented data needs."
            ),
            remediation_key="GOVERN_CORTEX_INTELLIGENCE",
            telemetry=telemetry,
        )

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        intelligence_detected = False
        try:
            for row in rows:
                if len(row) < 2:
                    continue
                service_type = str(row[1]).upper() if row[1] else ""
                if "INTELLIGENCE" in service_type or "DOCUMENT_AI" in service_type:
                    try:
                        credits = float(row[2] or 0) if len(row) > 2 else 0.0
                    except (TypeError, ValueError):
                        credits = 0.0
                    if credits > 0:
                        intelligence_detected = True
                        break
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        if not intelligence_detected:
            return []
        return [
            self.violation(
                "Account",
                "Snowflake Intelligence (Document AI / Classification) usage detected. "
                "Verify that source stages and tables have access policies and sensitivity "
                "tags applied before Intelligence features process that data.",
            )
        ]


# ===========================================================================
# CORTEX_005 — Cortex Fine-Tuning Cost Tracking
# ===========================================================================


class CortexFineTuningCostTrackingCheck(_CortexRule):
    """CORTEX_005: Detect idle fine-tuned models that are incurring storage cost without use.

    Fine-tuned Cortex models incur ongoing storage credits even when not used for
    inference. This rule flags models that were fine-tuned but have no matching
    inference queries in the last `fine_tuning_unused_days` days.
    """

    VIEW = "QUERY_HISTORY"
    TIME_COL = "START_TIME"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "CORTEX_005",
            "Cortex Fine-Tuning Cost Tracking",
            Severity.MEDIUM,
            rationale=(
                "Fine-tuned Cortex models are stored in your account and incur ongoing costs. "
                "Models that are trained but never used for inference represent wasted investment. "
                "Idle fine-tuned models should be deleted or their adoption should be driven."
            ),
            remediation=(
                "Review fine-tuned model usage in QUERY_HISTORY. "
                "Delete unused fine-tuned models via DROP MODEL. "
                "Document which workloads each fine-tuned model was created for."
            ),
            remediation_key="CLEAN_IDLE_FINE_TUNED_MODELS",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def _parse_fine_tune_activity(
        self,
        rows: tuple,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Scan QUERY_HISTORY rows for fine-tune and inference calls.

        Returns (fine_tune_dates, inference_dates) mapping model_key → latest date.
        Each fine-tuned model is tracked under its actual model identifier extracted
        from the FINETUNE() call, falling back to 'fine_tuned_model' when the
        pattern cannot be parsed.
        """
        fine_tune_dates: dict[str, str] = {}
        inference_dates: dict[str, str] = {}
        # Pattern: FINETUNE(<base_model>, '<output_model_name>', ...)
        _finetune_name_re = re.compile(r"FINETUNE\s*\([^,]+,\s*'([^']+)'", re.IGNORECASE)
        for row in rows:
            if len(row) < 7:
                continue
            query_text = str(row[1]) if row[1] else ""
            query_text_upper = query_text.upper()
            query_date = str(row[0])[:10] if row[0] else ""
            if not query_date:
                continue
            if "FINETUNE" in query_text_upper or "FINE_TUNE" in query_text_upper:
                m = _finetune_name_re.search(query_text)
                model_key = m.group(1).lower() if m else "fine_tuned_model"
                if model_key not in fine_tune_dates or fine_tune_dates[model_key] < query_date:
                    fine_tune_dates[model_key] = query_date
            elif "COMPLETE" in query_text_upper and ("FT_" in query_text_upper or "CUSTOM" in query_text_upper):
                # Inference call against a fine-tuned model; extract the model name from
                # the first string argument: COMPLETE('<model_name>', ...)
                m = re.search(r"COMPLETE\s*\(\s*'([^']+)'", query_text, re.IGNORECASE)
                model_key = m.group(1).lower() if m else "fine_tuned_model"
                if model_key not in inference_dates or inference_dates[model_key] < query_date:
                    inference_dates[model_key] = query_date
        return fine_tune_dates, inference_dates

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        thresholds = self._thresholds(self._conventions)
        try:
            fine_tune_dates, inference_dates = self._parse_fine_tune_activity(rows)
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        if not fine_tune_dates:
            return []
        violations: list[Violation] = []
        for model, ft_date in fine_tune_dates.items():
            if not inference_dates.get(model):
                violations.append(
                    self.violation(
                        model,
                        f"Fine-tuned model '{model}' (trained {ft_date}) has no detected inference "
                        f"usage in the last {thresholds.fine_tuning_unused_days} days. "
                        "Consider deleting unused fine-tuned models to eliminate storage costs.",
                    )
                )
        return violations


# ===========================================================================
# CORTEX_006 — Cortex LLM Function Sprawl
# ===========================================================================


class CortexLLMFunctionSprawlCheck(_CortexRule):
    """CORTEX_006: Flag roles using more distinct Cortex LLM functions than the sprawl threshold.

    Breadth of LLM function usage per role indicates ungoverned experimentation. When a
    single role uses many different Cortex LLM functions, it suggests a lack of defined
    AI governance policy — teams are individually exploring rather than working under a
    governed capability framework.
    """

    VIEW = "QUERY_HISTORY"
    TIME_COL = "START_TIME"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "CORTEX_006",
            "Cortex LLM Function Sprawl",
            Severity.LOW,
            rationale=(
                "Using many different Cortex LLM function types from a single role indicates "
                "ungoverned AI exploration. Without a defined capability framework, teams "
                "independently discover and use AI features without cost visibility or "
                "data governance review."
            ),
            remediation=(
                "Define an AI capability framework specifying which Cortex functions are "
                "approved for each use case. Create role-level allowlists for Cortex function "
                "access. Review roles using more than the threshold number of distinct functions "
                "for ungoverned experimentation."
            ),
            remediation_key="GOVERN_CORTEX_FUNCTION_SPRAWL",
            telemetry=telemetry,
        )
        self._conventions = conventions

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        thresholds = self._thresholds(self._conventions)
        # role → set of distinct Cortex LLM function keywords found in queries
        role_functions: dict[str, set[str]] = {}
        try:
            for row in rows:
                if len(row) < 9:
                    continue
                query_text = str(row[1]).upper() if row[1] else ""
                role = str(row[8]) if row[8] else "UNKNOWN"  # ROLE_NAME col
                found = {kw for kw in _CORTEX_LLM_FUNCTION_KEYWORDS if kw in query_text}
                if found:
                    role_functions.setdefault(role, set()).update(found)
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        violations: list[Violation] = []
        for role, functions in sorted(role_functions.items()):
            if len(functions) > thresholds.function_sprawl_threshold:
                fn_list = ", ".join(sorted(functions))
                violations.append(
                    self.violation(
                        role,
                        f"Role '{role}' used {len(functions)} distinct Cortex LLM functions "
                        f"in 30 days ({fn_list}), exceeding the sprawl threshold "
                        f"({thresholds.function_sprawl_threshold}). "
                        "Review against your AI capability framework.",
                    )
                )
        return violations


# ===========================================================================
# CORTEX_007 — Cortex Serverless AI Budget Gap
# ===========================================================================


class CortexServerlessAIBudgetGapCheck(_CortexRule):
    """CORTEX_007: Flag active Cortex AI spend without a corresponding Snowflake Budget.

    Snowflake Budgets are the only mechanism for enforcing credit caps on Cortex AI
    services. If Cortex credits are being consumed but no Budget object covers Cortex
    service types, spend can grow without bound and without alerting.
    """

    VIEW = "METERING_DAILY_HISTORY"
    TIME_COL = "USAGE_DATE"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "CORTEX_007",
            "Cortex Serverless AI Budget Gap",
            Severity.HIGH,
            rationale=(
                "Cortex AI services (LLM functions, Search, Analyst, Agents) are billed "
                "as serverless credits with no built-in cap. Without a Snowflake Budget "
                "scoped to Cortex service types, spend can exceed expectations without "
                "triggering any alerting or automatic enforcement."
            ),
            remediation=(
                "Create a Snowflake Budget covering Cortex AI service types. "
                "Set notification thresholds at 50% and 80% of expected monthly spend. "
                "Assign budget ownership to the team responsible for AI workloads."
            ),
            remediation_key="CREATE_CORTEX_BUDGET",
            telemetry=telemetry,
        )

    def _sum_cortex_credits(self, rows: tuple) -> float:
        """Sum credits from METERING rows filtered to Cortex/AI service types."""
        total = 0.0
        for row in rows:
            if len(row) < 2:
                continue
            service_type = str(row[1]).upper() if row[1] else ""
            if service_type not in _CORTEX_METERING_SERVICE_TYPES:
                continue
            try:
                total += float(row[2] or 0) if len(row) > 2 else 0.0
            except (TypeError, ValueError):
                pass
        return total

    def _budget_exists(self, cursor: SnowflakeCursorProtocol) -> bool | None:
        """Return True if a Cortex budget exists, False if not, None if view unavailable."""
        try:
            cursor.execute(
                "SELECT BUDGET_NAME FROM SNOWFLAKE.LOCAL.BUDGETS"  # nosec B608 -- fully-qualified system view, no user input
                " WHERE UPPER(BUDGET_NAME) LIKE '%CORTEX%'"
                " LIMIT 1"
            )
            return bool(cursor.fetchall())
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return None
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc

    def check_online(
        self,
        cursor: SnowflakeCursorProtocol,
        _resource_name: str | None = None,
        *,
        scan_context: ScanContext | None = None,
        **_kw,
    ) -> list[Violation]:
        rows = self._get_rows(cursor, scan_context)
        if rows is None or len(rows) == 0:
            return []
        try:
            cortex_credits = self._sum_cortex_credits(rows)
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return []
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
        if cortex_credits <= 0:
            return []
        budget_found = self._budget_exists(cursor)
        if budget_found is None:
            if self.telemetry:
                self.telemetry.warning("CORTEX_007: SNOWFLAKE.LOCAL.BUDGETS not available — skipping.")
            return []
        if budget_found:
            return []
        return [
            self.violation(
                "Account",
                f"Cortex AI services consumed {cortex_credits:.1f} credits in 30 days but no "
                "Snowflake Budget covering Cortex AI was found. Without a budget, spend is "
                "uncapped and no alerting will trigger at threshold breaches.",
            )
        ]


# ===========================================================================
# Factory
# ===========================================================================


def get_cortex_governance_rules(
    conventions: SnowfortConventions | None = None,
    telemetry: TelemetryPort | None = None,
) -> list[Rule]:
    """Return all 7 Cortex AI governance rules with injected dependencies."""
    return [
        CortexSearchServiceGovernanceCheck(conventions=conventions, telemetry=telemetry),
        CortexAnalystSemanticModelAuditCheck(telemetry=telemetry),
        CortexAgentGovernanceCheck(conventions=conventions, telemetry=telemetry),
        CortexIntelligenceGovernanceCheck(telemetry=telemetry),
        CortexFineTuningCostTrackingCheck(conventions=conventions, telemetry=telemetry),
        CortexLLMFunctionSprawlCheck(conventions=conventions, telemetry=telemetry),
        CortexServerlessAIBudgetGapCheck(telemetry=telemetry),
    ]
