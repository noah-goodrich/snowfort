# Project Plan: Directive F — Cortex AI Governance
*Established: 2026-04-30*

## Objective

Add 11 Cortex AI governance rules (COST_041–044 + CORTEX_001–007) that detect cost
concentration, uncontrolled access, runaway growth, and ungoverned AI feature usage across
all Snowflake Cortex AI products. Rules follow the established `_CortexRule` base class
pattern, use `ScanContext.get_or_fetch()` caching, and gracefully degrade on preview-feature
views via `is_allowlisted_sf_error()`.

## Acceptance Criteria

- [ ] `make check` green — lint, mypy, coverage ≥ 80%.
  - Verify: `cd packages/snowfort-audit && PATH=".venv/bin:$PATH" make check`

- [ ] All 4 cost rules present in `cortex_cost.py` with correct IDs.
  - Verify: `grep '"COST_04[1-4]"' src/snowfort_audit/domain/rules/cortex_cost.py | wc -l` → 4

- [ ] All 7 governance rules present in `cortex_governance.py` with correct IDs.
  - Verify: `grep '"CORTEX_00[1-7]"' src/snowfort_audit/domain/rules/cortex_governance.py | wc -l` → 7

- [ ] 8 new `CortexThresholds` fields present with documented defaults.
  - Verify: `python -c "from snowfort_audit.domain.conventions import CortexThresholds; t = CortexThresholds(); print(t.power_user_concentration_threshold, t.function_sprawl_threshold)"` → `0.8 5`

- [ ] `rules_snapshot.yaml` regenerated — all 11 new IDs present.
  - Verify: `grep "COST_04[1-4]\|CORTEX_00[1-7]" tests/unit/fixtures/rules_snapshot.yaml | wc -l` → 11

- [ ] ≥5 unit tests per COST_041–044 in `test_cortex_cost_rules.py`.
  - Verify: `pytest tests/unit/test_cortex_cost_rules.py -v -k "Cost04" | grep PASSED | wc -l` → ≥20

- [ ] ≥5 unit tests per CORTEX_001–007 in `test_cortex_governance_rules.py`.
  - Verify: `pytest tests/unit/test_cortex_governance_rules.py -v | grep PASSED | wc -l` → ≥35

- [ ] Each new rule returns `[]` when `scan_context=None`.
  - Verify: covered by `test_none_scan_context_returns_empty` per rule

- [ ] All preview-feature rules return `[]` on errno 2003 (object not found).
  - Verify: `test_view_unavailable_returns_empty` per rule in governance test file

- [ ] `sensitive-outputs` lint passes (no unannoted `password`/`secret`/`token` in violation strings).
  - Verify: `python scripts/check_sensitive_outputs.py` → exit 0

## Rule Specifications

### COST_041 — Cortex Auto-Model Routing Recommendation
- **Severity**: INFORMATIONAL
- **Trigger**: Any query explicitly calling a large Cortex model (llama3.1-405b, mistral-large2,
  claude-3-5-sonnet) when usage volume is low enough that a smaller model would suffice.
- **View**: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY`
- **Action**: Flag users/queries using large models; recommend enabling `COMPLETE` auto-routing.

### COST_042 — Cortex Power User Concentration
- **Severity**: MEDIUM
- **Trigger**: Top `power_user_min_users` users account for more than
  `power_user_concentration_threshold` (default 80%) of total credits in the window.
- **View**: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY`
- **Action**: Identify concentrating users for quota review.

### COST_043 — Cortex Public Role Access
- **Severity**: HIGH
- **Trigger**: PUBLIC role has USAGE on any Cortex LLM function.
- **Data source**: Direct cursor — `SHOW GRANTS ON FUNCTION SNOWFLAKE.CORTEX.COMPLETE(...)` etc.
- **Action**: Flag each Cortex function accessible to PUBLIC.

### COST_044 — Cortex Session Growth Trend
- **Severity**: LOW
- **Trigger**: Month-over-month credit growth exceeds `growth_rate_threshold` (50%) for
  `growth_consecutive_months` (2+) consecutive months.
- **View**: `METERING_DAILY_HISTORY` (SNOWPARK_CONTAINER_SERVICES / CORTEX service_type)
- **Action**: Flag the growth trend for budget review.

### CORTEX_001 — Cortex Search Service Governance
- **Severity**: MEDIUM
- **Trigger**: Cortex Search service exists but lacks governing policies (row access, network rules)
  or has PUBLIC access.
- **Data source**: `SHOW CORTEX SEARCH SERVICES` + `GRANTS_TO_ROLES`
- **Graceful degrade**: Return `[]` on errno 2003 (preview feature not available).

