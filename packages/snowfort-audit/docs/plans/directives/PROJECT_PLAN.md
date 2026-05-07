# Project Plan: Directive E — IaC Drift Detection + dbt Grant Analysis
*Established: 2026-05-01*

## Objective

Add 4 IaC drift detection and dbt grant analysis rules (OPS_015, OPS_016, GOV_025, GOV_026) in a
new `iac_drift.py` module, with configurable thresholds in conventions, server-side QUERY_HISTORY
aggregation via `get_or_fetch` cache, and shared helpers in `_iac.py`.

## Acceptance Criteria

- [ ] `iac_drift.py` contains 4 rule classes (OPS_015, OPS_016, GOV_025, GOV_026) following the
      `check_online` pattern with `scan_context` and cursor fallback
  - Verify: `grep 'class.*Check' iac_drift.py` → 4 classes
- [ ] `IacDriftThresholds` and `DbtGrantsThresholds` frozen dataclasses added to `conventions.py`,
      wired into `RuleThresholdConventions`
  - Verify: `grep 'IacDriftThresholds\|DbtGrantsThresholds' conventions.py`
- [ ] All 4 rules registered in `rule_registry.py` under a Directive E section
  - Verify: `grep 'OPS_015\|OPS_016\|GOV_025\|GOV_026' rule_registry.py` → 4 entries
- [ ] ≥5 unit tests per rule (≥20 total) in `test_iac_drift_rules.py` covering: no-violation,
      basic trigger, custom thresholds, allowlisted error, and edge cases
  - Verify: `python3 -m pytest tests/unit/test_iac_drift_rules.py -v --tb=short` → ≥20 pass
- [ ] `rules_snapshot.yaml` regenerated with OPS_015, OPS_016, GOV_025, GOV_026
  - Verify: `grep 'OPS_015\|OPS_016\|GOV_025\|GOV_026' rules_snapshot.yaml` → 4 entries
- [ ] `make check` passes (lint + mypy + tests + coverage threshold)
  - Verify: `make check` → all green
- [ ] Nothing-breaks regression: all existing 1228 tests continue to pass
  - Verify: included in `make check`

## Scope Boundaries

- NOT building: Interactive questionnaire mechanism (deferred — separate feature touching CLI,
  manifest schema, and Cortex Code integration)
- NOT building: Per-tool drift logic for SchemaChange/Pulumi beyond regex matching (configurable
  patterns cover them)
- NOT building: dbt project YAML parsing (GOV_025 uses QUERY_HISTORY comment patterns only in v1;
  path-based parsing is a follow-up)
- If done early: Ship, don't expand.

## Ship Definition

1. All acceptance criteria verified
2. PR opened → CI passes (make check)
3. Manual: run against test account with `--rule OPS_015 --rule OPS_016 --rule GOV_025 --rule GOV_026`
4. Merged

## Risks

- **QUERY_HISTORY volume:** Can be very large on production accounts. Mitigated by server-side
  aggregation with `REGEXP_LIKE` in SQL — never fetch raw query text to Python.
- **ACCESS_HISTORY privileges:** Requires elevated privileges. Mitigated by allowlisted error
  handling (degrade gracefully if unavailable).
- **Comment-pattern spoofability:** Query comment matching is trivially spoofable. Mitigated by
  ACTIONABLE category (not CRITICAL) and explicit heuristic disclaimer in finding messages.

## The Collective Review Summary

- **Scope Hawk:** Drop questionnaire from scope. Focus on 4 rules. Terraform/MANAGED_BY and dbt
  are the primary detection paths; other tools configurable via regex.
- **Craftsperson:** Need `_iac.py` helper with QUERY_HISTORY fetcher. Parametrized per-tool drift
  tests are where bugs hide.
- **Performance Engineer:** Server-side aggregation mandatory. `get_or_fetch` with `window_days=30`
  separates from grants cache.
- **Security Auditor:** Findings must be ACTIONABLE not CRITICAL. Graceful degradation when
  ACCESS_HISTORY is unavailable.
- **Adult:** Ship 4 rules, defer questionnaire, aggregate server-side.
