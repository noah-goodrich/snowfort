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
||||||| 51256b2
# snowfort-audit v0.4.0 Implementation Plan

**Status:** PLANNING
**Date:** 2026-04-09
**Theme:** Production bug fixes + rule tuning + Cortex cost governance + Q1 2026 feature rules + deferred work cleanup
**Sessions:** 9 (1a, 1b, 2, 3, 4, 5, 6, 7, 8)
**New rules added:** ~33

---

## Context

The v0.1.0 production scan of the INCLOUDCOUNSEL account (reported in `/development/snowfort-audit-briefing.md` and `/development/snowfort-audit-report.yaml`) surfaced:

1. **A real SEC_001 under-count bug** — snowfort flagged 3 ACCOUNTADMIN grants; manual investigation found 7 (3 dormant bare-name accounts + 2 users who default to ACCOUNTADMIN despite permifrost declaring otherwise).
2. **Rule severity miscalibration** that inflated the score to 3/100 (F) when the real story was closer to D/C. v0.3.0 fixed the scoring formula; v0.4.0 must fix the *rule-level* severity and false-positive problems.
3. **Entire categories of missed coverage**: no rules for Cortex AI / Code / Agents / Intelligence cost governance — the "fastest-growing cost category with zero guardrails" per the briefing. No rules for Dynamic Tables, Data Sharing, Developer Sandbox Sprawl, Cross-Region Inference, or Permifrost drift.
4. **13 Q1 2026 Snowflake features** with no corresponding rules (7 of which are high-priority for v0.4.0).
5. **Performance bottlenecks** from today's smoke test: SEC_008 / SEC_008_USER / SEC_008_ROLE / GOV_001 all hit `ACCOUNT_USAGE.GRANTS_TO_ROLES` independently (~100s total). MFA blocks parallel workers entirely. The view-phase parallelization we built in v0.3.0 isn't exercised on accounts with zero user views.
6. **Deferred work** from `docs/DEFERRED_WORK.md` that has been waiting: Cortex Code Skill, persisted Cortex summary in YAML export, ScanContext column-name refactor (deferred from v0.3.0).

v0.4.0 closes all of it in one release. **Scope is locked** — no category may be cut. Simpler implementations are accepted, but not at the cost of code quality, reliability, stability, security, or correctness. Confirmed research (2026-04-09) shows all Cortex cost-governance SQL primitives exist and are GA, so the Cortex rule pack is fully feasible.

### Collective Review Outcomes (applied throughout)

Six adversarial personas reviewed the plan. Five hard conditions were adopted:

1. **`ERRORED` finding state + `RuleExecutionError`.** Rules may only swallow a specific allowlist of `SnowflakeProgrammingError` SQLSTATE codes (e.g., view-not-found). Everything else propagates and is reported as ERRORED. Lands in Session 1a before any new rule is written.
2. **A1 SEC_001 fix is a grant-graph reachability check**, not a two-query union. Recursive CTE over `GRANTS_TO_ROLES` starting from each user's roles, plus `GRANTS_TO_USERS` for direct grants. Fixture test with 3-level role nesting must pass.
3. **`ScanContext.get_or_fetch(view, window)`** generalized prefetch. C1 is implemented as a reusable mechanism, not a GRANTS-specific one-off, so Sessions 4–6 can hit the shared cache from day one.
4. **Snapshot test harness** against a fixture ACCOUNT_USAGE dataset lands in Session 1a before Session 3's ScanContext column-name refactor touches 15+ rule files.
5. **C1 savings claim measured in Session 8** via `--profile` on a realistic scan before it lands in release notes.

Decisions confirmed with user:
- **9 sessions** (Session 1 split into 1a infra + 1b production fixes).
- **Full grant-graph reachability** for A1.
- **Parameterized rule family** pattern for the 17 Cortex rules (boring plain function, no metaclasses).

---

## Scope Lock (what cannot be cut)

All six categories ship. Every item within categories A (production bugs), C (customer-reported perf), D (briefing gaps), and F (previously deferred) is mandatory. Categories B (tuning) and E (Q1 2026 features) have no items marked optional — all tuning fixes and all 7 Q1 feature rules ship.

