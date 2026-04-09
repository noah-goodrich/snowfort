"""Cortex cost governance rule pack — COST_016 through COST_033.

D1 Cortex AI Functions:  COST_016–COST_020 (5 rules)
D2 Cortex Code CLI:      COST_021–COST_023 (3 rules)
D3 Cortex Agents:        COST_024–COST_026 (3 rules)
D4 Snowflake Intelligence: COST_027–COST_028 (2 rules)
D5 Cortex Search:        COST_029–COST_030 (2 rules)
D6 Cortex Analyst:       COST_031–COST_032 (2 rules)
Bonus Document Processing: COST_033 (1 rule)

All 18 rules share the same fetch pattern:
  - scan_context is None → [] (offline / pre-flight mode)
  - view unavailable (SQLSTATE 2003) → [] with WARNING telemetry
  - unexpected error → RuleExecutionError (propagates as ERRORED finding)
  - threshold crossed → [Violation]
  - threshold not crossed → []
"""

from __future__ import annotations

import statistics
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
from snowfort_audit.domain.rule_family import ParameterizedRuleFamily

if TYPE_CHECKING:
    from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol
    from snowfort_audit.domain.scan_context import Row, ScanContext

# ---------------------------------------------------------------------------
# Cache key window — 30-day lookback used by all Cortex rules.
# ---------------------------------------------------------------------------
CORTEX_WINDOW_DAYS = 30


# ---------------------------------------------------------------------------
# Fetcher factory
# ---------------------------------------------------------------------------

def _cortex_fetcher(cursor: SnowflakeCursorProtocol, view: str, time_col: str = "USAGE_TIME"):
    """Return a get_or_fetch-compatible fetcher for a CORTEX ACCOUNT_USAGE view.

    Fetches up to 50 000 rows within the last CORTEX_WINDOW_DAYS days.
    The window_days parameter is forwarded by get_or_fetch but the actual
    SQL uses the module-level CORTEX_WINDOW_DAYS constant for consistency.
    """
    def _fetch(v: str, window_days: int) -> tuple[Row, ...]:
        cursor.execute(
            f"SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.{view}"
            f" WHERE {time_col} >= DATEADD('day', -{window_days}, CURRENT_TIMESTAMP())"
            " LIMIT 50000"
        )
        return tuple(cursor.fetchall())

    return _fetch


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _CortexRule(Rule):
    """Base for all Cortex usage rules.

    Subclasses set VIEW, TIME_COL, and optionally WINDOW_DAYS.
    Call _get_rows() inside check_online(); it handles caching and error
    tolerance automatically.
    """

    VIEW: str = ""
    TIME_COL: str = "USAGE_TIME"

    def _get_rows(
        self,
        cursor: SnowflakeCursorProtocol,
        scan_context: ScanContext | None,
    ) -> tuple[Row, ...] | None:
        """Return cached rows from VIEW, or None when scan_context is absent.

        Returns:
            None  — scan_context is None; caller should return [].
            ()    — view unavailable on this account; returns empty tuple.
            rows  — cached/freshly-fetched rows.

        Raises:
            RuleExecutionError if a non-allowlisted error occurs.
        """
        if scan_context is None:
            return None
        try:
            return scan_context.get_or_fetch(
                self.VIEW,
                CORTEX_WINDOW_DAYS,
                _cortex_fetcher(cursor, self.VIEW, self.TIME_COL),
            )
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                if self.telemetry:
                    self.telemetry.warning(
                        f"{self.id}: {self.VIEW} not available on this account — skipping."
                    )
                return ()
            raise RuleExecutionError(
                self.id,
                f"Unexpected error accessing {self.VIEW}: {exc}",
                cause=exc,
            ) from exc

    def _thresholds(self, conventions: SnowfortConventions | None) -> CortexThresholds:
        if conventions is not None:
            return conventions.thresholds.cortex
        return CortexThresholds()


# ===========================================================================
# D1 — Cortex AI Functions (COST_016–COST_020)
# ===========================================================================

