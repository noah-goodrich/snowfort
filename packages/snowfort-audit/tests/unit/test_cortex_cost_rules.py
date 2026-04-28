"""Unit tests for Cortex cost governance rules (COST_016–COST_033).

Each rule has:
  1. scan_context=None → []  (offline mode)
  2. view unavailable (allowlisted error) → [] with telemetry warning
  3. threshold crossed → [Violation]
  4. threshold not crossed → []
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cortex_cost import (
    CortexAgentBudgetEnforcementCheck,
    CortexAgentSpendCapCheck,
    CortexAgentTagCoverageCheck,
    CortexAIFunctionCreditBudgetCheck,
    CortexAIFunctionModelAllowlistCheck,
    CortexAIFunctionPerUserSpendCheck,
    CortexAIFunctionQueryTagCoverageCheck,
    CortexAISQLAdoptionCheck,
    CortexAnalystEnabledWithoutBudgetCheck,
    CortexAnalystPerUserQuotaCheck,
    CortexCodeCLICreditSpikeCheck,
    CortexCodeCLIPerUserLimitCheck,
    CortexCodeCLIZombieUsageCheck,
    CortexDocumentProcessingSpendCheck,
    CortexSearchConsumptionBreakdownCheck,
    CortexSearchZombieServiceCheck,
    SnowflakeIntelligenceDailySpendCheck,
    SnowflakeIntelligenceGovernanceCheck,
    get_cortex_rules,
)
from snowfort_audit.domain.scan_context import ScanContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_allowlisted_error():
    """Create an error that is_allowlisted_sf_error() accepts (errno=2003)."""
    err = Exception("Object not found")
    err.errno = 2003
    return err


def _make_ctx_with_cached(view: str, rows: tuple) -> ScanContext:
    """Return a ScanContext that returns rows from get_or_fetch without hitting DB."""
    ctx = ScanContext()
    ctx._fetch_cache[(view, 30)] = rows
    return ctx


def _make_cursor_raising(exc):
    """Cursor whose execute() raises exc."""
    c = MagicMock()
    c.execute.side_effect = exc
    return c


def _cursor_empty():
    c = MagicMock()
    c.fetchall.return_value = []
    return c


# ---------------------------------------------------------------------------
# COST_016 CortexAIFunctionCreditBudgetCheck
# ---------------------------------------------------------------------------


class TestCortexAIFunctionCreditBudgetCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexAIFunctionCreditBudgetCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_returns_empty(self):
        telemetry = MagicMock()
        rule = CortexAIFunctionCreditBudgetCheck(telemetry=telemetry)
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        result = rule.check_online(cursor, scan_context=ctx)
        assert result == []
        telemetry.warning.assert_called_once()

    def test_over_threshold_flags_violation(self):
        # hard_limit default is 100; pass a row with day + two non-numeric + a credit val
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 50.0
        conv.thresholds.cortex.daily_credit_soft_limit = 30.0
        rule = CortexAIFunctionCreditBudgetCheck(conventions=conv)
        # Row layout: (USAGE_TIME, user, credits, ...)
        rows = (("2026-04-01T00:00:00", "USER1", 60.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "60" in result[0].message

    def test_under_threshold_no_violations(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 200.0
        conv.thresholds.cortex.daily_credit_soft_limit = 100.0
        rule = CortexAIFunctionCreditBudgetCheck(conventions=conv)
        rows = (("2026-04-01T00:00:00", "USER1", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_unexpected_error_raises_rule_execution_error(self):
        rule = CortexAIFunctionCreditBudgetCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(RuntimeError("DB error"))
        with pytest.raises(RuleExecutionError):
            rule.check_online(cursor, scan_context=ctx)


# ---------------------------------------------------------------------------
# COST_017 CortexAIFunctionModelAllowlistCheck
# ---------------------------------------------------------------------------


class TestCortexAIFunctionModelAllowlistCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexAIFunctionModelAllowlistCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_no_allowlist_configured_skips(self):
        conv = MagicMock()
        conv.thresholds.cortex.model_allowlist_expected = []
        rule = CortexAIFunctionModelAllowlistCheck(conventions=conv)
        rows = (("2026-04-01", "USER1", "llama3-70b", 1.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_non_allowlisted_model_flags(self):
        conv = MagicMock()
        conv.thresholds.cortex.model_allowlist_expected = ["MISTRAL-7B"]
        rule = CortexAIFunctionModelAllowlistCheck(conventions=conv)
        # Put model name at col 1 so the heuristic finds it first
        rows = (("2026-04-01", "LLAMA3-70B", 1.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) >= 1
        assert "LLAMA3-70B" in result[0].message

    def test_allowlisted_model_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.model_allowlist_expected = ["MISTRAL-7B"]
        rule = CortexAIFunctionModelAllowlistCheck(conventions=conv)
        rows = (("2026-04-01", "MISTRAL-7B", 1.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAIFunctionModelAllowlistCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_018 CortexAIFunctionQueryTagCoverageCheck
# ---------------------------------------------------------------------------


class TestCortexAIFunctionQueryTagCoverageCheck:
    def test_none_scan_context_returns_empty(self):
        rule = CortexAIFunctionQueryTagCoverageCheck()
        assert rule.check_online(_cursor_empty(), scan_context=None) == []

    def test_high_untagged_rate_flags(self):
        rule = CortexAIFunctionQueryTagCoverageCheck()
        # Rows: (time, user, credits, tag). Untagged = tag is None/empty.
        # The rule checks row[-3:] for non-empty strings. Use numeric credits so
        # the last 3 cols for untagged rows have no non-empty strings.
        # 8 untagged: last 3 cols = (1.0, None, None) — no strings
        # 2 tagged: last 3 cols = (1.0, None, "team") — "team" is non-empty string
        untagged_rows = tuple(("2026-04-01", "USR", 1.0, None, None) for _ in range(8))
        tagged_rows = (
            ("2026-04-01", "USR", 1.0, None, "team/proj"),
            ("2026-04-01", "USR", 1.0, None, "team/proj"),
        )
        rows = untagged_rows + tagged_rows
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "%" in result[0].message

    def test_low_untagged_rate_no_violation(self):
        rule = CortexAIFunctionQueryTagCoverageCheck()
        # Only 1 untagged out of 10 = 10% < 20%
        untagged_row = (("2026-04-01", "USR", 1.0, None, None),)
        tagged_rows = tuple(("2026-04-01", "USR", 1.0, None, "team/proj") for _ in range(9))
        rows = untagged_row + tagged_rows
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAIFunctionQueryTagCoverageCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_019 CortexAIFunctionPerUserSpendCheck
# ---------------------------------------------------------------------------


class TestCortexAIFunctionPerUserSpendCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAIFunctionPerUserSpendCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_outlier_user_flagged(self):
        rule = CortexAIFunctionPerUserSpendCheck()
        # user A: 10 credits, user B: 1 credit — A is 10x median
        rows = (
            ("2026-04-01", "USER_A", 10.0),
            ("2026-04-02", "USER_B", 1.0),
            ("2026-04-03", "USER_C", 1.0),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) >= 1
        assert "USER_A" in result[0].message

    def test_no_outlier_no_violation(self):
        rule = CortexAIFunctionPerUserSpendCheck()
        rows = (
            ("2026-04-01", "U1", 2.0),
            ("2026-04-02", "U2", 2.0),
            ("2026-04-03", "U3", 2.0),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAIFunctionPerUserSpendCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_020 CortexAISQLAdoptionCheck
# ---------------------------------------------------------------------------


class TestCortexAISQLAdoptionCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAISQLAdoptionCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_view_unavailable_flags_violation(self):
        rule = CortexAISQLAdoptionCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "CORTEX_AISQL" in result[0].message

    def test_view_available_no_violation(self):
        rule = CortexAISQLAdoptionCheck()
        rows = (("2026-04-01", "USER1", 1.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_unexpected_error_raises(self):
        rule = CortexAISQLAdoptionCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(RuntimeError("bad"))
        with pytest.raises(RuleExecutionError):
            rule.check_online(cursor, scan_context=ctx)


# ---------------------------------------------------------------------------
# COST_021 CortexCodeCLIPerUserLimitCheck
# ---------------------------------------------------------------------------


class TestCortexCodeCLIPerUserLimitCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexCodeCLIPerUserLimitCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_user_near_limit_3_days_flagged(self):
        rule = CortexCodeCLIPerUserLimitCheck()
        # usage 9.0 / limit 10.0 = 90% > 80%, 3 days
        rows = tuple((f"2026-04-0{i}", "NOAH", 9.0, 10.0) for i in range(1, 4))
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "NOAH" in result[0].message

    def test_under_limit_no_violation(self):
        rule = CortexCodeCLIPerUserLimitCheck()
        rows = tuple((f"2026-04-0{i}", "NOAH", 1.0, 10.0) for i in range(1, 5))
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexCodeCLIPerUserLimitCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_022 CortexCodeCLIZombieUsageCheck
# ---------------------------------------------------------------------------


class TestCortexCodeCLIZombieUsageCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexCodeCLIZombieUsageCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_no_usage_at_all_flags_account(self):
        rule = CortexCodeCLIZombieUsageCheck()
        ctx = _make_ctx_with_cached(rule.VIEW, ())
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "No Cortex Code CLI" in result[0].message

    def test_active_users_present_no_violation(self):
        rule = CortexCodeCLIZombieUsageCheck()
        rows = (("2026-04-01", "NOAH", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_account_level_violation(self):
        # When view is unavailable (allowlisted error), rows=() → "no usage" violation
        # (COST_022 treats empty usage as a signal, not a skip)
        rule = CortexCodeCLIZombieUsageCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "No Cortex Code CLI" in result[0].message


# ---------------------------------------------------------------------------
# COST_023 CortexCodeCLICreditSpikeCheck
# ---------------------------------------------------------------------------


class TestCortexCodeCLICreditSpikeCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexCodeCLICreditSpikeCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_spike_flagged(self):
        rule = CortexCodeCLICreditSpikeCheck()
        # Day 1: 1 credit; Day 2: 10 credits → 10x spike > 5x threshold
        rows = (
            ("2026-04-01", "NOAH", 1.0),
            ("2026-04-02", "NOAH", 10.0),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "spike" in result[0].message.lower() or "10" in result[0].message

    def test_no_spike_no_violation(self):
        rule = CortexCodeCLICreditSpikeCheck()
        rows = (
            ("2026-04-01", "NOAH", 5.0),
            ("2026-04-02", "NOAH", 6.0),
        )
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_single_row_returns_empty(self):
        rule = CortexCodeCLICreditSpikeCheck()
        rows = (("2026-04-01", "NOAH", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_024 CortexAgentBudgetEnforcementCheck
# ---------------------------------------------------------------------------


class TestCortexAgentBudgetEnforcementCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAgentBudgetEnforcementCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_agent_without_budget_flagged(self):
        rule = CortexAgentBudgetEnforcementCheck()
        rows = (("2026-04-01", "SALES_AGENT", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        cursor.fetchall.return_value = []  # SHOW BUDGETS returns nothing
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "SALES_AGENT" in result[0].message

    def test_agent_with_budget_no_violation(self):
        rule = CortexAgentBudgetEnforcementCheck()
        rows = (("2026-04-01", "SALES_AGENT", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        # SHOW BUDGETS returns a row with AGENT_SALES_AGENT → strips prefix
        cursor.fetchall.return_value = [(1, "AGENT_SALES_AGENT")]
        result = rule.check_online(cursor, scan_context=ctx)
        assert result == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAgentBudgetEnforcementCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_025 CortexAgentSpendCapCheck
# ---------------------------------------------------------------------------


class TestCortexAgentSpendCapCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAgentSpendCapCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_over_threshold_flagged(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 10.0
        rule = CortexAgentSpendCapCheck(conventions=conv)
        rows = (("2026-04-01", "MY_AGENT", 50.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "MY_AGENT" in result[0].message

    def test_under_threshold_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 100.0
        rule = CortexAgentSpendCapCheck(conventions=conv)
        rows = (("2026-04-01", "MY_AGENT", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_026 CortexAgentTagCoverageCheck
# ---------------------------------------------------------------------------


class TestCortexAgentTagCoverageCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAgentTagCoverageCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_untagged_agent_flagged(self):
        rule = CortexAgentTagCoverageCheck()
        rows = (("2026-04-01", "UNTAGGED_AGENT", 5.0, None),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "UNTAGGED_AGENT" in result[0].message

    def test_tagged_agent_no_violation(self):
        rule = CortexAgentTagCoverageCheck()
        rows = (("2026-04-01", "TAGGED_AGENT", 5.0, '{"team":"sales"}'),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_027 SnowflakeIntelligenceDailySpendCheck
# ---------------------------------------------------------------------------


class TestSnowflakeIntelligenceDailySpendCheck:
    def test_none_scan_context_returns_empty(self):
        assert SnowflakeIntelligenceDailySpendCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_over_limit_flagged(self):
        conv = MagicMock()
        conv.thresholds.cortex.snowflake_intelligence_max_daily_credits = 10.0
        rule = SnowflakeIntelligenceDailySpendCheck(conventions=conv)
        rows = (("2026-04-01", "INTEL_1", 100.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "INTEL_1" in result[0].message

    def test_under_limit_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.snowflake_intelligence_max_daily_credits = 500.0
        rule = SnowflakeIntelligenceDailySpendCheck(conventions=conv)
        rows = (("2026-04-01", "INTEL_1", 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_028 SnowflakeIntelligenceGovernanceCheck
# ---------------------------------------------------------------------------


class TestSnowflakeIntelligenceGovernanceCheck:
    def test_none_scan_context_returns_empty(self):
        assert SnowflakeIntelligenceGovernanceCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_untagged_intelligence_flagged(self):
        rule = SnowflakeIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "INTEL_X", 5.0, None),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "INTEL_X" in result[0].message

    def test_tagged_intelligence_no_violation(self):
        rule = SnowflakeIntelligenceGovernanceCheck()
        rows = (("2026-04-01", "INTEL_X", 5.0, '{"cost_center":"eng"}'),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_029 CortexSearchConsumptionBreakdownCheck
# ---------------------------------------------------------------------------


class TestCortexSearchConsumptionBreakdownCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexSearchConsumptionBreakdownCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_over_threshold_flagged(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 10.0
        rule = CortexSearchConsumptionBreakdownCheck(conventions=conv)
        rows = (("2026-04-01", "SEARCH_SVC", 50.0, 30.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "SEARCH_SVC" in result[0].message

    def test_under_threshold_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 1000.0
        rule = CortexSearchConsumptionBreakdownCheck(conventions=conv)
        rows = (("2026-04-01", "SEARCH_SVC", 2.0, 1.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_030 CortexSearchZombieServiceCheck
# ---------------------------------------------------------------------------


class TestCortexSearchZombieServiceCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexSearchZombieServiceCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_zombie_service_flagged(self):
        rule = CortexSearchZombieServiceCheck()
        # col layout: USAGE_DATE, SERVICE_NAME, SERVING_CREDITS, BATCH_CREDITS
        rows = (("2026-04-01", "ZOMBIE_SVC", 0.0, 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "ZOMBIE_SVC" in result[0].message
        assert "zombie" in result[0].message.lower()

    def test_active_service_no_violation(self):
        rule = CortexSearchZombieServiceCheck()
        rows = (("2026-04-01", "ACTIVE_SVC", 10.0, 5.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexSearchZombieServiceCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_031 CortexAnalystPerUserQuotaCheck
# ---------------------------------------------------------------------------


class TestCortexAnalystPerUserQuotaCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAnalystPerUserQuotaCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_over_quota_flagged(self):
        conv = MagicMock()
        conv.thresholds.cortex.analyst_max_requests_per_user_per_day = 100
        rule = CortexAnalystPerUserQuotaCheck(conventions=conv)
        rows = tuple(("2026-04-01", "HEAVY_USER", 10) for _ in range(20))
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) >= 1
        assert "HEAVY_USER" in result[0].message

    def test_under_quota_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.analyst_max_requests_per_user_per_day = 1000
        rule = CortexAnalystPerUserQuotaCheck(conventions=conv)
        rows = (("2026-04-01", "LIGHT_USER", 5),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_032 CortexAnalystEnabledWithoutBudgetCheck
# ---------------------------------------------------------------------------


class TestCortexAnalystEnabledWithoutBudgetCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexAnalystEnabledWithoutBudgetCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_usage_without_budget_flagged(self):
        rule = CortexAnalystEnabledWithoutBudgetCheck()
        rows = (("2026-04-01", "USER1", 5),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)  # no budgets
        result = rule.check_online(cursor, scan_context=ctx)
        assert len(result) == 1
        assert "no Snowflake Budget" in result[0].message

    def test_usage_with_budget_no_violation(self):
        rule = CortexAnalystEnabledWithoutBudgetCheck()
        rows = (("2026-04-01", "USER1", 5),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)  # budget exists
        assert rule.check_online(cursor, scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexAnalystEnabledWithoutBudgetCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# COST_033 CortexDocumentProcessingSpendCheck
# ---------------------------------------------------------------------------


class TestCortexDocumentProcessingSpendCheck:
    def test_none_scan_context_returns_empty(self):
        assert CortexDocumentProcessingSpendCheck().check_online(_cursor_empty(), scan_context=None) == []

    def test_over_threshold_flagged(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 10.0
        rule = CortexDocumentProcessingSpendCheck(conventions=conv)
        rows = (("2026-04-01", "BATCH_JOB", 500.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        result = rule.check_online(_cursor_empty(), scan_context=ctx)
        assert len(result) == 1
        assert "500" in result[0].message

    def test_under_threshold_no_violation(self):
        conv = MagicMock()
        conv.thresholds.cortex.daily_credit_hard_limit = 1000.0
        rule = CortexDocumentProcessingSpendCheck(conventions=conv)
        rows = (("2026-04-01", "BATCH_JOB", 2.0),)
        ctx = _make_ctx_with_cached(rule.VIEW, rows)
        assert rule.check_online(_cursor_empty(), scan_context=ctx) == []

    def test_view_unavailable_returns_empty(self):
        rule = CortexDocumentProcessingSpendCheck()
        ctx = ScanContext()
        cursor = _make_cursor_raising(_make_allowlisted_error())
        assert rule.check_online(cursor, scan_context=ctx) == []


# ---------------------------------------------------------------------------
# get_cortex_rules() factory
# ---------------------------------------------------------------------------


def test_get_cortex_rules_returns_18_rules():
    rules = get_cortex_rules()
    assert len(rules) == 18


def test_get_cortex_rules_all_have_unique_ids():
    rules = get_cortex_rules()
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids)), "Duplicate rule IDs detected"


def test_get_cortex_rules_ids_in_range():
    rules = get_cortex_rules()
    for rule in rules:
        num = int(rule.id.split("_")[1])
        assert 16 <= num <= 33, f"Rule {rule.id} out of expected range"


# ---------------------------------------------------------------------------
# AC-1: COST_016 data-processing path must raise RuleExecutionError, not swallow
# ---------------------------------------------------------------------------


class TestCOST016DataProcessingErrorPropagation:
    """The try/except around the credit_by_day aggregation loop (line ~196)
    must NOT silently return [].  Non-allowlisted errors must raise
    RuleExecutionError so they appear as ERRORED findings."""

    def test_data_processing_error_raises_rule_execution_error(self):
        """A RuntimeError during credit aggregation must raise RuleExecutionError."""
        rule = CortexAIFunctionCreditBudgetCheck()

        class ExplodingRow:
            def __getitem__(self, idx):
                if isinstance(idx, slice):
                    raise RuntimeError("unexpected aggregation error")
                if idx == 0:
                    return "2026-04-01T00:00:00"
                return "x"

            def __len__(self):
                return 4

        ctx = _make_ctx_with_cached(rule.VIEW, (ExplodingRow(),))
        with pytest.raises(RuleExecutionError):
            rule.check_online(_cursor_empty(), scan_context=ctx)