| Category | Items | Count |
|----------|-------|-------|
| A — Production bugs | A1 SEC_001 grant reachability, A2 dropped-DB filter | 2 |
| B — Rule tuning | B1 COST_012 CDC exclude, B2 COST_001 threshold, B3 SEC_003 SSO-aware, B4 OPS_001 severity+exclude, B5 SEC_007 SSO-aware, B6 SEC_011 service+zombie excludes | 6 |
| C — Perf + architecture | C1 generalized prefetch, C2 keypair bootstrap+MFA detect, C3 column-name refactor, C4 warehouse sizing doc | 4 |
| D — Missed coverage rules | D1 Cortex AI (~5), D2 Cortex Code CLI (~3), D3 Cortex Agents (~3), D4 Snowflake Intelligence (~2), D5 Cortex Search (~2), D6 Cortex Analyst (~2), D7 Dynamic Tables (2), D8 Masking coverage (1), D9 Data Sharing (2), D10 Sandbox Sprawl (1), D11 Cross-Region Inference (1), D12 Permifrost drift (1) | ~25 |
| E — Q1 2026 feature gaps | E1 PAT, E2 AI_REDACT, E3 Authorization policies, E4 Trust Center extensions, E5 PrivateLink enforcement, E6 Iceberg governance, E7 SPCS security | 7 |
| F — Deferred work | F1 Cortex Code Skill (SKILL.md), F2 Cortex summary in YAML | 2 |

---

## Rule ID Allocation

Next free IDs reserved per session to avoid collisions:

- **SEC**: SEC_012 – SEC_018 (Session 6 Q1 features)
- **COST**: COST_016 – COST_033 (Session 4 Cortex cost pack)
- **OPS**: OPS_010, OPS_011 (Session 5)
- **GOV**: GOV_005 (Session 6 Iceberg), GOV_006, GOV_007, GOV_008, GOV_009 (Session 5)
- **REL**: REL_010, REL_011 (Session 5 Dynamic Tables)

---

## Session 1a — Foundation Infrastructure (no new rules)

**Goal:** Land every piece of infrastructure that Sessions 1b–8 depend on. No rule work.

### Deliverables
1. **`RuleThresholdConventions`** frozen dataclass added to `src/snowfort_audit/domain/conventions.py` with nested blocks: `warehouse_auto_suspend`, `zombie_user_days`, `high_churn` (rows_per_day_threshold, exclude_name_patterns), `mandatory_tagging` (exclude_warehouse_patterns default `("COMPUTE_SERVICE_WH_*",)`), `network_perimeter` (sso_downgrade_bool), `cortex` block with per-feature thresholds.
2. **`[tool.snowfort.conventions.thresholds]`** support in `src/snowfort_audit/infrastructure/config_loader.py` — extend `load_conventions` to recursively merge the new nested block.
3. **`RuleExecutionError` exception** and **`ERRORED` finding state** — new `FindingStatus` enum in `src/snowfort_audit/domain/rule_definitions.py`. Every rule either: returns violations, returns `[]` (silent-pass), or raises `RuleExecutionError` (becomes ERRORED finding). A narrow SQLSTATE allowlist (object-not-found on views that may legitimately not exist in older accounts) may return `[]`; everything else propagates.
4. **`ScanContext.get_or_fetch(view, window)`** generalized prefetch helper. Shared cache keyed by (view, time_window). Session 1b wires GRANTS into it; Sessions 4–6 wire Cortex views into it.
5. **`ParameterizedRuleFamily`** helper — a plain function that returns `Rule` dataclass instances, called N times per feature family. **No metaclasses, no decorators that hide control flow.** Used by Session 4 (Cortex pack) and Session 6 (E3/E4/E5 policy-presence family).
6. **Snapshot test harness** — `tests/unit/test_rules_snapshot.py` runs every existing rule against a fixture `ScanContext` constructed from captured `ACCOUNT_USAGE` data and asserts finding output matches a committed snapshot. Session 3's column-name refactor depends on this.
7. **Rule authoring checklist** — `docs/directives/RULE_AUTHORING_CHECKLIST.md`: docstring citing briefing section, thresholds as named constants with rationale comments, full-sentence `remediation`, sensitive-output review (no tokens / policy bodies / PII in `details`).
8. **Sensitive-output lint** — simple regex-based pre-commit check that scans new rule files for suspicious substrings in violation messages (`token`, `password`, `secret`, `pem`, raw bytes).