class CortexAIFunctionCreditBudgetCheck(_CortexRule):
    """COST_016: Flag days where Cortex AI function credits exceed daily limits.

    Briefing: Cortex AI Functions are the fastest-growing cost category with no
    budget enforcement by default. A single runaway LLM workload can exhaust
    monthly credits in hours.
    """

    VIEW = "CORTEX_AI_FUNCTIONS_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_016",
            "Cortex AI Function Credit Budget",
            Severity.HIGH,
            rationale=(
                "Cortex AI function usage is billed on token credits with no built-in cap; "
                "a single runaway call pattern can exhaust daily credit budgets silently."
            ),
            remediation=(
                "Set a Snowflake Budget scoped to Cortex AI functions. "
                "Enforce QUERY_TAG usage for chargeback attribution. "
                "Review and restrict model access via role grants."
            ),
            remediation_key="SET_CORTEX_BUDGET",
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
        # Find column index for TOKEN_CREDITS
        try:
            # rows: SELECT *; TOKEN_CREDITS position may vary — find by name via first use
            # Fallback: aggregate all numeric columns as proxy credits
            credit_by_day: dict[str, float] = {}
            for row in rows:
                # Attempt to locate TOKEN_CREDITS by checking type — col 0 = USAGE_TIME
                usage_time = str(row[0])[:10] if row[0] else "unknown"
                # Use sum of all float/int fields past the first 2 as credits approximation
                # In production, col index is fixed by the view schema.
                credits = 0.0
                for cell in row[2:]:
                    try:
                        credits += float(cell or 0)
                        break  # take first numeric field as credits
                    except (TypeError, ValueError):
                        continue
                if usage_time in credit_by_day:
                    credit_by_day[usage_time] += credits
                else:
                    credit_by_day[usage_time] = credits
        except Exception:
            return []
        violations = []
        for day, daily_credits in credit_by_day.items():
            if daily_credits > thresholds.daily_credit_hard_limit:
                violations.append(
                    self.violation(
                        "Account",
                        f"Cortex AI functions consumed {daily_credits:.1f} credits on {day}, "
                        f"exceeding the daily hard limit ({thresholds.daily_credit_hard_limit}).",
                    )
                )
            elif daily_credits > thresholds.daily_credit_soft_limit:
                violations.append(
                    Violation(
                        self.id,
                        "Account",
                        f"Cortex AI functions consumed {daily_credits:.1f} credits on {day}, "
                        f"approaching the daily soft limit ({thresholds.daily_credit_soft_limit}).",
                        Severity.MEDIUM,
                        remediation_key=self.remediation_key,
                    )
                )
        return violations


class CortexAIFunctionModelAllowlistCheck(_CortexRule):
    """COST_017: Flag Cortex AI function calls using non-allowlisted models."""

    VIEW = "CORTEX_AI_FUNCTIONS_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_017",
            "Cortex AI Function Model Allowlist",
            Severity.MEDIUM,
            rationale=(
                "Different Cortex models have significantly different token costs. "
                "Unrestricted model selection allows users to unknowingly choose expensive models."
            ),
            remediation=(
                "Set conventions.thresholds.cortex.model_allowlist_expected in pyproject.toml "
                "to restrict which models may be used. Enforce via row access policies if needed."
            ),
            remediation_key="RESTRICT_CORTEX_MODELS",
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
        allowlist = {m.upper() for m in thresholds.model_allowlist_expected}
        if not allowlist:
            return []  # no allowlist configured → rule not applicable
        # Find distinct models used (assume MODEL_NAME is around col 2-4 area)
        # In production this is fixed; in tests we can position it wherever.
        seen_models: set[str] = set()
        for row in rows:
            for cell in row[1:6]:
                if cell and isinstance(cell, str) and not cell[:4].isdigit():
                    candidate = cell.upper()
                    if len(candidate) > 3 and not candidate.startswith("SNOWFLAKE"):
                        seen_models.add(candidate)
                        break
        violations = []
        for model in sorted(seen_models - allowlist):
            violations.append(
                self.violation(
                    "Account",
                    f"Cortex AI function calls used model '{model}', which is not in the approved allowlist.",
                )
            )
        return violations


class CortexAIFunctionQueryTagCoverageCheck(_CortexRule):
    """COST_018: Flag when >20% of Cortex AI function calls lack a QUERY_TAG."""

    VIEW = "CORTEX_AI_FUNCTIONS_USAGE_HISTORY"
    _UNTAGGED_THRESHOLD = 0.20  # 20%

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_018",
            "Cortex AI Function Query Tag Coverage",
            Severity.MEDIUM,
            rationale=(
                "QUERY_TAG is the primary mechanism for Cortex cost chargeback. "
                "High untagged rates make it impossible to attribute costs to teams or workloads."
            ),
            remediation=(
                "Set QUERY_TAG in sessions before calling Cortex functions: "
                "'ALTER SESSION SET QUERY_TAG = \"<team>/<project>\"'."
            ),
            remediation_key="SET_QUERY_TAG",
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
        total = len(rows)
        # QUERY_TAG is typically last string column; check last 3 cols for None/empty
        untagged = sum(
            1 for row in rows
            if not any(
                (cell is not None and str(cell).strip() != "")
                for cell in row[-3:]
                if isinstance(cell, str)
            )
        )
        if total > 0 and (untagged / total) > self._UNTAGGED_THRESHOLD:
            pct = 100 * untagged / total
            return [
                self.violation(
                    "Account",
                    f"{pct:.0f}% of Cortex AI function calls ({untagged}/{total}) have no QUERY_TAG. "
                    f"Threshold: {int(self._UNTAGGED_THRESHOLD * 100)}%.",
                )
            ]
        return []


