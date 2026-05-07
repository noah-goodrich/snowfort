# snowfort-audit v0.4.0 Implementation Plan

**Status:** SHIPPED
**Date:** 2026-04-09
**Theme:** Production bug fixes + rule tuning + Cortex cost governance + Q1 2026 feature rules + deferred work cleanup
**Sessions:** 9 (1a, 1b, 2, 3, 4, 5, 6, 7, 8)
**New rules added:** ~33

*Shipped: 2026-04-29 — v0.4.0 tagged (v0.4.1 patch followed)*

---

## Context

The v0.1.0 production scan of the INCLOUDCOUNSEL account (reported in `/development/snowfort-audit-briefing.md` and
`/development/snowfort-audit-report.yaml`) surfaced:

1. **A real SEC_001 under-count bug** — snowfort flagged 3 ACCOUNTADMIN grants; manual investigation found 7 (3 dormant
   bare-name accounts + 2 users who default to ACCOUNTADMIN despite permifrost declaring otherwise).
2. **Rule severity miscalibration** that inflated the score to 3/100 (F) when the real story was closer to D/C. v0.3.0
   fixed the scoring formula; v0.4.0 must fix the *rule-level* severity and false-positive problems.
3. **Entire categories of missed coverage**: no rules for Cortex AI / Code / Agents / Intelligence cost governance — the
   "fastest-growing cost category with zero guardrails" per the briefing. No rules for Dynamic Tables, Data Sharing,
   Developer Sandbox Sprawl, Cross-Region Inference, or Permifrost drift.
4. **13 Q1 2026 Snowflake features** with no corresponding rules (7 of which are high-priority for v0.4.0).
5. **Performance bottlenecks** from today's smoke test: SEC_008 / SEC_008_USER / SEC_008_ROLE / GOV_001 all hit
   `ACCOUNT_USAGE.GRANTS_TO_ROLES` independently (~100s total). MFA blocks parallel workers entirely. The view-phase
   parallelization we built in v0.3.0 isn't exercised on accounts with zero user views.
6. **Deferred work** from `docs/DEFERRED_WORK.md` that has been waiting: Cortex Code Skill, persisted Cortex summary
   in YAML export, ScanContext column-name refactor (deferred from v0.3.0).

v0.4.0 closes all of it in one release. **Scope is locked** — no category may be cut. Simpler implementations are
accepted, but not at the cost of code quality, reliability, stability, security, or correctness. Confirmed research
(2026-04-09) shows all Cortex cost-governance SQL primitives exist and are GA, so the Cortex rule pack is fully
feasible.

### Collective Review Outcomes (applied throughout)

Six adversarial personas reviewed the plan. Five hard conditions were adopted:

1. **`ERRORED` finding state + `RuleExecutionError`.** Rules may only swallow a specific allowlist of
   `SnowflakeProgrammingError` SQLSTATE codes (e.g., view-not-found). Everything else propagates and is reported as
   ERRORED. Lands in Session 1a before any new rule is written.
2. **A1 SEC_001 fix is a grant-graph reachability check**, not a two-query union. Recursive CTE over
   `GRANTS_TO_ROLES` starting from each user's roles, plus `GRANTS_TO_USERS` for direct grants. Fixture test with
   3-level role nesting must pass.
3. **`ScanContext.get_or_fetch(view, window)`** generalized prefetch. C1 is implemented as a reusable mechanism, not a
   GRANTS-specific one-off, so Sessions 4–6 can hit the shared cache from day one.
4. **Snapshot test harness** against a fixture ACCOUNT_USAGE dataset lands in Session 1a before Session 3's ScanContext
   column-name refactor touches 15+ rule files.
5. **C1 savings claim measured in Session 8** via `--profile` on a realistic scan before it lands in release notes.

Decisions confirmed with user:
- **9 sessions** (Session 1 split into 1a infra + 1b production fixes).
- **Full grant-graph reachability** for A1.
- **Parameterized rule family** pattern for the 17 Cortex rules (boring plain function, no metaclasses).

---

## Scope Lock (what cannot be cut)

All six categories ship. Every item within categories A (production bugs), C (customer-reported perf), D (briefing
gaps), and F (previously deferred) is mandatory. Categories B (tuning) and E (Q1 2026 features) have no items marked
optional — all tuning fixes and all 7 Q1 feature rules ship.

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

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] `RuleThresholdConventions` default values load; pyproject.toml override tests pass.
- [x] `RuleExecutionError` propagates correctly; SQLSTATE allowlist test passes.
- [x] `ScanContext.get_or_fetch` memoizes a single fetch for repeated calls.
- [x] Snapshot harness captures all existing rules without change; committed snapshot is authoritative.
- [x] Sensitive-output lint script runs cleanly against current rule files.

---

## Session 1b — A1 + A2 + GRANTS prefetch integration

**Goal:** Close the SEC_001 production bug with a full grant-graph reachability check, wire GRANTS into the new
generalized prefetch, and fix the DDL fetch noise from dropped databases.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] A1 regression test passes: 3-level role chain detected.
- [x] GRANTS_TO_ROLES and GRANTS_TO_USERS queries execute exactly once across all rules (measured by telemetry
  counter).
- [x] `_fetch_batch_ddl` filters out views whose database is in `DELETED IS NOT NULL`; test with fixture containing a
  dropped `DBT_FAKE__X` database.

---