### Files modified / created
- `src/snowfort_audit/domain/conventions.py` (extend)
- `src/snowfort_audit/domain/scan_context.py` (add `get_or_fetch`)
- `src/snowfort_audit/domain/rule_definitions.py` (add `RuleExecutionError`, `FindingStatus`)
- `src/snowfort_audit/infrastructure/config_loader.py` (extend)
- `src/snowfort_audit/domain/rule_family.py` (NEW — `ParameterizedRuleFamily` helper)
- `tests/unit/test_conventions_thresholds.py` (NEW)
- `tests/unit/test_scan_context_prefetch.py` (NEW)
- `tests/unit/test_rules_snapshot.py` (NEW — harness + initial snapshot)
- `tests/unit/fixtures/account_usage_fixture.py` (NEW — captured fixture data)
- `docs/directives/RULE_AUTHORING_CHECKLIST.md` (NEW)
- `scripts/check_sensitive_outputs.py` (NEW)

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] `RuleThresholdConventions` default values load; pyproject.toml override tests pass.
- [ ] `RuleExecutionError` propagates correctly; SQLSTATE allowlist test passes.
- [ ] `ScanContext.get_or_fetch` memoizes a single fetch for repeated calls.
- [ ] Snapshot harness captures all existing rules without change; committed snapshot is authoritative.
- [ ] Sensitive-output lint script runs cleanly against current rule files.

---

## Session 1b — A1 + A2 + GRANTS prefetch integration

**Goal:** Close the SEC_001 production bug with a full grant-graph reachability check, wire GRANTS into the new generalized prefetch, and fix the DDL fetch noise from dropped databases.

### Deliverables
1. **A1 SEC_001 reachability fix.** Rewrite `AdminExposureCheck.check_online` in `src/snowfort_audit/domain/rules/security.py` to:
   - Use a recursive CTE over `SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES` starting from each user's default + secondary roles.
   - Union direct grants from `SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS`.
   - Report any user who can reach `ACCOUNTADMIN`, `SECURITYADMIN`, or `SYSADMIN` via any path.
   - Fixture test: user A has direct ACCOUNTADMIN grant; user B has role R1→R2→ACCOUNTADMIN chain; user C has role R3 whose default_role defaults to ACCOUNTADMIN via SCIM. Expected count: 3 (not 1).
2. **GRANTS prefetch** into the new `ScanContext.get_or_fetch` cache. Refactor SEC_007_ROLE, SEC_007_USER, SEC_008, SEC_008_USER, SEC_008_ROLE, SEC_011, GOV_001 to consume the cached grants instead of re-querying.
3. **A2 dropped-database filter.** Extend `_fetch_batch_ddl` in `src/snowfort_audit/use_cases/online_scan.py` to first fetch `SELECT DATABASE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE DELETED IS NULL` and filter the VIEWS query to active databases only. Do the same in `_run_view_phase_fallback`.

### Files modified / created
- `src/snowfort_audit/domain/rules/security.py` (rewrite AdminExposureCheck, refactor SEC_007/008/011)
- `src/snowfort_audit/domain/rules/governance.py` (refactor GOV_001)
- `src/snowfort_audit/use_cases/online_scan.py` (GRANTS prefetch wiring + A2 filter)
- `tests/unit/test_security_rules_full.py` (new A1 regression fixture with 3-level nesting)
- `tests/unit/test_online_scan_use_case.py` (A2 dropped-database filter test)

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] A1 regression test passes: 3-level role chain detected.
- [ ] GRANTS_TO_ROLES and GRANTS_TO_USERS queries execute exactly once across all rules (measured by telemetry counter).
- [ ] `_fetch_batch_ddl` filters out views whose database is in `DELETED IS NOT NULL`; test with fixture containing a dropped `DBT_FAKE__X` database.

---

## Session 2 — Rule tuning B1–B6 (six separate commits)

**Goal:** Calibrate severity and false-positive rates for the six rules flagged in the adversarial review. Each tuning fix lands as its own commit with a before/after finding-count note in the commit body.

### Deliverables (one commit each)
- **B1** — `HighChurnPermanentTableCheck` (COST_012): accept `conventions.thresholds.high_churn.exclude_name_patterns`, default `()` but can be set to exclude CDC staging patterns via pyproject.toml.
- **B2** — `AggressiveAutoSuspendCheck` (COST_001): change convention default from 1s to 30s; also flag `auto_suspend > max_seconds` (default 3600s) as MEDIUM.
- **B3** — `NetworkPerimeterCheck` (SEC_003): consume new `scan_context.sso_enforced` flag; downgrade severity from HIGH to LOW when SSO is detected.
- **B4** — `MandatoryTaggingCheck` (OPS_001): severity CRITICAL → MEDIUM; exclude warehouses matching `conventions.thresholds.mandatory_tagging.exclude_warehouse_patterns`.
- **B5** — `ZombieUserCheck` (SEC_007): same SSO-aware downgrade as B3.
- **B6** — `FederatedAuthenticationCheck` (SEC_011): exclude `TYPE='SERVICE'` users; exclude users already in `scan_context.zombie_user_logins`.