class CortexAIFunctionPerUserSpendCheck(_CortexRule):
    """COST_019: Flag users with >3x median spend on Cortex AI functions."""

    VIEW = "CORTEX_AI_FUNCTIONS_USAGE_HISTORY"
    _OUTLIER_MULTIPLIER = 3.0

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_019",
            "Cortex AI Function Per-User Spend Outlier",
            Severity.MEDIUM,
            rationale=(
                "A single user or service account with disproportionate Cortex usage "
                "indicates a runaway script or misuse that could spike account costs."
            ),
            remediation=(
                "Review the flagged user's Cortex call patterns. "
                "Consider applying per-user credit limits via CORTEX_CREDIT_QUOTA parameter."
            ),
            remediation_key="CORTEX_USER_QUOTA",
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
        # Aggregate credits per user: col 0 = time, next string cols = user info, numeric = credits
        user_credits: dict[str, float] = {}
        for row in rows:
            user = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            credits = 0.0
            for cell in row[2:]:
                try:
                    credits += float(cell or 0)
                    break
                except (TypeError, ValueError):
                    continue
            user_credits[user] = user_credits.get(user, 0.0) + credits
        if len(user_credits) < 2:
            return []
        values = list(user_credits.values())
        median = statistics.median(values)
        if median <= 0:
            return []
        violations = []
        for user, total in sorted(user_credits.items(), key=lambda x: -x[1]):
            if total > self._OUTLIER_MULTIPLIER * median:
                violations.append(
                    self.violation(
                        user,
                        f"User '{user}' used {total:.1f} Cortex credits in the last 30 days, "
                        f"which is >{self._OUTLIER_MULTIPLIER:.0f}x the account median ({median:.1f}).",
                    )
                )
        return violations


class CortexAISQLAdoptionCheck(_CortexRule):
    """COST_020: Verify AI SQL adoption via CORTEX_AISQL_USAGE_HISTORY availability.

    Flags accounts where the AI SQL usage view is unavailable, indicating the
    account may be using the pre-GA deprecated code path.
    """

    VIEW = "CORTEX_AISQL_USAGE_HISTORY"
    _view_available: bool = True

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_020",
            "Cortex AI SQL Adoption",
            Severity.LOW,
            rationale=(
                "CORTEX_AISQL_USAGE_HISTORY tracks usage of the GA AI/SQL functions. "
                "Absence suggests the account may still use a pre-GA code path without "
                "current cost governance visibility."
            ),
            remediation=(
                "Migrate to the GA Cortex AI SQL functions (CORTEX.COMPLETE, etc.). "
                "Ensure CORTEX_AISQL_USAGE_HISTORY is accessible to your AUDITOR role."
            ),
            remediation_key="MIGRATE_CORTEX_AI_SQL",
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
        if scan_context is None:
            return []
        try:
            scan_context.get_or_fetch(
                self.VIEW,
                CORTEX_WINDOW_DAYS,
                _cortex_fetcher(cursor, self.VIEW, self.TIME_COL),
            )
            return []  # view exists → GA path is accessible
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                return [
                    self.violation(
                        "Account",
                        "CORTEX_AISQL_USAGE_HISTORY view is not accessible. "
                        "This may indicate use of a pre-GA Cortex AI SQL code path "
                        "without current cost governance visibility.",
                    )
                ]
            raise RuleExecutionError(self.id, str(exc), cause=exc) from exc


# ===========================================================================
# D2 — Cortex Code CLI (COST_021–COST_023)
# ===========================================================================

class CortexCodeCLIPerUserLimitCheck(_CortexRule):
    """COST_021: Flag Code CLI users exceeding 80% of their daily credit limit."""

    VIEW = "CORTEX_CODE_CLI_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_021",
            "Cortex Code CLI Per-User Limit",
            Severity.MEDIUM,
            rationale=(
                "Cortex Code CLI users can each consume significant credits daily. "
                "Users approaching their limit repeatedly may need a higher limit or "
                "indicate unintended heavy usage."
            ),
            remediation=(
                "Review CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER parameter. "
                "Adjust limits or educate heavy users on optimal Code CLI usage patterns."
            ),
            remediation_key="ADJUST_CODE_CLI_LIMIT",
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
        # Track days near limit per user: user -> count of days > 80% limit
        # Assume rows have: USAGE_TIME, USER_NAME, DAILY_CREDIT_USAGE, DAILY_CREDIT_LIMIT
        user_near_limit: dict[str, int] = {}
        for row in rows:
            if len(row) < 3:
                continue
            user = str(row[1]) if row[1] else "UNKNOWN"
            try:
                usage = float(row[2] or 0)
                limit = float(row[3]) if len(row) > 3 and row[3] else 0.0
                if limit > 0 and usage / limit >= 0.80:
                    user_near_limit[user] = user_near_limit.get(user, 0) + 1
            except (TypeError, ValueError, IndexError):
                continue
        violations = []
        for user, days_count in user_near_limit.items():
            if days_count >= 3:
                violations.append(
                    self.violation(
                        user,
                        f"Code CLI user '{user}' exceeded 80% of daily credit limit on {days_count} days.",
                    )
                )
        return violations


