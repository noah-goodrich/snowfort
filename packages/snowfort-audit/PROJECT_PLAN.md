# Directive B Part 2 — Warehouse Utilization & Sizing Rules

**Branch:** feat/warehouse-utilization-rules  
**Directive ref:** docs/plans/directives/warehouse-sizing.md  
**Depends on:** Directive B Part 1 (PERF_020, COST_036, COST_037 — merged)

---

## Objective

Implement five warehouse utilization and savings rules that complete the warehouse analysis
layer of Directive B. All five rules consume `ACCOUNT_USAGE` views, follow the `sizing.py`
scaffolding, and are registered in `rule_registry.py`.

---

## Acceptance Criteria

- [ ] **PERF_021** `QueryDurationAnomalyCheck` — flags warehouses where P95/P50 duration ratio
  exceeds the configured threshold (default 10×). Severity LOW, category ACTIONABLE.
- [ ] **PERF_022** `WorkloadIsolationCheck` — flags warehouses where both short-P50 hours
  (< 5 s) and long-P50 hours (> 60 s) appear within the lookback window. Severity MEDIUM,
  category ACTIONABLE.
- [ ] **PERF_023** `AutoSuspendOptimizationCheck` — flags warehouses where P75 inter-query gap
  is less than `auto_suspend` (recommend tightening) or greater than 10× `auto_suspend`
  (already aggressive). Severity LOW, category ACTIONABLE.
- [ ] **COST_034** `ConsolidationCandidatesCheck` — identifies warehouse pairs where combined
  P50 utilization < 60%. Severity MEDIUM, category ACTIONABLE.
- [ ] **COST_035** `SavingsProjectionCheck` — projects annual dollar savings for underutilized
  warehouses using `project_annual_savings()` from `workload_profile.py`. Severity
  INFORMATIONAL, category INFORMATIONAL.
- [ ] All 5 rules registered in `rule_registry.py`.
- [ ] `rules_snapshot.yaml` regenerated and includes new rule IDs.
- [ ] Each rule has ≥ 4 unit tests: basic violation, no-violation, conventions override,
  error→RuleExecutionError.
- [ ] `make check` passes (ruff, mypy, pylint, pytest).

## New Convention Fields

`WarehouseSizingThresholds` in `conventions.py`:

| Field | Default | Used by |
|---|---|---|
| `duration_anomaly_ratio` | `10.0` | PERF_021 |
| `auto_suspend_aggressive_ratio` | `10.0` | PERF_023 |
| `consolidation_combined_p50_max` | `0.60` | COST_034 |
| `credit_price_per_hour` | `3.0` | COST_035 |

## Test Plan

- [ ] `test_perf021_flags_anomalous_warehouse`
- [ ] `test_perf021_skips_normal_ratio`
- [ ] `test_perf021_threshold_override`
- [ ] `test_perf021_error_raises_rule_execution_error`
- [ ] `test_perf022_flags_mixed_workload`
- [ ] `test_perf022_skips_uniform_workload`
- [ ] `test_perf022_threshold_override`
- [ ] `test_perf022_error_raises_rule_execution_error`
- [ ] `test_perf023_flags_tighten_recommendation`
- [ ] `test_perf023_flags_already_aggressive`
- [ ] `test_perf023_skips_well_configured`
- [ ] `test_perf023_error_raises_rule_execution_error`
- [ ] `test_cost034_flags_consolidation_pair`
- [ ] `test_cost034_skips_high_utilization`
- [ ] `test_cost034_threshold_override`
- [ ] `test_cost034_error_raises_rule_execution_error`
- [ ] `test_cost035_flags_savings_opportunity`
- [ ] `test_cost035_skips_xsmall_no_downsize`
- [ ] `test_cost035_includes_dollar_amount`
- [ ] `test_cost035_threshold_override`
- [ ] `test_cost035_error_raises_rule_execution_error`