### Supporting work
- `src/snowfort_audit/domain/scan_context.py` — add `sso_enforced: bool | None` and `zombie_user_logins: frozenset[str] | None`.
- `src/snowfort_audit/use_cases/online_scan.py` `_prefetch` — detect SSO via `SHOW SECURITY INTEGRATIONS` + user `EXT_AUTHN_UID` populated rate; compute `zombie_user_logins` from `SHOW USERS` last-login fields.
- `src/snowfort_audit/infrastructure/rule_registry.py` — inject `conventions` into the six tuned rules.

### Files modified
- `src/snowfort_audit/domain/rules/cost.py` (B1, B2)
- `src/snowfort_audit/domain/rules/security.py` (B3, B5, B6)
- `src/snowfort_audit/domain/rules/op_excellence.py` (B4)
- `src/snowfort_audit/domain/scan_context.py`
- `src/snowfort_audit/use_cases/online_scan.py`
- `src/snowfort_audit/infrastructure/rule_registry.py`
- `tests/unit/test_cost_rules_full.py`, `tests/unit/test_security_rules_full.py`, `tests/unit/test_perf_gov_infra.py`

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] 6 commits, each with scan-diff commentary in body.
- [ ] `test_high_churn_exclusions` passes with a CDC staging name.
- [ ] `test_aggressive_auto_suspend` asserts both too-low (<30s) and too-high (>3600s) flavors.
- [ ] `test_network_perimeter_sso_downgrade` asserts severity LOW when `sso_enforced=True`.
- [ ] `test_mandatory_tagging_severity_and_exclusion` asserts MEDIUM severity and COMPUTE_SERVICE_WH exclusion.
- [ ] `test_zombie_user_sso_downgrade` asserts lower severity under SSO.
- [ ] `test_federated_auth_excludes_service_and_zombies` asserts service users and zombies are skipped.

---

## Session 3 — C2 keypair bootstrap + C3 column-name refactor + C4 docs

**Goal:** Land the previously-deferred ScanContext column-name refactor (protected by the snapshot harness from Session 1a), ship the keypair auth bootstrap to unblock MFA-constrained users, and publish the warehouse sizing guide.

### Deliverables
1. **C3 ScanContext column-name refactor.** Add helper `ScanContext.col(row, attr, name)` that uses the existing `*_cols` dicts. Refactor all 15+ rule files that currently use magic tuple indices (`row[0]`, `row[8]`) to use the helper. Pure mechanical refactor; snapshot harness from Session 1a verifies zero behavioral change.
2. **C2 Keypair auth bootstrap.**
   - New CLI subcommand: `snowfort audit bootstrap --keypair [--dry-run]`.
   - Generates RSA keypair, writes private key with mode `0600` to user-controlled path (never `/tmp`).
   - Refuses to use existing key files with group or world read permissions.
   - Prints `ALTER USER` SQL for the user to execute manually.
   - `snowfort audit scan` detects MFA at startup; if detected, emits telemetry warning with remediation: "Use keypair auth for parallel scans. Run: snowfort audit bootstrap --keypair".
   - Never logs MFA type at INFO level (fingerprinting leak).
3. **C4 Warehouse sizing documentation.** `docs/WAREHOUSE_SIZING.md` with a workload → recommended size matrix. Link from README.

### Files modified / created
- `src/snowfort_audit/domain/scan_context.py` (add `col()` helper)
- All 15+ files under `src/snowfort_audit/domain/rules/` (mechanical refactor)
- `src/snowfort_audit/infrastructure/gateways/keypair_bootstrap.py` (NEW)
- `src/snowfort_audit/interface/cli/bootstrap.py` (new `--keypair` flag)
- `src/snowfort_audit/use_cases/bootstrap.py` (orchestrator)
- `src/snowfort_audit/use_cases/online_scan.py` (MFA detection + warning)
- `docs/WAREHOUSE_SIZING.md` (NEW)
- `README.md` (link + keypair setup note)
- `tests/unit/test_keypair_bootstrap.py` (NEW)
- `tests/unit/test_scan_context_col_helper.py` (NEW)

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] Snapshot harness reports zero deltas from the refactor.
- [ ] `snowfort audit bootstrap --keypair --dry-run` prints ALTER USER SQL without touching the account.
- [ ] Keypair file-mode check: refuses to use a `0644` key file; accepts a `0600` file.
- [ ] MFA detection emits warning without logging MFA type at INFO.
- [ ] `docs/WAREHOUSE_SIZING.md` exists and is linked from README.

---

## Session 4 — Cortex cost governance rule pack (D1–D6, ~17 rules) — COMPLETED

**Goal:** Ship the Cortex cost governance rule pack as a `ParameterizedRuleFamily` — 17 rules generated by 6 feature-family function calls. Each rule produces a distinct finding so users see "Cortex Search has no budget" separately from "Cortex Analyst has no budget".