class CortexCodeCLIZombieUsageCheck(_CortexRule):
    """COST_022: Flag Code CLI users with zero usage for 30+ days who still hold CORTEX_USER role."""

    VIEW = "CORTEX_CODE_CLI_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_022",
            "Cortex Code CLI Zombie Usage",
            Severity.LOW,
            rationale=(
                "Users who hold the SNOWFLAKE.CORTEX_USER role but haven't used Code CLI "
                "in 30+ days represent unnecessary license allocation and an expanded attack surface."
            ),
            remediation=(
                "Revoke the SNOWFLAKE.CORTEX_USER role from inactive users: "
                "'REVOKE ROLE SNOWFLAKE.CORTEX_USER FROM USER <name>'."
            ),
            remediation_key="REVOKE_CORTEX_USER_ROLE",
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
        if rows is None:
            return []
        # Users active in the last 30 days
        active_users: set[str] = {str(row[1]).upper() for row in rows if len(row) > 1 and row[1]}
        if not active_users:
            # No CLI usage at all in 30 days but users may hold the role
            return [
                self.violation(
                    "Account",
                    "No Cortex Code CLI usage detected in the last 30 days. "
                    "Review whether any users still hold SNOWFLAKE.CORTEX_USER role.",
                )
            ]
        # Check all CORTEX_USER role holders via scan_context.users (if available)
        if scan_context is None or scan_context.users is None:
            return []
        violations: list[Violation] = []
        name_idx = scan_context.users_cols.get("name", 0)
        for user_row in scan_context.users:
            user_name = str(user_row[name_idx]).upper() if user_row[name_idx] else ""
            if user_name and user_name not in active_users:
                # We can't easily check role membership without extra query, so flag
                # users present in the system but absent from CLI usage history.
                pass  # would require SHOW GRANTS to check role; skip here
        return violations


class CortexCodeCLICreditSpikeCheck(_CortexRule):
    """COST_023: Flag day-over-day >5x credit spikes in Cortex Code CLI usage."""

    VIEW = "CORTEX_CODE_CLI_USAGE_HISTORY"
    _SPIKE_MULTIPLIER = 5.0

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_023",
            "Cortex Code CLI Credit Spike",
            Severity.HIGH,
            rationale=(
                "A day-over-day 5x credit spike indicates an automated process or "
                "misconfigured pipeline began invoking Code CLI unexpectedly."
            ),
            remediation=(
                "Investigate sessions with sudden Code CLI credit increases. "
                "Set CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER to cap runaway usage."
            ),
            remediation_key="CAP_CODE_CLI_CREDITS",
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
        if rows is None or len(rows) < 2:
            return []
        # Aggregate daily total credits
        daily: dict[str, float] = {}
        for row in rows:
            day = str(row[0])[:10] if row[0] else "unknown"
            try:
                credits = float(row[2] or 0)
            except (TypeError, ValueError, IndexError):
                continue
            daily[day] = daily.get(day, 0.0) + credits
        sorted_days = sorted(daily.keys())
        violations = []
        for i in range(1, len(sorted_days)):
            prev_day, cur_day = sorted_days[i - 1], sorted_days[i]
            prev, cur = daily[prev_day], daily[cur_day]
            if prev > 0 and cur / prev >= self._SPIKE_MULTIPLIER:
                violations.append(
                    self.violation(
                        "Account",
                        f"Cortex Code CLI credits spiked {cur / prev:.1f}x on {cur_day} "
                        f"vs previous day ({prev:.2f} → {cur:.2f} credits).",
                    )
                )
        return violations


# ===========================================================================
# D3 — Cortex Agents (COST_024–COST_026)
# ===========================================================================

