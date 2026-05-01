"""Unit tests for Cortex AI governance rules (CORTEX_001–007).

Each rule has:
  1. scan_context=None → []  (offline mode, for _CortexRule subclasses)
  2. view/command unavailable (errno 2003) → []  (preview graceful degrade)
  3. threshold crossed / concern detected → [Violation]
  4. threshold not crossed / clean state → []
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cortex_governance import (
    CortexAgentGovernanceCheck,
    CortexAnalystSemanticModelAuditCheck,
    CortexFineTuningCostTrackingCheck,
    CortexIntelligenceGovernanceCheck,
    CortexLLMFunctionSprawlCheck,
    CortexSearchServiceGovernanceCheck,
    CortexServerlessAIBudgetGapCheck,
    get_cortex_governance_rules,
)
from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Helpers (mirrors cortex_cost test helpers)
# ---------------------------------------------------------------------------


def _make_allowlisted_error():
    err = Exception("Object not found")
    err.errno = 2003
    return err


def _make_ctx_with_cached(view: str, rows: tuple) -> ScanContext:
    ctx = ScanContext()
    ctx._fetch_cache[(view, 30)] = rows
    return ctx


def _make_cursor_raising(exc):
    c = MagicMock()
    c.execute.side_effect = exc
    return c


def _cursor_empty():
    c = MagicMock()
    c.fetchall.return_value = []
    return c


def _full_conventions(
    search_threshold_gb=10,
    agent_max_sessions=1000,
    fine_tuning_days=30,
    sprawl_threshold=5,
):
    """Return a MagicMock convention with all CortexThresholds fields set."""
    conv = MagicMock()
    t = conv.thresholds.cortex
    t.search_corpus_size_threshold_gb = search_threshold_gb
    t.agent_max_daily_sessions = agent_max_sessions
    t.fine_tuning_unused_days = fine_tuning_days
    t.function_sprawl_threshold = sprawl_threshold
    t.power_user_concentration_threshold = 0.80
    t.power_user_min_users = 3
    t.growth_rate_threshold = 0.50
    t.growth_consecutive_months = 2
    t.daily_credit_hard_limit = 100.0
    t.daily_credit_soft_limit = 50.0
    t.model_allowlist_expected = ()
    t.analyst_max_requests_per_user_per_day = 1000
    t.snowflake_intelligence_max_daily_credits = 50.0
    return conv


# ---------------------------------------------------------------------------
# CORTEX_001 CortexSearchServiceGovernanceCheck
# ---------------------------------------------------------------------------


class TestCortexSearchServiceGovernanceCheck:
    def test_show_not_available_returns_empty(self):
        """errno 2003 on SHOW CORTEX SEARCH SERVICES → [] with warning."""
        telemetry = MagicMock()
        rule = CortexSearchServiceGovernanceCheck(telemetry=telemetry)
        cursor = MagicMock()
        cursor.execute.side_effect = _make_allowlisted_error()
        result = rule.check_online(cursor, scan_context=None)
        assert result == []
        telemetry.warning.assert_called_once()

    def test_no_services_no_violation(self):
        rule = CortexSearchServiceGovernanceCheck()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        assert rule.check_online(cursor, scan_context=None) == []

    def test_public_grant_flags_violation(self):
        rule = CortexSearchServiceGovernanceCheck()
        cursor = MagicMock()
        # First call: SHOW CORTEX SEARCH SERVICES → returns one service
        # Second call: SHOW GRANTS ON CORTEX SEARCH SERVICE → PUBLIC grant
        cursor.fetchall.side_effect = [
            [("2026-01-01", "MY_SEARCH_SVC", None)],
            [("2026-01-01", "USAGE", "SEARCH SERVICE", "MY_SEARCH_SVC", "ROLE", "PUBLIC")],
        ]
        result = rule.check_online(cursor, scan_context=None)
        assert len(result) >= 1
        assert any("PUBLIC" in v.message for v in result)

    def test_no_public_grant_no_violation(self):
        rule = CortexSearchServiceGovernanceCheck()
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [("2026-01-01", "MY_SEARCH_SVC", None)],
            [("2026-01-01", "USAGE", "SEARCH SERVICE", "MY_SEARCH_SVC", "ROLE", "ANALYST_ROLE")],
        ]
        assert rule.check_online(cursor, scan_context=None) == []

    def test_corpus_size_over_threshold_flags_violation(self):
        conv = _full_conventions(search_threshold_gb=5)
        rule = CortexSearchServiceGovernanceCheck(conventions=conv)
        cursor = MagicMock()
        # Service with 10 GB corpus; no PUBLIC grant
        cursor.fetchall.side_effect = [
            [("2026-01-01", "BIG_SVC", 10.0)],
            [],  # SHOW GRANTS → empty (no PUBLIC)
        ]
        result = rule.check_online(cursor, scan_context=None)
        assert len(result) >= 1
        assert any("GB" in v.message for v in result)

    def test_unexpected_error_raises(self):
        rule = CortexSearchServiceGovernanceCheck()
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("network error")
        with pytest.raises(RuleExecutionError):
            rule.check_online(cursor, scan_context=None)


# ---------------------------------------------------------------------------
# CORTEX_002 CortexAnalystSemanticModelAuditCheck
# ---------------------------------------------------------------------------


class TestCortexAnalystSemanticModelAuditCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexAnalystSemanticModelAuditCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAnalystSemanticModelAuditCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_no_analyst_queries_no_violation(self):
        rule = CortexAnalystSemanticModelAuditCheck()
        rows = (
            ("Q1", "SELECT * FROM my_table", None, None, None, None, "USER1"),
            ("Q2", "SHOW WAREHOUSES", None, None, None, None, "USER2"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_analyst_query_detected_flags_violation(self):
        rule = CortexAnalystSemanticModelAuditCheck()
        # Query text containing CORTEX_ANALYST keyword
        rows = (
            ("Q1", "/* CORTEX_ANALYST */ SELECT revenue FROM sales", None, None, None, None, "USER1"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "1 user" in result[0].message.lower()

    def test_multiple_analyst_users_single_violation(self):
        """Even with N users, we emit a single account-level violation."""
        rule = CortexAnalystSemanticModelAuditCheck()
        rows = tuple(
            (f"Q{i}", "/* CORTEX_ANALYST */ SELECT x", None, None, None, None, f"USER{i}")
            for i in range(5)
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# CORTEX_003 CortexAgentGovernanceCheck
# ---------------------------------------------------------------------------


class TestCortexAgentGovernanceCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexAgentGovernanceCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAgentGovernanceCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_no_agent_queries_no_violation(self):
        rule = CortexAgentGovernanceCheck()
        rows = (
            ("2026-04-01T00:00:00", "SELECT * FROM t", None, None, None, None, "USER1"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_over_session_limit_flags_violation(self):
        conv = _full_conventions(agent_max_sessions=5)
        rule = CortexAgentGovernanceCheck(conventions=conv)
        # 6 agent queries on same day
        rows = tuple(
            ("2026-04-01T00:00:00", "CORTEX_AGENT call", None, None, None, None, f"U{i}", None, "ROLE")
            for i in range(6)
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "6" in result[0].message

    def test_under_session_limit_no_violation(self):
        conv = _full_conventions(agent_max_sessions=100)
        rule = CortexAgentGovernanceCheck(conventions=conv)
        rows = tuple(
            ("2026-04-01T00:00:00", "CORTEX_AGENT call", None, None, None, None, f"U{i}", None, "ROLE")
            for i in range(3)
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# CORTEX_004 CortexIntelligenceGovernanceCheck
# ---------------------------------------------------------------------------


class TestCortexIntelligenceGovernanceCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexIntelligenceGovernanceCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexIntelligenceGovernanceCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_no_intelligence_usage_no_violation(self):
        rule = CortexIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "WAREHOUSE_METERING", 100.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_intelligence_usage_flags_violation(self):
        rule = CortexIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "CORTEX_INTELLIGENCE", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "Intelligence" in result[0].message

    def test_document_ai_usage_flags_violation(self):
        rule = CortexIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "DOCUMENT_AI", 2.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1

    def test_zero_credits_no_violation(self):
        rule = CortexIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "CORTEX_INTELLIGENCE", 0.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# CORTEX_005 CortexFineTuningCostTrackingCheck
# ---------------------------------------------------------------------------


class TestCortexFineTuningCostTrackingCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexFineTuningCostTrackingCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexFineTuningCostTrackingCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_no_fine_tuning_no_violation(self):
        rule = CortexFineTuningCostTrackingCheck()
        rows = (
            ("Q1", "SELECT * FROM t", None, None, None, None, "USER1"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_idle_fine_tuned_model_flags_violation(self):
        rule = CortexFineTuningCostTrackingCheck()
        rows = (
            # Fine-tune job exists
            ("2026-03-01T00:00:00", "FINETUNE model_x ON dataset", None, None, None, None, "USER1"),
            # No inference call for model_x in the window
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "fine_tuned_model" in result[0].resource_name

    def test_empty_rows_no_violation(self):
        rule = CortexFineTuningCostTrackingCheck()
        ctx = _make_ctx_with_cached(rule.VIEW, ())
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# CORTEX_006 CortexLLMFunctionSprawlCheck
# ---------------------------------------------------------------------------


class TestCortexLLMFunctionSprawlCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexLLMFunctionSprawlCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexLLMFunctionSprawlCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_under_sprawl_threshold_no_violation(self):
        conv = _full_conventions(sprawl_threshold=5)
        rule = CortexLLMFunctionSprawlCheck(conventions=conv)
        # Role uses only 2 functions
        rows = (
            ("Q1", "COMPLETE(prompt)", None, None, None, None, "U", None, "ANALYST_ROLE"),
            ("Q2", "SUMMARIZE(doc)", None, None, None, None, "U", None, "ANALYST_ROLE"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_over_sprawl_threshold_flags_violation(self):
        conv = _full_conventions(sprawl_threshold=3)
        rule = CortexLLMFunctionSprawlCheck(conventions=conv)
        # Role uses 4 distinct LLM functions
        rows = (
            ("Q1", "COMPLETE(x)", None, None, None, None, "U", None, "POWER_ROLE"),
            ("Q2", "SUMMARIZE(x)", None, None, None, None, "U", None, "POWER_ROLE"),
            ("Q3", "TRANSLATE(x, 'en', 'fr')", None, None, None, None, "U", None, "POWER_ROLE"),
            ("Q4", "SENTIMENT(x)", None, None, None, None, "U", None, "POWER_ROLE"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "POWER_ROLE" in result[0].resource_name

    def test_no_llm_queries_no_violation(self):
        rule = CortexLLMFunctionSprawlCheck()
        rows = (
            ("Q1", "SELECT * FROM table1", None, None, None, None, "U", None, "ROLE"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_multiple_roles_independently_checked(self):
        conv = _full_conventions(sprawl_threshold=2)
        rule = CortexLLMFunctionSprawlCheck(conventions=conv)
        # ROLE_A uses 3 functions (over threshold=2), ROLE_B uses 1 (under)
        rows = (
            ("Q1", "COMPLETE(x)", None, None, None, None, "U", None, "ROLE_A"),
            ("Q2", "SUMMARIZE(x)", None, None, None, None, "U", None, "ROLE_A"),
            ("Q3", "TRANSLATE(x, 'a', 'b')", None, None, None, None, "U", None, "ROLE_A"),
            ("Q4", "SENTIMENT(x)", None, None, None, None, "U", None, "ROLE_B"),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert result[0].resource_name == "ROLE_A"


# ---------------------------------------------------------------------------
# CORTEX_007 CortexServerlessAIBudgetGapCheck
# ---------------------------------------------------------------------------


class TestCortexServerlessAIBudgetGapCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexServerlessAIBudgetGapCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_metering_view_unavailable_returns_empty(self):
        rule = CortexServerlessAIBudgetGapCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_no_cortex_spend_no_violation(self):
        rule = CortexServerlessAIBudgetGapCheck()
        rows = (("2026-04-01", "WAREHOUSE_METERING", 100.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_cortex_spend_with_budget_no_violation(self):
        rule = CortexServerlessAIBudgetGapCheck()
        rows = (("2026-04-01", "CORTEX_AI", 50.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        # Budget query returns a matching budget
        cursor.fetchall.return_value = [("CORTEX_MONTHLY_BUDGET",)]
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_cortex_spend_no_budget_flags_violation(self):
        rule = CortexServerlessAIBudgetGapCheck()
        rows = (("2026-04-01", "CORTEX_AI", 50.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        # Budget query returns empty — no budget found
        cursor.fetchall.return_value = []
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "Budget" in result[0].message or "budget" in result[0].message

    def test_budgets_view_unavailable_skips_gracefully(self):
        """If SNOWFLAKE.LOCAL.BUDGETS is not available (errno 2003), return []."""
        telemetry = MagicMock()
        rule = CortexServerlessAIBudgetGapCheck(telemetry=telemetry)
        rows = (("2026-04-01", "CORTEX_AI", 50.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        # Metering data is in cache — first cursor.execute call is the budget query
        cursor.execute.side_effect = _make_allowlisted_error()
        cursor.fetchall.return_value = []
        result = rule.check_online(cursor, scan_context=ctx)
        assert result == []
        telemetry.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestGetCortexGovernanceRules:
    def test_factory_returns_seven_rules(self):
        rules = get_cortex_governance_rules()
        assert len(rules) == 7

    def test_rule_ids_are_correct(self):
        ids = {r.id for r in get_cortex_governance_rules()}
        expected = {f"CORTEX_00{i}" for i in range(1, 8)}
        assert ids == expected

    def test_factory_accepts_conventions_and_telemetry(self):
        conv = MagicMock()
        tel = MagicMock()
        rules = get_cortex_governance_rules(conventions=conv, telemetry=tel)
        assert len(rules) == 7