### Cortex prefetch
`_prefetch` gains one `get_or_fetch` call per Cortex view (wrapped in try/except per-view so one failure doesn't cascade; view-unavailable returns `[]` with ERRORED telemetry, not silent pass):

- `CORTEX_AI_FUNCTIONS_USAGE_HISTORY`
- `CORTEX_AISQL_USAGE_HISTORY`
- `CORTEX_CODE_CLI_USAGE_HISTORY`
- `CORTEX_CODE_SNOWSIGHT_USAGE_HISTORY`
- `CORTEX_AGENT_USAGE_HISTORY`
- `SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY`
- `CORTEX_ANALYST_USAGE_HISTORY`
- `CORTEX_SEARCH_DAILY_USAGE_HISTORY`
- `CORTEX_SEARCH_SERVING_USAGE_HISTORY`
- `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY`

Each uses `WHERE USAGE_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())` (adjusted per view's actual time column).

### Rule pack (17 total, COST_016 – COST_033)

**D1 — Cortex AI Functions (5 rules)**
- `COST_016` `CortexAIFunctionCreditBudgetCheck` — aggregate TOKEN_CREDITS/day, flag > `cortex.daily_credit_hard_limit`, warn > soft limit.
- `COST_017` `CortexAIFunctionModelAllowlistCheck` — any MODEL_NAME used that isn't in `cortex.model_allowlist_expected` flags.
- `COST_018` `CortexAIFunctionQueryTagCoverageCheck` — rows with `QUERY_TAG IS NULL` > 20% flags (chargeback hygiene).
- `COST_019` `CortexAIFunctionPerUserSpendCheck` — top-N users by credits; outlier = >3x median flags.
- `COST_020` `CortexAISQLAdoptionCheck` — flag continued use of deprecated `CORTEX_FUNCTIONS_USAGE_HISTORY` view.

**D2 — Cortex Code CLI (3 rules)**
- `COST_021` `CortexCodeCLIPerUserLimitCheck` — check `CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER` parameter set; flag users whose credits > 80% of limit for 3+ days.
- `COST_022` `CortexCodeCLIZombieUsageCheck` — users with zero CLI usage for 30d but still have `SNOWFLAKE.CORTEX_USER` role.
- `COST_023` `CortexCodeCLICreditSpikeCheck` — day-over-day >5x increase flags.

**D3 — Cortex Agents (3 rules)**
- `COST_024` `CortexAgentBudgetEnforcementCheck` — `SHOW BUDGETS LIKE 'AGENT_%'`; flag agents without budget.
- `COST_025` `CortexAgentSpendCapCheck` — aggregate by AGENT_NAME; flag > threshold.
- `COST_026` `CortexAgentTagCoverageCheck` — flag agents whose `AGENT_TAGS IS NULL`.

**D4 — Snowflake Intelligence (2 rules)**
- `COST_027` `SnowflakeIntelligenceDailySpendCheck` — aggregate per SNOWFLAKE_INTELLIGENCE_NAME; flag > `snowflake_intelligence_max_daily_credits`.
- `COST_028` `SnowflakeIntelligenceGovernanceCheck` — Intelligence running without cost-center tag attribution.

**D5 — Cortex Search (2 rules)**
- `COST_029` `CortexSearchConsumptionBreakdownCheck` — check SERVING / EMBED_TEXT_TOKENS / BATCH split; flag unexpected growth or cap breach.
- `COST_030` `CortexSearchZombieServiceCheck` — services with zero SERVING for 30d but still consuming BATCH refresh.

**D6 — Cortex Analyst (2 rules)**
- `COST_031` `CortexAnalystPerUserQuotaCheck` — flag users > `analyst_max_requests_per_user_per_day`.
- `COST_032` `CortexAnalystEnabledWithoutBudgetCheck` — `ENABLE_CORTEX_ANALYST = TRUE` with no account budget.

**Bonus** — `COST_033` `CortexDocumentProcessingSpendCheck` — aggregates `AI_PARSE_DOCUMENT` + `AI_EXTRACT` from `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY`.

### Files modified / created
- `src/snowfort_audit/domain/rules/cortex_cost.py` (NEW — all 18 rules + shared `CortexUsageRule` base)
- `src/snowfort_audit/domain/scan_context.py` (10 new Cortex fields + their `_cols`)
- `src/snowfort_audit/domain/conventions.py` (extend `RuleThresholdConventions` with `cortex` block)
- `src/snowfort_audit/use_cases/online_scan.py` (Cortex prefetch via `get_or_fetch`)
- `src/snowfort_audit/infrastructure/rule_registry.py` (register 18 rules)
- `tests/unit/test_cortex_cost_rules.py` (NEW — unit tests for every rule)
- `tests/unit/fixtures/cortex_usage_fixtures.py` (NEW — fake ScanContext constructors)
- `docs/RULES_CATALOG.md` (extend)

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] `cortex_cost.py` module coverage ≥ 90%.
- [x] Each rule has four test cases: `scan_context=None` → `[]`; view unavailable → `[]` with ERRORED telemetry; threshold crossed → violation; threshold not crossed → `[]`.
- [x] One Cortex view failing during prefetch does NOT block the others.
- [x] `snowfort audit rules` lists all 18 new rule IDs.
- [x] `ParameterizedRuleFamily` implementation is a plain function (no metaclasses) — code review enforcement.

---

## Session 5 — Remaining D rules (D7–D12, 8 rules)

**Goal:** Close the rest of the "What the Audit Missed" list from the briefing.

### Rules (8 total)

- `REL_010` `DynamicTableRefreshLagCheck` (D7) — query `ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY`; flag lag > target.
- `REL_011` `DynamicTableFailureDetectionCheck` (D7) — flag any `STATE='FAILED'` in last 24h.
- `GOV_006` `MaskingPolicyCoverageExtendedCheck` (D8) — extend GOV_004: for each AI_CLASSIFY-tagged sensitive column, check that a masking policy is attached.
- `GOV_007` `InboundShareRiskCheck` (D9) — `SHOW SHARES IN ACCOUNT`; flag inbound shares without owner tag / documentation.
- `GOV_008` `OutboundShareRiskCheck` (D9) — flag outbound shares without expiration, without per-consumer grants, without row-access policy.
- `GOV_009` `CrossRegionInferenceCheck` (D11) — check `SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT`; flag if enabled and data-residency tags present on tables.
- `OPS_010` `DeveloperSandboxSprawlCheck` (D10) — compare `ACCOUNT_USAGE.DATABASES WHERE DELETED IS NOT NULL` against retention; flag dropped DBs consuming Time Travel > 7 days.
- `OPS_011` `PermifrostDriftCheck` (D12, opt-in) — only runs if `--permifrost-spec PATH` CLI flag provided; diffs actual grants vs Permifrost YAML spec. Without the flag, rule returns `[]` with telemetry info.

### Files modified / created
- `src/snowfort_audit/domain/rules/reliability.py` (REL_010, REL_011)
- `src/snowfort_audit/domain/rules/governance.py` (GOV_006, GOV_007, GOV_008, GOV_009)
- `src/snowfort_audit/domain/rules/op_excellence.py` (OPS_010)
- `src/snowfort_audit/domain/rules/iac_drift.py` (NEW — OPS_011)
- `src/snowfort_audit/interface/cli/scan.py` (add `--permifrost-spec` flag)
- `src/snowfort_audit/infrastructure/rule_registry.py` (register 8 rules)
- `tests/unit/test_reliability_rules_full.py`, `tests/unit/test_governance_rules.py`, `tests/unit/test_ops_rules.py`, `tests/unit/test_permifrost_drift.py` (NEW)

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] Happy + unhappy path per rule.
- [ ] `OPS_011` without `--permifrost-spec` skipped cleanly; with the flag, diffs a fixture YAML.
- [ ] `demo_setup.sql` extended: dynamic table with intentional lag, a dropped `SNOWFORT_TEST_ZOMBIE_DB`, an iceberg table without catalog.