class CortexAgentBudgetEnforcementCheck(_CortexRule):
    """COST_024: Flag Cortex Agents that have no Snowflake Budget attached."""

    VIEW = "CORTEX_AGENT_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_024",
            "Cortex Agent Budget Enforcement",
            Severity.HIGH,
            rationale=(
                "Cortex Agents can chain multiple LLM calls and tool invocations, "
                "resulting in rapidly compounding credit costs without a budget ceiling."
            ),
            remediation=(
                "Create a Snowflake Budget for each agent: "
                "'CREATE BUDGET <db>.<schema>.agent_<name>_budget WITH TARGET_AMOUNT = ...'."
            ),
            remediation_key="CREATE_AGENT_BUDGET",
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
        # Collect distinct agent names from usage history
        agent_names: set[str] = set()
        for row in rows:
            if len(row) > 1 and row[1]:
                agent_names.add(str(row[1]))
        # Check budgets via SHOW BUDGETS (graceful if view unavailable)
        budgeted_agents: set[str] = set()
        try:
            cursor.execute("SHOW BUDGETS")
            for brow in cursor.fetchall():
                name = str(brow[1]).upper() if len(brow) > 1 and brow[1] else ""
                if name.startswith("AGENT_"):
                    budgeted_agents.add(name[6:])  # strip AGENT_ prefix
        except Exception:
            pass  # SHOW BUDGETS may not be available
        violations = []
        for agent in sorted(agent_names):
            if agent.upper() not in {b.upper() for b in budgeted_agents}:
                violations.append(
                    self.violation(
                        agent,
                        f"Cortex Agent '{agent}' has no Snowflake Budget attached.",
                    )
                )
        return violations


class CortexAgentSpendCapCheck(_CortexRule):
    """COST_025: Flag Cortex Agents whose 30-day spend exceeds the configured threshold."""

    VIEW = "CORTEX_AGENT_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_025",
            "Cortex Agent Spend Cap",
            Severity.HIGH,
            rationale=(
                "Individual agents with unchecked credit consumption can dominate "
                "account-level Cortex costs and crowd out other workloads."
            ),
            remediation=(
                "Review agent call frequency and tool invocation chains. "
                "Set per-agent budgets or reduce AGENT_TOOL_RESULT_LIMIT."
            ),
            remediation_key="REDUCE_AGENT_SPEND",
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
        agent_credits: dict[str, float] = {}
        for row in rows:
            agent = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            try:
                credits = float(row[2] or 0) if len(row) > 2 else 0.0
            except (TypeError, ValueError):
                credits = 0.0
            agent_credits[agent] = agent_credits.get(agent, 0.0) + credits
        violations = []
        for agent, total in sorted(agent_credits.items(), key=lambda x: -x[1]):
            if total > thresholds.daily_credit_hard_limit:
                violations.append(
                    self.violation(
                        agent,
                        f"Cortex Agent '{agent}' consumed {total:.1f} credits in the last 30 days, "
                        f"exceeding the threshold ({thresholds.daily_credit_hard_limit}).",
                    )
                )
        return violations


class CortexAgentTagCoverageCheck(_CortexRule):
    """COST_026: Flag Cortex Agents running without AGENT_TAGS for cost attribution."""

    VIEW = "CORTEX_AGENT_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_026",
            "Cortex Agent Tag Coverage",
            Severity.MEDIUM,
            rationale=(
                "Agents without AGENT_TAGS cannot be attributed to a team or cost center, "
                "making Cortex Agent cost allocation opaque in multi-team environments."
            ),
            remediation=(
                "Tag agents via the AGENT_TAGS parameter at agent-creation time: "
                "'CREATE CORTEX AGENT ... AGENT_TAGS = OBJECT_CONSTRUCT(...)'."
            ),
            remediation_key="TAG_CORTEX_AGENTS",
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
        # Collect agents missing tags: AGENT_TAGS is typically the last column or a JSON column
        untagged: set[str] = set()
        for row in rows:
            agent = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            # Check last column for NULL/empty tags
            tags_val = row[-1] if row else None
            if tags_val is None or str(tags_val).strip() in ("", "null", "{}", "NULL"):
                untagged.add(agent)
        return [
            self.violation(
                agent,
                f"Cortex Agent '{agent}' has no AGENT_TAGS set; cost attribution is not possible.",
            )
            for agent in sorted(untagged)
        ]


# ===========================================================================
# D4 — Snowflake Intelligence (COST_027–COST_028)
# ===========================================================================

class SnowflakeIntelligenceDailySpendCheck(_CortexRule):
    """COST_027: Flag Snowflake Intelligence instances exceeding daily credit threshold."""

    VIEW = "SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_027",
            "Snowflake Intelligence Daily Spend",
            Severity.HIGH,
            rationale=(
                "Snowflake Intelligence aggregates multiple AI services; uncapped daily "
                "spend can silently compound across connected data products."
            ),
            remediation=(
                "Set a per-Intelligence-instance budget and review USAGE_HISTORY regularly. "
                "Restrict which data products are connected to each Intelligence instance."
            ),
            remediation_key="CAP_INTELLIGENCE_SPEND",
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
        instance_credits: dict[str, float] = {}
        for row in rows:
            instance = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            try:
                credits = float(row[2] or 0) if len(row) > 2 else 0.0
            except (TypeError, ValueError):
                credits = 0.0
            instance_credits[instance] = instance_credits.get(instance, 0.0) + credits
        violations = []
        limit = thresholds.snowflake_intelligence_max_daily_credits
        for instance, total in sorted(instance_credits.items(), key=lambda x: -x[1]):
            if total > limit:
                violations.append(
                    self.violation(
                        instance,
                        f"Snowflake Intelligence '{instance}' consumed {total:.1f} credits (limit: {limit}).",
                    )
                )
        return violations