## Session 2 — Rule tuning B1–B6 (six separate commits)

**Goal:** Calibrate severity and false-positive rates for the six rules flagged in the adversarial review.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] 6 commits, each with scan-diff commentary in body.
- [x] `test_high_churn_exclusions` passes with a CDC staging name.
- [x] `test_aggressive_auto_suspend` asserts both too-low (<30s) and too-high (>3600s) flavors.
- [x] `test_network_perimeter_sso_downgrade` asserts severity LOW when `sso_enforced=True`.
- [x] `test_mandatory_tagging_severity_and_exclusion` asserts MEDIUM severity and COMPUTE_SERVICE_WH exclusion.
- [x] `test_zombie_user_sso_downgrade` asserts lower severity under SSO.
- [x] `test_federated_auth_excludes_service_and_zombies` asserts service users and zombies are skipped.

---

## Session 3 — C2 keypair bootstrap + C3 column-name refactor + C4 docs

**Goal:** Land the previously-deferred ScanContext column-name refactor, ship the keypair auth bootstrap, and publish
the warehouse sizing guide.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] Snapshot harness reports zero deltas from the refactor.
- [x] `snowfort audit bootstrap --keypair --dry-run` prints ALTER USER SQL without touching the account.
- [x] Keypair file-mode check: refuses to use a `0644` key file; accepts a `0600` file.
- [x] MFA detection emits warning without logging MFA type at INFO.
- [x] `docs/WAREHOUSE_SIZING.md` exists and is linked from README.

---

## Session 4 — Cortex cost governance rule pack (D1–D6, ~17 rules) — COMPLETED

**Goal:** Ship the Cortex cost governance rule pack as a `ParameterizedRuleFamily`.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] `cortex_cost.py` module coverage ≥ 90%.
- [x] Each rule has four test cases: `scan_context=None` → `[]`; view unavailable → `[]` with ERRORED telemetry;
  threshold crossed → violation; threshold not crossed → `[]`.
- [x] One Cortex view failing during prefetch does NOT block the others.
- [x] `snowfort audit rules` lists all 18 new rule IDs.
- [x] `ParameterizedRuleFamily` implementation is a plain function (no metaclasses) — code review enforcement.

---

## Session 5 — Remaining D rules (D7–D12, 8 rules)

**Goal:** Close the rest of the "What the Audit Missed" list from the briefing.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] Happy + unhappy path per rule.
- [x] `OPS_011` without `--permifrost-spec` skipped cleanly; with the flag, diffs a fixture YAML.
- [x] `demo_setup.sql` extended: dynamic table with intentional lag, a dropped `SNOWFORT_TEST_ZOMBIE_DB`, an iceberg
  table without catalog.

---

## Session 6 — Q1 2026 feature gap rules (E1–E7, 7 rules)

**Goal:** Close the Q1 2026 Snowflake feature coverage gap.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] One unit test per rule (violation-yes + violation-no paths).
- [x] Each rule degrades gracefully (ERRORED) when its target view/command is unavailable.
- [x] `PolicyPresenceRule` family used for E3/E4/E5 is a plain function, no metaclasses.

---

## Session 7 — Deferred work F1/F2 + smoke test hardening + docs

**Goal:** Close the remaining deferred backlog and harden the smoke test for release.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80%.
- [x] `snowfort audit scan --cortex -o report.yaml` produces YAML with `cortex_summary:` block.
- [x] `SKILL.md` example commands resolve in `snowfort audit --help`.
- [x] Smoke test run against seeded sandbox: every seeded rule ID appears in report.

---

## Session 8 — Release candidate, C1 savings validation, ship v0.4.0

**Goal:** Final profiling, honest validation of the C1 savings claim, release engineering.

### Acceptance criteria
- [x] `make check` green, coverage ≥ 80% across 110+ rules.
- [x] Smoke test exits 0 with all new rules reported.
- [x] Profile measurement committed to CHANGELOG.
- [x] Tag `v0.4.0` created.
- [x] Final rule count: v0.3.0 had 90 rules; v0.4.0 ships 116 rules (26 new in v0.4.0; 10 more added in Directive C
  post-tag, total 126+).

---

## Additional Work Shipped (beyond plan scope)

**Directive C — RBAC Topology & Role Hierarchy** (shipped 2026-04-29, post v0.4.0 tag):

Decomposed monolithic SEC_001 into four targeted sub-rules and added god-role detection, privilege concentration
analysis, and role hierarchy validation. 10 new rules, 78 unit tests.

| Rule | Name |
|------|------|
| SEC_001a | AdminGrantCountCheck |
| SEC_001b | DormantAdminAccountsCheck |
| SEC_001c | AdminAsDefaultRoleCheck |
| SEC_001d | LegacyIdentityDuplicationCheck |
| SEC_024 | OrphanRoleRatioCheck |
| SEC_025 | GodRoleDetectionCheck |
| SEC_026 | PrivilegeConcentrationCheck |
| SEC_027 | RoleFlowValidationCheck |
| SEC_028 | UserRoleExplosionCheck |
| SEC_029 | IncompleteDepartmentRolesCheck |

SEC_004 (PublicGrantsCheck) also enhanced to distinguish warehouse USAGE grants (LOW/EXPECTED) from data object grants
(HIGH/ACTIONABLE).

Tracked in: `docs/plans/assimilated/2026-04-29-directive-c-rbac-topology.md`