---

## Session 6 — Q1 2026 feature gap rules (E1–E7, 7 rules)

**Goal:** Close the Q1 2026 Snowflake feature coverage gap. E3/E4/E5 share a `PolicyPresenceRule` family via `ParameterizedRuleFamily`.

### Rules (7 total)

- `SEC_012` `ProgrammaticAccessTokenCheck` (E1, HIGH) — query `SNOWFLAKE.ACCOUNT_USAGE.PROGRAMMATIC_ACCESS_TOKENS`; flag tokens without expiration, >90d expiration, or no role scopes.
- `SEC_013` `AIRedactPolicyCoverageCheck` (E2, MEDIUM) — flag sensitive-tagged columns without any AI_REDACT masking policy.
- `SEC_014` `AuthorizationPolicyCheck` (E3, MEDIUM) — `SHOW AUTHORIZATION POLICIES`; flag warehouses/users/service accounts without attached policy. Uses `PolicyPresenceRule` family.
- `SEC_015` `TrustCenterExtensionsCheck` (E4, MEDIUM) — query `SNOWFLAKE.TRUST_CENTER.FINDINGS`; flag CIS scanner package disabled or non-zero HIGH-severity findings.
- `SEC_016` `PrivateLinkOnlyEnforcementCheck` (E5, MEDIUM) — check `SYSTEM$ALLOWLIST_PRIVATELINK()` and network policies.
- `SEC_017` `SnowparkContainerServicesSecurityCheck` (E7, MEDIUM) — `SHOW SERVICES IN ACCOUNT`; flag services without external-access restriction, without tag, without compute pool isolation.
- `GOV_005` `IcebergTableGovernanceCheck` (E6, MEDIUM) — `SNOWFLAKE.ACCOUNT_USAGE.ICEBERG_TABLES`; flag tables without explicit catalog, retention, or encryption.