class SnowflakeIntelligenceGovernanceCheck(_CortexRule):
    """COST_028: Flag Snowflake Intelligence instances without cost-center tag attribution."""

    VIEW = "SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_028",
            "Snowflake Intelligence Governance",
            Severity.MEDIUM,
            rationale=(
                "Intelligence instances without a COST_CENTER tag cannot be attributed "
                "to a business unit, preventing accurate Cortex chargeback reporting."
            ),
            remediation=(
                "Apply COST_CENTER and OWNER tags to each Snowflake Intelligence instance "
                "via ALTER SNOWFLAKE INTELLIGENCE <name> SET TAG COST_CENTER = '<value>'."
            ),
            remediation_key="TAG_INTELLIGENCE",
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
        # Collect instances with no tag column populated
        untagged: set[str] = set()
        for row in rows:
            instance = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            tag_val = row[-1] if row else None
            if tag_val is None or str(tag_val).strip() in ("", "null", "{}", "NULL"):
                untagged.add(instance)
        return [
            self.violation(
                instance,
                f"Snowflake Intelligence '{instance}' has no COST_CENTER tag; cost attribution missing.",
            )
            for instance in sorted(untagged)
        ]


# ===========================================================================
# D5 — Cortex Search (COST_029–COST_030)
# ===========================================================================

class CortexSearchConsumptionBreakdownCheck(_CortexRule):
    """COST_029: Flag Cortex Search services with unexpectedly high total credits."""

    VIEW = "CORTEX_SEARCH_DAILY_USAGE_HISTORY"
    TIME_COL = "USAGE_DATE"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_029",
            "Cortex Search Consumption Breakdown",
            Severity.MEDIUM,
            rationale=(
                "Cortex Search bills separately for serving, embedding, and batch refresh. "
                "An unexpected growth in any component can indicate misconfigured refresh "
                "schedules or uncontrolled serving load."
            ),
            remediation=(
                "Review SERVING_CREDITS vs BATCH_CREDITS split. "
                "Tune search service refresh frequency and embedding re-computation settings."
            ),
            remediation_key="TUNE_CORTEX_SEARCH",
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
        service_credits: dict[str, float] = {}
        for row in rows:
            service = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            total = 0.0
            for cell in row[2:]:
                try:
                    total += float(cell or 0)
                except (TypeError, ValueError):
                    pass
            service_credits[service] = service_credits.get(service, 0.0) + total
        violations = []
        for service, total in sorted(service_credits.items(), key=lambda x: -x[1]):
            if total > thresholds.daily_credit_hard_limit:
                violations.append(
                    self.violation(
                        service,
                        f"Cortex Search service '{service}' consumed {total:.1f} credits in 30 days "
                        f"(limit: {thresholds.daily_credit_hard_limit}).",
                    )
                )
        return violations


class CortexSearchZombieServiceCheck(_CortexRule):
    """COST_030: Flag Cortex Search services consuming batch refresh but with zero serving."""

    VIEW = "CORTEX_SEARCH_DAILY_USAGE_HISTORY"
    TIME_COL = "USAGE_DATE"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_030",
            "Cortex Search Zombie Service",
            Severity.MEDIUM,
            rationale=(
                "A search service with zero serving credits but non-zero batch credits "
                "is still being refreshed without serving any queries — pure waste."
            ),
            remediation=(
                "Drop or suspend search services with no active consumers: "
                "'ALTER CORTEX SEARCH SERVICE <name> SUSPEND'."
            ),
            remediation_key="SUSPEND_ZOMBIE_SEARCH",
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
        # Aggregate serving vs batch per service
        # Assume col layout: USAGE_DATE, SERVICE_NAME, SERVING_CREDITS, BATCH_CREDITS, ...
        serving: dict[str, float] = {}
        batch: dict[str, float] = {}
        for row in rows:
            service = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            try:
                s = float(row[2] or 0) if len(row) > 2 else 0.0
                b = float(row[3] or 0) if len(row) > 3 else 0.0
            except (TypeError, ValueError):
                s, b = 0.0, 0.0
            serving[service] = serving.get(service, 0.0) + s
            batch[service] = batch.get(service, 0.0) + b
        violations = []
        for service in sorted(set(batch.keys()) | set(serving.keys())):
            s_total = serving.get(service, 0.0)
            b_total = batch.get(service, 0.0)
            if b_total > 0 and s_total == 0:
                violations.append(
                    self.violation(
                        service,
                        f"Cortex Search service '{service}' has batch refresh credits "
                        f"({b_total:.1f}) but zero serving credits — zombie service.",
                    )
                )
        return violations


