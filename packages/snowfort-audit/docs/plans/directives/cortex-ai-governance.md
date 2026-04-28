# Directive F: Cortex AI Governance

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** The fastest-growing and least-governed cost surface in Snowflake.
Cortex AI features (Complete, Search, Analyst, Intelligence, Agents, fine-tuning)
can generate significant credit consumption with no built-in spend controls beyond
account-level budgets.

---

## Objective

Add governance rules for Cortex AI feature usage: cost monitoring, access control
validation, model routing optimization, and consumption trend analysis. Catch
uncontrolled AI spend before it becomes a budget surprise.

## Scope

### Cost Governance

**Note:** 18 Cortex cost rules already exist in `cortex_cost.py` (COST_016 through
COST_033), covering per-service budgets, per-user spend, model allowlists, query tag
coverage, zombie usage, and credit spikes. The rules below are **net-new** — they
address gaps not covered by existing rules. See the existing inventory:
- D1 AI Functions: COST_016–020 (budget, allowlist, tag coverage, per-user, adoption)
- D2 Code CLI: COST_021–023 (per-user limit, zombie, credit spike)
- D3 Agents: COST_024–026 (budget, spend cap, tag coverage)
- D4 Intelligence: COST_027–028 (daily spend, governance)
- D5 Search: COST_029–030 (consumption, zombie service)
- D6 Analyst: COST_031–032 (per-user quota, budget)
- D7 Document Processing: COST_033

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| COST_041 | Cortex Auto Model Routing | Flag accounts using explicit large model calls (e.g., `llama3.1-405b`) where `AUTO` routing would suffice. Large models cost 3-10x more per token. Check `QUERY_HISTORY` for `CORTEX.COMPLETE()` calls with explicit model parameter. Not covered by COST_017 (allowlist) which only validates approved models, not cost-optimal routing. | MEDIUM |
| COST_042 | Cortex Power User Concentration | Flag if >80% of Cortex credit consumption comes from <3 users. Concentration risk — one user's experiment can blow the budget. Not covered by COST_019 (per-user spend) which checks individual limits, not distribution shape. | MEDIUM |
| COST_043 | Cortex PUBLIC Access | Flag Cortex functions (COMPLETE, SEARCH, etc.) callable by PUBLIC role. AI functions should have explicit role-based access control. No existing rule checks function-level access grants for Cortex. | HIGH |
| COST_044 | Cortex Session Growth Trend | Flag if Cortex credit consumption is growing >50% month-over-month for 2+ consecutive months. Early warning for runaway adoption. Not covered by COST_023 (Code CLI spike) which is single-service and single-period. | LOW |

### Feature-Specific Governance

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| CORTEX_001 | Search Service Governance | Flag Cortex Search services with no access control (PUBLIC), no refresh schedule, or corpus >10GB without cost justification tag. | MEDIUM |
| CORTEX_002 | Analyst Semantic Model Audit | Detect Cortex Analyst semantic models. Flag models with >50 verified queries/day (cost concentration), PUBLIC access, or models not updated in 90+ days (stale). | MEDIUM |
| CORTEX_003 | Agent Governance | Detect Cortex Agents. Flag agents with external tool access, no budget constraint, PUBLIC access, or >1000 sessions/day. | HIGH |
| CORTEX_004 | Intelligence Governance | Detect Snowflake Intelligence instances. Flag instances with PUBLIC access or daily credit consumption above threshold (configurable, default 50 credits). | MEDIUM |
| CORTEX_005 | Fine-Tuning Cost Tracking | Detect fine-tuning jobs. Flag completed jobs with no subsequent model usage (wasted training spend). Flag running jobs exceeding cost threshold. | MEDIUM |
| CORTEX_006 | LLM Function Sprawl | Count distinct Cortex function types in use (COMPLETE, EXTRACT, CLASSIFY, SUMMARIZE, TRANSLATE, SENTIMENT, EMBED). Flag if >5 function types with no governance tag on consuming objects. Sprawl without visibility. | LOW |
| CORTEX_007 | Serverless AI Budget Gap | Flag accounts with Cortex AI usage but no serverless compute budget or resource monitor covering AI consumption. | HIGH |

### Conventions