### Note on SEC_016 collision
v0.3.0 does not use `SEC_016`; current codebase has `SEC_016 MFAAccountEnforcementCheck`. **Verify during Session 1a** that SEC_016 is either unused or this plan's allocation needs to shift. If collision, use SEC_018 for PrivateLink and renumber the rest.

### Files modified / created
- `src/snowfort_audit/domain/rules/security_advanced.py` (extend with SEC_012–017)
- `src/snowfort_audit/domain/rules/governance.py` (GOV_005)
- `src/snowfort_audit/infrastructure/rule_registry.py` (register 7 rules)
- `tests/unit/test_security_rules_full.py`, `tests/unit/test_governance_rules.py`
- `docs/RULES_CATALOG.md`

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] One unit test per rule (violation-yes + violation-no paths).
- [ ] Each rule degrades gracefully (ERRORED) when its target view/command is unavailable.
- [ ] `PolicyPresenceRule` family used for E3/E4/E5 is a plain function, no metaclasses.

---

## Session 7 — Deferred work F1/F2 + smoke test hardening + docs

**Goal:** Close the remaining deferred backlog and harden the smoke test for release.

### Deliverables
1. **F1 Cortex Code Skill.**
   - `.cortex/skills/snowfort-audit/SKILL.md` (NEW) — teaches Cortex Code to invoke `snowfort audit scan --manifest`, parse findings, generate remediation suggestions from `remediation_instruction`.
   - `docs/CORTEX_CODE_SKILL.md` (NEW) — long-form install guide and example prompts.
2. **F2 Cortex summary in YAML.**
   - Refactor `src/snowfort_audit/infrastructure/cortex_synthesizer.py` to return a structured `CortexSummary` with `tl_dr`, `top_risks`, `quick_wins`.
   - Add `cortex_summary: CortexSummary | None` field to `ScanResult`.
   - YAML export serializes it under a top-level `cortex_summary:` block.
3. **Smoke test hardening.**
   - Extend `src/snowfort_audit/resources/demo_setup.sql` with all new seed objects from Sessions 2, 4, 5, 6 (labeled by rule ID).
   - Extend `demo_teardown.sql` symmetrically.
   - `scripts/smoke_test.sh` — extend to assert expected new rule IDs appear in output YAML (grep-based).
   - `docs/SMOKE_TEST.md` (NEW) — which rules are smoke-covered vs unit-only (Cortex rules are unit-only because seeding real Cortex usage costs real credits).
4. **Docs catch-up.**
   - Regenerate `docs/RULES_CATALOG.md` from the rule registry.
   - Update `docs/DEFERRED_WORK.md` to mark F1/F2 as shipped.

### Files modified / created
- `.cortex/skills/snowfort-audit/SKILL.md` (NEW)
- `docs/CORTEX_CODE_SKILL.md` (NEW)
- `src/snowfort_audit/infrastructure/cortex_synthesizer.py` (extend)
- `src/snowfort_audit/domain/results.py` (add `cortex_summary` field)
- `src/snowfort_audit/use_cases/online_scan.py` (persist summary)
- `src/snowfort_audit/interface/cli/report.py` (YAML export)
- `src/snowfort_audit/resources/demo_setup.sql` (extend)
- `src/snowfort_audit/resources/demo_teardown.sql` (extend)
- `scripts/smoke_test.sh` (extend)
- `docs/SMOKE_TEST.md` (NEW)
- `docs/RULES_CATALOG.md` (regen)
- `docs/DEFERRED_WORK.md` (mark F1/F2 shipped)
- `tests/unit/test_cortex_summary_serialization.py` (NEW)

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80%.
- [ ] `snowfort audit scan --cortex -o report.yaml` produces YAML with `cortex_summary:` block.
- [ ] `SKILL.md` example commands resolve in `snowfort audit --help`.
- [ ] Smoke test run against seeded sandbox: every seeded rule ID appears in report.

---

## Session 8 — Release candidate, C1 savings validation, ship v0.4.0