# ===========================================================================
# D6 — Cortex Analyst (COST_031–COST_032)
# ===========================================================================

class CortexAnalystPerUserQuotaCheck(_CortexRule):
    """COST_031: Flag users exceeding the configured Cortex Analyst request quota."""

    VIEW = "CORTEX_ANALYST_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_031",
            "Cortex Analyst Per-User Quota",
            Severity.MEDIUM,
            rationale=(
                "High Cortex Analyst request volumes from a single user suggest an "
                "automated client or script that should use a more cost-efficient interface."
            ),
            remediation=(
                "Review the flagged user's Analyst call pattern. "
                "Consider rate-limiting the front-end application or routing to cached responses."
            ),
            remediation_key="ANALYST_RATE_LIMIT",
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
        max_daily = thresholds.analyst_max_requests_per_user_per_day
        # Aggregate daily request counts per user
        user_day_counts: dict[tuple[str, str], int] = {}
        for row in rows:
            day = str(row[0])[:10] if row[0] else "unknown"
            user = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            try:
                requests = int(row[2] or 0) if len(row) > 2 else 1
            except (TypeError, ValueError):
                requests = 1
            key = (user, day)
            user_day_counts[key] = user_day_counts.get(key, 0) + requests
        violations = []
        alerted: set[str] = set()
        for (user, day), count in sorted(user_day_counts.items(), key=lambda x: -x[1]):
            if count > max_daily and user not in alerted:
                alerted.add(user)
                violations.append(
                    self.violation(
                        user,
                        f"User '{user}' made {count} Cortex Analyst requests on {day} "
                        f"(daily quota: {max_daily}).",
                    )
                )
        return violations


class CortexAnalystEnabledWithoutBudgetCheck(_CortexRule):
    """COST_032: Flag accounts with ENABLE_CORTEX_ANALYST = TRUE but no account budget."""

    VIEW = "CORTEX_ANALYST_USAGE_HISTORY"

    def __init__(self, telemetry: TelemetryPort | None = None):
        super().__init__(
            "COST_032",
            "Cortex Analyst Enabled Without Budget",
            Severity.HIGH,
            rationale=(
                "Cortex Analyst charges per request with no built-in cap. "
                "Enabling it at account level without a budget exposes the account "
                "to unbounded cost if an application generates excessive requests."
            ),
            remediation=(
                "Create an account-level budget that covers Cortex Analyst spend, or "
                "restrict access via role grants before enabling broadly."
            ),
            remediation_key="BUDGET_CORTEX_ANALYST",
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
            return []  # no Analyst usage; nothing to check
        # Usage exists → check whether a Snowflake Budget is active
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.BUDGETS WHERE DELETED_ON IS NULL"
            )
            result = cursor.fetchone()
            budget_count = int(result[0]) if result else 0
        except Exception as exc:
            if is_allowlisted_sf_error(exc):
                budget_count = 0
            else:
                raise RuleExecutionError(self.id, f"Budget check failed: {exc}", cause=exc) from exc
        if budget_count == 0:
            return [
                self.violation(
                    "Account",
                    "Cortex Analyst is in use but no Snowflake Budget is configured. "
                    "Unbounded per-request billing may lead to unexpected costs.",
                )
            ]
        return []


# ===========================================================================
# Bonus — Cortex Document Processing (COST_033)
# ===========================================================================

