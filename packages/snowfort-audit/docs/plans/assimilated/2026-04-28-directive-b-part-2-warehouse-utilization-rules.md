# Directive B Part 2 — Warehouse Utilization & Sizing Rules

**Branch:** feat/warehouse-utilization-rules
**Directive ref:** docs/plans/directives/warehouse-sizing.md
**Depends on:** Directive B Part 1 (PERF_020, COST_036, COST_037 — merged)
*Shipped: 2026-04-28 — PR #9 merged to main*

---

## Objective

Implement five warehouse utilization and savings rules that complete the warehouse analysis
layer of Directive B. All five rules consume `ACCOUNT_USAGE` views, follow the `sizing.py`
scaffolding, and are registered in `rule_registry.py`.

---

## Acceptance Criteria

- [x] **PERF_021** `QueryDurationAnomalyCheck` — flags warehouses where P95/P50 duration ratio
  exceeds the configured threshold (default 10×). Severity LOW, category ACTIONABLE.
- [x] **PERF_022** `WorkloadIsolationCheck` — flags warehouses where both short-P50 hours
  (< 5 s) and long-P50 hours (> 60 s) appear within the lookback window. Severity MEDIUM,
  category ACTIONABLE.
- [x] **PERF_023** `AutoSuspendOptimizationCheck` — flags warehouses where P75 inter-query gap
  is less than `auto_suspend` (recommend tightening) or greater than 10× `auto_suspend`
  (already aggressive). Severity LOW, category ACTIONABLE.
- [x] **COST_034** `ConsolidationCandidatesCheck` — identifies warehouse pairs where combined
  P50 utilization < 60%. Severity MEDIUM, category ACTIONABLE.
- [x] **COST_035** `SavingsProjectionCheck` — projects annual dollar savings for underutilized
  warehouses using `project_annual_savings()` from `workload_profile.py`. Severity
  INFORMATIONAL, category INFORMATIONAL.
- [x] All 5 rules registered in `rule_registry.py`.
- [x] `rules_snapshot.yaml` regenerated and includes new rule IDs.
- [x] Each rule has ≥ 4 unit tests: basic violation, no-violation, conventions override,
  error→RuleExecutionError.
- [x] `make check` passes (ruff, mypy, pylint, pytest).

## New Convention Fields

`WarehouseSizingThresholds` in `conventions.py`:

| Field | Default | Used by |
|---|---|---|
| `duration_anomaly_ratio` | `10.0` | PERF_021 |
| `auto_suspend_aggressive_ratio` | `10.0` | PERF_023 |
| `consolidation_combined_p50_max` | `0.60` | COST_034 |
| `credit_price_per_hour` | `3.0` | COST_035 |

## Test Plan

- [x] `test_perf021_flags_anomalous_warehouse`
- [x] `test_perf021_skips_normal_ratio`
- [x] `test_perf021_threshold_override`
- [x] `test_perf021_error_raises_rule_execution_error`
- [x] `test_perf022_flags_mixed_workload`
- [x] `test_perf022_skips_uniform_workload`
- [x] `test_perf022_threshold_override`
- [x] `test_perf022_error_raises_rule_execution_error`
- [x] `test_perf023_flags_tighten_recommendation`
- [x] `test_perf023_flags_already_aggressive`
- [x] `test_perf023_skips_well_configured`
- [x] `test_perf023_error_raises_rule_execution_error`
- [x] `test_cost034_flags_consolidation_pair`
- [x] `test_cost034_skips_high_utilization`
- [x] `test_cost034_threshold_override`
- [x] `test_cost034_error_raises_rule_execution_error`
- [x] `test_cost035_flags_savings_opportunity`
- [x] `test_cost035_skips_xsmall_no_downsize`
- [x] `test_cost035_includes_dollar_amount`
- [x] `test_cost035_threshold_override`
- [x] `test_cost035_error_raises_rule_execution_error`

## Additional Work Shipped

- `_SIZE_ORDER` list and `_downsize_one()` helper added to `sizing.py` for reuse
- `itertools.combinations` + `workload_profile` imports added to `sizing.py`
- Note for Part 3: add inline comment to COST_034 SQL explaining the `/2.0`
  pre-filter condition (`# both warehouses must be < threshold/2 to form a valid pair`)