**Goal:** Final profiling, honest validation of the C1 savings claim, release engineering.

### Activities
1. **Profiling pass.** Run `snowfort audit scan --profile` against the INCLOUDCOUNSEL-class sandbox. Measure:
   - GRANTS prefetch savings (target ~100s; report the real number).
   - Cortex prefetch per-view timing.
   - Any rule running > 60s gets a note.
2. **Update release notes** with the *measured* C1 savings number, not the estimate.
3. **Release engineering.**
   - `pyproject.toml` — bump version to `0.4.0`.
   - `CHANGELOG.md` — populate v0.4.0 section grouped by category.
   - `README.md` — update rule count, feature highlights, Cortex cost governance banner.
   - `docs/RULES_CATALOG.md` — final catalog.
4. **Final validation.**
   - Full `make check` green.
   - `pytest tests/functional` end-to-end login flow.
   - Final smoke test against sandbox.
   - Final Collective review for ship readiness.
5. **Git tag `v0.4.0`** and optional PyPI publish (with user authorization).

### Files modified
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `docs/RULES_CATALOG.md`

### Acceptance criteria
- [ ] `make check` green, coverage ≥ 80% across 110+ rules.
- [ ] Smoke test exits 0 with all new rules reported.
- [ ] Profile measurement committed to CHANGELOG.
- [ ] Tag `v0.4.0` created.
- [ ] Final rule count: v0.3.0 had 90 rules; v0.4.0 ships ~123 rules (33 new).

---

## Dependency Graph

```
Session 1a (foundation infra) ── required by ALL downstream sessions
    │
    ├── Session 1b (A1 + A2 + GRANTS prefetch integration)
    ├── Session 2 (B1–B6 rule tuning)
    ├── Session 3 (C2 + C3 + C4)
    │   └── Session 4 (D1–D6 Cortex pack) — benefits from C3 refactor
    │       └── Session 5 (D7–D12 remaining D rules)
    │           └── Session 6 (E1–E7 Q1 feature rules)
    │               └── Session 7 (F1/F2 + smoke + docs)
    │                   └── Session 8 (release)
```

Sessions 1b, 2, and 3 are independent of each other after 1a; can theoretically run in parallel if needed.

---

## Critical Files for Implementation

| File | Role | Primary sessions |
|------|------|------------------|
| `src/snowfort_audit/domain/conventions.py` | `RuleThresholdConventions` + `cortex` block | 1a, 4 |
| `src/snowfort_audit/domain/scan_context.py` | `get_or_fetch`, `col` helper, Cortex fields | 1a, 3, 4 |
| `src/snowfort_audit/domain/rule_definitions.py` | `RuleExecutionError`, `FindingStatus` | 1a |
| `src/snowfort_audit/domain/rule_family.py` | `ParameterizedRuleFamily` helper | 1a (new), 4, 6 |
| `src/snowfort_audit/use_cases/online_scan.py` | Prefetch orchestration + MFA detection + A2 filter | 1a, 1b, 2, 3, 4 |
| `src/snowfort_audit/infrastructure/rule_registry.py` | Register all new rules | 1b, 2, 4, 5, 6 |
| `src/snowfort_audit/domain/rules/security.py` | A1 fix + B3/B5/B6 tuning | 1b, 2 |
| `src/snowfort_audit/domain/rules/cortex_cost.py` (NEW) | 18 Cortex rules | 4 |
| `src/snowfort_audit/infrastructure/cortex_synthesizer.py` | Structured `CortexSummary` | 7 |
| `src/snowfort_audit/resources/demo_setup.sql` | Smoke seeds for new rules | 5, 6, 7 |
| `docs/directives/RULE_AUTHORING_CHECKLIST.md` (NEW) | Quality gate for all new rules | 1a |

---

## Verification (how to test end-to-end)

After each session:
- `cd /development/packages/snowfort-audit && make check` — lint + mypy + test + coverage ≥ 80%.
- `pytest tests/unit/ -v` — all unit tests pass.
- Snapshot harness (`pytest tests/unit/test_rules_snapshot.py`) — zero deltas from baseline except in deliberately-changed rules.

Final (Session 8):
- `pytest tests/functional -v` — end-to-end login flow and CLI.
- `./scripts/smoke_test.sh` — seeds sandbox, runs full scan with `--workers 4` and `--profile`, asserts new rule IDs present in output, teardown.
- `snowfort audit scan --profile` output reviewed; GRANTS prefetch measured; report in CHANGELOG.
- `snowfort audit rules | wc -l` — confirms ~123 rules registered.
- `python -m build` — wheel + sdist build cleanly.