```toml
[tool.snowfort.thresholds.cortex]
daily_credit_hard_limit = 100.0
daily_credit_soft_limit = 50.0
# Empty tuple = any model acceptable. Populate to restrict.
model_allowlist_expected = []
analyst_max_requests_per_user_per_day = 1000
snowflake_intelligence_max_daily_credits = 50.0
# New fields for expanded governance
power_user_concentration_threshold = 0.80
power_user_min_users = 3
growth_rate_threshold = 0.50          # 50% month-over-month
growth_consecutive_months = 2
fine_tuning_unused_days = 30          # Days after training with no inference
agent_max_daily_sessions = 1000
search_corpus_size_threshold_gb = 10
function_sprawl_threshold = 5
```

### Data Sources

| View / Command | Purpose |
|----------------|---------|
| `ACCOUNT_USAGE.QUERY_HISTORY` | Cortex function calls, model parameters, user attribution |
| `ACCOUNT_USAGE.METERING_DAILY_HISTORY` | Credit consumption by service type |
| `ACCOUNT_USAGE.CORTEX_USAGE_HISTORY` (if available) | Detailed Cortex-specific usage |
| `SHOW CORTEX SEARCH SERVICES` | Search service inventory |
| `SHOW CORTEX ANALYST SEMANTIC MODELS` (if available) | Analyst model inventory |
| `INFORMATION_SCHEMA.APPLICABLE_ROLES` | Access control validation |

## Key Design Decisions

1. **Use existing `CortexThresholds` convention block.** Project A's foundation
   already has `CortexThresholds` in `conventions.py` with `daily_credit_hard_limit`,
   `daily_credit_soft_limit`, `model_allowlist_expected`,
   `analyst_max_requests_per_user_per_day`, and
   `snowflake_intelligence_max_daily_credits`. Extend this block with new fields
   rather than creating a separate convention.

2. **COST_0xx for cost rules, CORTEX_0xx for feature governance.** Cost rules
   (COST_041-044) go in the Cost pillar. Feature-specific governance rules
   (CORTEX_001-007) go in the Governance pillar. This keeps pillar scoring
   meaningful.

3. **Graceful degradation for unavailable views.** Not all accounts have
   `CORTEX_USAGE_HISTORY` or Cortex features enabled. Rules must check for view
   existence via `is_allowlisted_sf_error()` and return `[]` (no violations)
   if the feature isn't in use — not ERRORED.

4. **Model routing recommendation is INFORMATIONAL.** COST_041 doesn't know if the
   user needs the large model for quality reasons. It flags the opportunity;
   `category=INFORMATIONAL` lets the user decide.

5. **PUBLIC access to AI functions is HIGH, not CRITICAL.** Unlike PUBLIC grants
   on data tables, PUBLIC access to AI functions is a cost and safety risk, not
   a data breach risk. HIGH is appropriate.

## TDD Requirements

Every rule requires:
1. Unit test with mock `QUERY_HISTORY` / metering data asserting correct detection
2. Unit test: feature not in use (view doesn't exist) → no violations, no error
3. Unit test: configurable thresholds from conventions
4. Unit test: correct pillar assignment (COST_0xx → Cost, CORTEX_0xx → Governance)

COST_041 additionally requires:
5. Unit test: `CORTEX.COMPLETE('auto', ...)` calls → no violation
6. Unit test: `CORTEX.COMPLETE('llama3.1-405b', ...)` calls → INFORMATIONAL finding

COST_042 additionally requires:
7. Unit test: 3 users each with 33% consumption → no violation
8. Unit test: 1 user with 90% consumption → violation

CORTEX_003 additionally requires:
9. Unit test: agent with external tool access → HIGH violation
10. Unit test: agent with PUBLIC access → HIGH violation

## Ship Definition

1. PR with all COST_041-044 and CORTEX_001-007 rules
2. `make check` passes
3. Rules gracefully degrade on accounts without Cortex features
4. Manual: run against account with known Cortex usage, verify credit attribution

## Risks

| Risk | Mitigation |
|------|------------|
| Cortex feature set evolves rapidly; new services may appear | Design rules around `QUERY_HISTORY` patterns, not specific SHOW commands; new features can be added as individual rules |
| `CORTEX_USAGE_HISTORY` may not exist on all editions | Graceful degradation to `METERING_DAILY_HISTORY` + `QUERY_HISTORY` |
| Model names change (e.g., `mistral-large` → `mistral-large2`) | Model detection uses configurable patterns, not exact strings |
| Cortex Agents / Intelligence are preview features | Check feature availability via `is_allowlisted_sf_error()`; skip if unavailable |
| Credit attribution for serverless features is imprecise | Use best available data; note precision limitations in finding context |