### CORTEX_002 — Cortex Analyst Semantic Model Audit
- **Severity**: MEDIUM
- **Trigger**: Cortex Analyst queries detected in `QUERY_HISTORY` but no corresponding semantic
  model objects governed by RBAC (no tag or row policy on underlying tables).
- **View**: `QUERY_HISTORY` (filter: query_text ILIKE '%ANALYST%COMPLETE%')

### CORTEX_003 — Cortex Agent Governance
- **Severity**: HIGH
- **Trigger**: Cortex Agent sessions exceed `agent_max_daily_sessions` (1000) per day, OR agent
  roles have access to sensitive tables without row-access policies.
- **Views**: `QUERY_HISTORY` + `GRANTS_TO_ROLES`

### CORTEX_004 — Cortex Intelligence Governance
- **Severity**: MEDIUM
- **Trigger**: Cortex Intelligence features (Document AI, Classification) are used by roles without
  data governance tags on the underlying stage/table sources.
- **Views**: `METERING_DAILY_HISTORY` + `GRANTS_TO_ROLES`
- **Graceful degrade**: Return `[]` on errno 2003.

### CORTEX_005 — Cortex Fine-Tuning Cost Tracking
- **Severity**: MEDIUM
- **Trigger**: Fine-tuned models exist (fine-tune jobs in `QUERY_HISTORY`) but have not been
  used for inference in the last `fine_tuning_unused_days` (30) days — idle compute cost.
- **View**: `QUERY_HISTORY`

### CORTEX_006 — Cortex LLM Function Sprawl
- **Severity**: LOW
- **Trigger**: More than `function_sprawl_threshold` (5) distinct Cortex LLM function types
  (COMPLETE, SUMMARIZE, EXTRACT_ANSWER, TRANSLATE, SENTIMENT, CLASSIFY_TEXT, etc.) used
  by a single role in the window — indicates ungoverned experimentation.
- **View**: `QUERY_HISTORY`

### CORTEX_007 — Cortex Serverless AI Budget Gap
- **Severity**: HIGH
- **Trigger**: Cortex AI spend detected in `METERING_DAILY_HISTORY` but no budget object covers
  Cortex service types in `SNOWFLAKE.LOCAL.BUDGETS`.
- **Views**: `METERING_DAILY_HISTORY` + `SNOWFLAKE.LOCAL.BUDGETS`
- **Graceful degrade**: Return `[]` on errno 2003 (BUDGETS view may not exist in all editions).

## CortexThresholds Extensions

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

## Scope Boundaries

- NOT building: cross-account Cortex federation visibility
- NOT building: automated remediation (disabling functions, revoking PUBLIC role access)
- NOT building: `SYSTEM$CLASSIFY`-based live content detection
- NOT building: Directive E (IaC drift) — separate directive
- Preview-feature rules (CORTEX_001, 004, 007) must degrade gracefully — never error on
  unavailable views/commands

## New Files

| File | Description |
|------|-------------|
| `domain/rules/cortex_governance.py` | 7 governance rule classes + factory |
| `tests/unit/test_cortex_governance_rules.py` | ≥35 unit tests |

## Modified Files

| File | Change |
|------|--------|
| `domain/conventions.py` | +8 fields to `CortexThresholds` |
| `domain/rules/cortex_cost.py` | +4 rule classes (COST_041–044) + factory entries |
| `infrastructure/rule_registry.py` | +`get_cortex_governance_rules()` splat registration |
| `tests/unit/test_cortex_cost_rules.py` | +~20 tests for COST_041–044 |
| `tests/unit/fixtures/rules_snapshot.yaml` | Regenerated |

## Ship Definition

1. All acceptance criteria checked
2. `make check` passes clean
3. Snapshot regenerated and committed
4. Assimilated plan written to `docs/plans/assimilated/2026-04-30-directive-f-cortex-ai-governance.md`
5. PR open and linked to directive tracker

## Risks

- `SHOW CORTEX SEARCH SERVICES` is a preview command — wrapped in `is_allowlisted_sf_error()`
  with graceful `[]` return
- `CORTEX_007` depends on `SNOWFLAKE.LOCAL.BUDGETS` which may not exist in Standard/Business
  Critical without Budgets feature enabled — same errno 2003 guard
- `METERING_DAILY_HISTORY` `service_type` values for Cortex may differ across account editions;
  use `ILIKE '%CORTEX%'` rather than exact match
- COST_043 uses `SHOW GRANTS ON FUNCTION` (direct cursor, not `_CortexRule` cache path) —
  documented in code comment and covered by dedicated test
</content>
</invoke>