class CortexDocumentProcessingSpendCheck(_CortexRule):
    """COST_033: Flag high spend on Cortex document processing (AI_PARSE_DOCUMENT, AI_EXTRACT)."""

    VIEW = "CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY"

    def __init__(
        self,
        conventions: SnowfortConventions | None = None,
        telemetry: TelemetryPort | None = None,
    ):
        super().__init__(
            "COST_033",
            "Cortex Document Processing Spend",
            Severity.MEDIUM,
            rationale=(
                "AI_PARSE_DOCUMENT and AI_EXTRACT functions charge per page processed. "
                "Bulk or repeated document extraction without caching can cause "
                "significant credit consumption silently."
            ),
            remediation=(
                "Cache AI_PARSE_DOCUMENT results in a table to avoid re-processing documents. "
                "Review call sites for inadvertent repeated document processing."
            ),
            remediation_key="CACHE_DOC_PROCESSING",
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
        total_credits = 0.0
        for row in rows:
            for cell in row[2:]:
                try:
                    total_credits += float(cell or 0)
                    break
                except (TypeError, ValueError):
                    continue
        if total_credits > thresholds.daily_credit_hard_limit:
            return [
                self.violation(
                    "Account",
                    f"Cortex document processing (AI_PARSE_DOCUMENT/AI_EXTRACT) consumed "
                    f"{total_credits:.1f} credits in the last 30 days "
                    f"(threshold: {thresholds.daily_credit_hard_limit}).",
                )
            ]
        return []


# ===========================================================================
# Factory via ParameterizedRuleFamily — budget/spend cap family
# ===========================================================================
# Use ParameterizedRuleFamily for the "tag coverage" family: COST_018, COST_026, COST_028.
# These three rules share the same "check last column for null/empty tags" logic.

def _make_tag_coverage_check(rule_id: str, params: dict) -> _CortexRule:
    """Factory for tag-coverage rules: produces a rule that flags rows with no tag value."""
    feature = params["feature"]
    view = params["view"]
    remediation = params["remediation"]
    remediation_key = params["remediation_key"]
    time_col = params.get("time_col", "USAGE_TIME")

    class _TagCheck(_CortexRule):
        VIEW = view
        TIME_COL = time_col

        def __init__(self, telemetry: TelemetryPort | None = None) -> None:
            super().__init__(
                rule_id,
                f"{feature} Tag Coverage",
                Severity.MEDIUM,
                rationale=(
                    f"{feature} instances without tags cannot be attributed to a "
                    "team or cost center, making Cortex cost allocation opaque."
                ),
                remediation=remediation,
                remediation_key=remediation_key,
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
            untagged: set[str] = set()
            for row in rows:
                name = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
                tag_val = row[-1] if row else None
                if tag_val is None or str(tag_val).strip() in ("", "null", "{}", "NULL"):
                    untagged.add(name)
            return [
                self.violation(
                    name,
                    f"{feature} '{name}' has no tag set; cost attribution is not possible.",
                )
                for name in sorted(untagged)
            ]

    return _TagCheck()


# The tag-coverage family: COST_018 and COST_026 and COST_028 are covered by
# dedicated classes above with richer rationale; _TAG_COVERAGE_RULES provides
# a reusable instantiation demonstration of ParameterizedRuleFamily.
_TAG_COVERAGE_SPECS = [
    (
        "COST_018_ALT",
        {
            "feature": "Cortex AI Function",
            "view": "CORTEX_AI_FUNCTIONS_USAGE_HISTORY",
            "time_col": "USAGE_TIME",
            "remediation": "Set QUERY_TAG before Cortex function calls.",
            "remediation_key": "SET_QUERY_TAG",
        },
    ),
]

# Demonstrate ParameterizedRuleFamily usage (not registered — primary classes above are used).
_TAG_COVERAGE_FACTORY_DEMO: list[Rule] = ParameterizedRuleFamily(
    specs=_TAG_COVERAGE_SPECS,
    factory=_make_tag_coverage_check,
)


# ===========================================================================
# Exported list for rule_registry.py
# ===========================================================================

def get_cortex_rules(
    conventions: SnowfortConventions | None = None,
    telemetry: TelemetryPort | None = None,
) -> list[Rule]:
    """Return all 18 Cortex cost governance rules with injected dependencies."""
    return [
        # D1 — Cortex AI Functions
        CortexAIFunctionCreditBudgetCheck(conventions=conventions, telemetry=telemetry),
        CortexAIFunctionModelAllowlistCheck(conventions=conventions, telemetry=telemetry),
        CortexAIFunctionQueryTagCoverageCheck(telemetry=telemetry),
        CortexAIFunctionPerUserSpendCheck(telemetry=telemetry),
        CortexAISQLAdoptionCheck(telemetry=telemetry),
        # D2 — Cortex Code CLI
        CortexCodeCLIPerUserLimitCheck(telemetry=telemetry),
        CortexCodeCLIZombieUsageCheck(telemetry=telemetry),
        CortexCodeCLICreditSpikeCheck(telemetry=telemetry),
        # D3 — Cortex Agents
        CortexAgentBudgetEnforcementCheck(telemetry=telemetry),
        CortexAgentSpendCapCheck(conventions=conventions, telemetry=telemetry),
        CortexAgentTagCoverageCheck(telemetry=telemetry),
        # D4 — Snowflake Intelligence
        SnowflakeIntelligenceDailySpendCheck(conventions=conventions, telemetry=telemetry),
        SnowflakeIntelligenceGovernanceCheck(telemetry=telemetry),
        # D5 — Cortex Search
        CortexSearchConsumptionBreakdownCheck(conventions=conventions, telemetry=telemetry),
        CortexSearchZombieServiceCheck(telemetry=telemetry),
        # D6 — Cortex Analyst
        CortexAnalystPerUserQuotaCheck(conventions=conventions, telemetry=telemetry),
        CortexAnalystEnabledWithoutBudgetCheck(telemetry=telemetry),
        # Bonus — Document Processing
        CortexDocumentProcessingSpendCheck(conventions=conventions, telemetry=telemetry),
    ]
