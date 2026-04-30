# Directive F: Cortex AI Governance

**Depends on:** Directive E skeleton (conventions framework), Directive C/D (RBAC + sensitive data)

**Priority:** Addresses ungoverned AI feature adoption across the full Cortex AI product
surface — the fastest-growing cost and risk category in Snowflake accounts.

*Shipped: 2026-04-30*

---

## Objective

Add 11 Cortex AI governance rules (COST_041–044 + CORTEX_001–007) that detect cost
concentration, uncontrolled access, runaway growth, and ungoverned AI feature usage
across all Snowflake Cortex AI products. Rules follow the established `_CortexRule`
base class pattern with `ScanContext` caching and graceful degradation on preview views.

## Cost Rules (COST_041–044)

| Rule ID | Name | Severity | Data Source | Key Logic |
|---------|------|----------|-------------|-----------|
| COST_041 | Cortex Auto-Model Routing Recommendation | LOW | `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Detect explicit large-model calls (llama3.1-405b, mistral-large2, claude-3-5-sonnet) that could use auto-routing |
| COST_042 | Cortex Power User Credit Concentration | MEDIUM | `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Top-N users > `power_user_concentration_threshold` (80%) of total credits |
| COST_043 | Cortex LLM Public Role Access | HIGH | Direct cursor: `SHOW GRANTS ON FUNCTION` | Flag any Cortex LLM function with USAGE granted to PUBLIC |
| COST_044 | Cortex Session Growth Trend | LOW | `METERING_DAILY_HISTORY` | Month-over-month growth ≥ 50% for 2+ consecutive months |

**Note on COST_043**: Unlike other `_CortexRule` subclasses, COST_043 uses direct cursor
queries (`SHOW GRANTS ON FUNCTION SNOWFLAKE.CORTEX.*`) because `SHOW` commands return
different row shapes than `ACCOUNT_USAGE` views and cannot be cached via `_cortex_fetcher`.

## Governance Rules (CORTEX_001–007)

| Rule ID | Name | Severity | Data Source | Key Logic |
|---------|------|----------|-------------|-----------|
| CORTEX_001 | Cortex Search Service Governance | MEDIUM | `SHOW CORTEX SEARCH SERVICES` + grants | PUBLIC access or corpus > `search_corpus_size_threshold_gb` (10 GB) |
| CORTEX_002 | Cortex Analyst Semantic Model Audit | MEDIUM | `QUERY_HISTORY` | Analyst NL-to-SQL queries detected without governed source tables |
| CORTEX_003 | Cortex Agent Governance | HIGH | `QUERY_HISTORY` | Agent sessions > `agent_max_daily_sessions` (1000/day) |
| CORTEX_004 | Cortex Intelligence Governance | MEDIUM | `METERING_DAILY_HISTORY` | Intelligence/Document AI usage detected without access policy signal |
| CORTEX_005 | Cortex Fine-Tuning Cost Tracking | MEDIUM | `QUERY_HISTORY` | Fine-tuned models with no inference usage in `fine_tuning_unused_days` (30d) |
| CORTEX_006 | Cortex LLM Function Sprawl | LOW | `QUERY_HISTORY` | Role uses > `function_sprawl_threshold` (5) distinct Cortex LLM function types |
| CORTEX_007 | Cortex Serverless AI Budget Gap | HIGH | `METERING_DAILY_HISTORY` + `SNOWFLAKE.LOCAL.BUDGETS` | Cortex spend with no Budget object covering AI services |

## CortexThresholds Extensions

8 new fields added to `CortexThresholds` frozen dataclass:

```python
power_user_concentration_threshold: float = 0.80   # COST_042
power_user_min_users: int = 3                       # COST_042
growth_rate_threshold: float = 0.50                 # COST_044
growth_consecutive_months: int = 2                  # COST_044
fine_tuning_unused_days: int = 30                   # CORTEX_005
agent_max_daily_sessions: int = 1000                # CORTEX_003
search_corpus_size_threshold_gb: int = 10           # CORTEX_001
function_sprawl_threshold: int = 5                  # CORTEX_006
```

## Architecture Patterns

### _CortexRule Subclasses
COST_041, COST_042, COST_044, CORTEX_002–007 all subclass `_CortexRule`. They:
- Set `VIEW` and `TIME_COL` class attributes
- Call `self._get_rows(cursor, scan_context)` which handles `ScanContext` caching,
  errno 2003 allowlisting, and `RuleExecutionError` propagation
- Return `[]` when `scan_context is None`

### Direct Cursor Rules (COST_043, CORTEX_001)
These rules use direct cursor commands (`SHOW GRANTS`, `SHOW CORTEX SEARCH SERVICES`)
that cannot be cached via `ScanContext`. They:
- Are not `_CortexRule` subclasses (COST_043 is a plain `Rule`)
- Handle errno 2003 via `is_allowlisted_sf_error()` per-function/service
- Still follow `RuleExecutionError` re-raise on unexpected errors

### Complexity Management
Complex `check_online` methods were refactored with private helper methods to stay
under the C901 complexity limit (≤ 11):
- `CortexSessionGrowthTrendCheck._build_month_credits()` and `_detect_consecutive_growth()`
- `CortexSearchServiceGovernanceCheck._check_public_grants()` and `_check_corpus_size()`
- `CortexFineTuningCostTrackingCheck._parse_fine_tune_activity()`
- `CortexServerlessAIBudgetGapCheck._sum_cortex_credits()` and `_budget_exists()`

## Test Coverage

- `test_cortex_cost_rules.py`: +6 test classes covering COST_041–044 (26 new tests)
- `test_cortex_governance_rules.py`: 7 test classes covering CORTEX_001–007 (38 tests)
- All rules have: `test_none_scan_context_returns_empty`, `test_view_unavailable_returns_empty`,
  threshold-crossed, threshold-not-crossed tests
- 1228 total tests pass, 86% coverage

## Scope Exclusions

- Cross-account Cortex federation visibility
- Automated remediation (revoking PUBLIC, deleting models)
- `SYSTEM$CLASSIFY`-based live content detection
- Directive E (IaC drift) — separate directive

## PR

`feat/directive-f-cortex-ai-governance` → `feat/directive-c-d-rbac-sensitive-data`
(base branch updated to `main` once PR 16 merges)
