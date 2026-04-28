# Project A: Foundation — Trustworthy Output

*Shipped: April 28, 2026 — PR #1 merged to main*

## Objective

Make snowfort-audit's existing ~118 rules reliable and its output consumable by both
humans and Cortex Code. Fix silent error handling that hides failures, add SSO-aware
severity so findings reflect the account's actual auth posture, reduce CDC noise via
configurable regex patterns (not hard-coded lists), add violation categorization with
adjusted scoring, and enrich the JSON manifest and audit cache with enough context for
Cortex Code to parse findings and walk users through interactive remediation.

## Acceptance Criteria

### AC-1: Zero Silent Exception Swallowing [x]

**Current state:** 108 `except Exception` blocks across `domain/rules/` and
`use_cases/online_scan.py`. Of those, ~85 in `domain/rules/` already follow the
canonical `is_allowlisted_sf_error` / `RuleExecutionError` pattern. The remaining
~15-20 are the problem:
- `domain/rules/cost.py` lines 146, 568: bare `except Exception: pass` (silent)
- `domain/rules/cortex_cost.py` lines 196, 694: bare `except Exception: return []`
- `use_cases/online_scan.py` line 146 (`_check_views_chunk`): bare `pass`
- `use_cases/online_scan.py` line 221: connectivity fallback (legitimate, keep)
- `use_cases/online_scan.py` line 413: bare `pass` during prefetch
- Several interface-layer handlers (streamlit, TUI, CLI) — these are outside rule
  execution and may legitimately catch-and-display. Review case-by-case.

Every `except Exception` in `domain/rules/` must either:
- call `is_allowlisted_sf_error(exc)` and return `[]` for allowlisted errors, or
- raise `RuleExecutionError(self.id, str(exc), cause=exc)`

In `use_cases/online_scan.py`, each handler must be reviewed individually:
- Rule execution handlers (`_run_rules_chunk` line 173): already captures as
  `(rule_id, error_message)` tuple — this is intentional error collection, but
  should be converted to `RuleExecutionError` for consistency.
- Prefetch/connectivity handlers: may legitimately catch-and-continue with logging.
  These get a case-by-case pass but must log, not silently swallow.

The scan summary reports:
- Count and IDs of errored rules
- A reliability flag: scan marked "unreliable" if >5% of executed rules errored

**TDD:**
1. Write test: rule with bare `except Exception: return []` → assert it raises
   `RuleExecutionError` after fix.
2. Write test: `OnlineScanUseCase` collects `RuleExecutionError` into
   `AuditResult.errored_rules: list[str]` and sets `AuditResult.reliable: bool`.
3. Write test: >5% error rate → `reliable=False`.
4. Then implement: fix ~15-20 bare handlers, add `errored_rules` and `reliable`
   to `AuditResult`.

**Verify:**
```bash
grep -rn "except Exception" src/snowfort_audit/domain/rules/ \
  | grep -v "RuleExecutionError\|is_allowlisted_sf_error" | wc -l
# Must output: 0
```
Note: `use_cases/online_scan.py` and `interface/` are excluded from the zero-match
check because they contain legitimate non-rule exception handlers (connectivity
fallbacks, prefetch degradation, UI error display). These are reviewed individually.

### AC-2: SSO-Aware Severity [x]

**Current state:** SSO detection already exists. `_derive_sso_and_zombies()` in
`online_scan.py` (line 66) computes `sso_enforced=True` when ≥50% of non-SERVICE
users have `ext_authn_uid` set. Two rules already consume it:
- SEC_003 (`PasswordPolicyCheck`, line 266): downgrades to `Severity.LOW` when
  `sso_enforced=True` — **already done, no change needed.**
- SEC_007 (`ZombieUserCheck`, lines 529-530): simple LOW downgrade when
  `sso_enforced=True` — **partially done, needs auth-type bucketing.**

**Remaining work** is extending SSO awareness to additional rules and adding
auth-type bucketing to SEC_007:

| Rule | Current Behavior | New Behavior | Category |
|------|-----------------|--------------|----------|
| SEC_002 (MFA per-user) | Always HIGH | LOW when `sso_enforced` | EXPECTED |
| SEC_003 (password policy) | Already LOW when SSO | No change needed | EXPECTED |
| SEC_007 zombie: password + admin | Simple LOW when SSO | CRITICAL (bucketed) | ACTIONABLE |
| SEC_007 zombie: password, no admin | Simple LOW when SSO | HIGH (bucketed) | ACTIONABLE |
| SEC_007 zombie: SSO-only, no pwd | Simple LOW when SSO | LOW (bucketed) | INFORMATIONAL |
| SEC_007 zombie: key-pair only | Simple LOW when SSO | LOW (bucketed) | INFORMATIONAL |
| SEC_011 non-federated: svc acct | Always MEDIUM | LOW when `sso_enforced` | EXPECTED |
| SEC_016 (MFA account-level) | Always HIGH | LOW when `sso_enforced` | EXPECTED |

SSO detection threshold is configurable via `SecurityConventions.sso_threshold: float`
(default `0.5` — matching the current hardcoded value in `_derive_sso_and_zombies()`).

Fix SEC_008 (ZombieRoleCheck) SQL compilation bug discovered during production run.

**TDD:**
1. Write parametrized test for each row above: given `sso_enforced=True/False`,
   assert severity and category match.
2. Write test: SEC_003 already returns LOW when `sso_enforced=True` (regression guard).
3. Write test: SEC_007 with mixed user types → correct bucketing per auth method.
4. Write test: `sso_threshold=0.8` changes SSO detection boundary.
5. Write test: SEC_008 SQL compiles without error against mock cursor.
6. Then implement: add SSO awareness to SEC_002/SEC_011/SEC_016, refactor SEC_007
   to bucket by auth type instead of blanket LOW downgrade.

### AC-3: CDC Noise Reduction via Configurable Regex [x]

`HighChurnThresholds` gains a new field:
```python
cdc_schema_pattern: str = r"(?i)(staging|raw|cdc|fivetran|airbyte|stitch|hevo)"
```

COST_012 (`HighChurnPermanentTableCheck`) behavior:
- If table's schema name matches `cdc_schema_pattern`: set `category=EXPECTED`,
  change remediation to "Convert to TRANSIENT to eliminate fail-safe cost."
- If table name matches existing `exclude_name_patterns`: skip entirely (existing behavior).
- Unmatched high-churn tables: `category=ACTIONABLE`, severity stays MEDIUM.

Pattern is user-configurable via `pyproject.toml`:
```toml
[tool.snowfort.thresholds.high_churn]
cdc_schema_pattern = "(?i)(staging|raw|ingest)"
```

**TDD:**
1. Write test: table `RAW_CDC.PUBLIC.CUSTOMERS` with default pattern → EXPECTED
   category, transient remediation message.
2. Write test: table `ANALYTICS.PUBLIC.REVENUE` with default pattern → ACTIONABLE,
   original remediation.
3. Write test: custom pattern from conventions overrides default.
4. Write test: `exclude_name_patterns` still works (glob match → skip entirely).
5. Then implement: add field to `HighChurnThresholds`, update COST_012 logic.

### AC-4: Violation Categorization + Adjusted Scoring [x]

New enum in `rule_definitions.py`:
```python
class FindingCategory(Enum):
    ACTIONABLE = "ACTIONABLE"    # Requires remediation
    EXPECTED = "EXPECTED"        # Known/accepted behavior (CDC, SSO overlap)
    INFORMATIONAL = "INFORMATIONAL"  # FYI only (service accounts, key-pair users)
```

`Violation` gains:
```python
category: FindingCategory = FindingCategory.ACTIONABLE
```

`AuditScorecard` gains:
```python
adjusted_score: int = 100          # Score from ACTIONABLE violations only
adjusted_grade: str = "A"
actionable_count: int = 0
expected_count: int = 0
informational_count: int = 0
```

Scoring logic: `adjusted_score` uses the same `_pillar_score()` formula but counts
only `category=ACTIONABLE` violations. `compliance_score` (raw) unchanged for
backward compatibility. Both displayed in CLI output.

**TDD:**
1. Write test: 100 EXPECTED + 5 ACTIONABLE violations → `compliance_score` reflects
   all 105; `adjusted_score` reflects only the 5.
2. Write test: `from_violations()` correctly counts `actionable_count`,
   `expected_count`, `informational_count`.
3. Write test: default `category=ACTIONABLE` — existing violations without explicit
   category produce identical raw and adjusted scores.
4. Write test: `Violation(category=FindingCategory.EXPECTED)` frozen dataclass works.
5. Then implement: add enum, update `Violation`, update `AuditScorecard`, update
   `_count_violations()`.

### AC-5: Cortex-Native Manifest Enrichment [x]

Each violation in `--manifest` JSON, `.snowfort/audit_results.json` cache, and
`build_yaml_report()` YAML gains:

| Field | Type | Source |
|-------|------|--------|
| `category` | string | `FindingCategory.value` |
| `context` | string | `Rule.rationale` (1-sentence why-it-matters) |
| `blast_radius` | int or null | Count of affected objects where computable |
| `quick_win` | bool | `True` if remediation is a single SQL statement |
| `remediation_key` | string or null | Already exists on `Violation` |

YAML report `summary` section gains `adjusted_score` and `adjusted_grade` alongside
existing `compliance_score`.

`CortexSynthesizer` prompt updated to include category breakdown:
```
Of {total} findings: {actionable} require action, {expected} are expected behavior,
{informational} are informational. Adjusted score: {adjusted_score}/100 ({adjusted_grade}).
Focus your analysis on the {actionable} actionable findings.
```

**TDD:**
1. Write test: `_render_manifest_json()` output includes `category`, `context`,
   `blast_radius`, `quick_win` on each violation dict.
2. Write test: `write_audit_cache()` output includes all new fields; loading a
   cache file missing these fields defaults gracefully (no crash).
3. Write test: `build_yaml_report()` summary includes `adjusted_score`.
4. Write test: `CortexSynthesizer` prompt string contains category breakdown.
5. Then implement: update serialization in `report.py`, cache load/save, YAML
   builder, synthesizer prompt.

### AC-6: Nothing Breaks [x]

- `make check` passes: lint + mypy + import-linter + tests + coverage >= 80%.
- `rules_snapshot.yaml` updated to reflect any rule behavior changes.
- JSON cache backward-compatible: old caches without `category`/`context` fields
  load without crash, defaulting to `ACTIONABLE` / empty string.

**TDD:** This criterion is verified by running the full existing test suite plus
all new tests from AC-1 through AC-5. No separate test needed — it's the
integration gate.

## Scope Boundaries

**In scope:**
- Backfilling error handling across all existing rules
- SSO-aware severity adjustments to existing SEC rules
- CDC pattern-based category assignment for COST_012
- Violation categorization enum + adjusted scoring
- Manifest/cache/YAML enrichment for Cortex Code consumption
- Fixing SEC_008 SQL compilation bug

**Out of scope — these go in later projects (Directives B-F):**
- New rule IDs (no new PERF_0xx, COST_0xx, SEC_0xx, GOV_0xx, OPS_0xx)
- Warehouse sizing analysis (Directive B)
- Storage cost optimization / Iceberg migration (Directive B)
- RBAC topology / god-role detection (Directive C)
- Sensitive data detection (Directive D)
- IaC drift detection / dbt grant analysis (Directive E)
- Cortex AI governance rules (Directive F)
- Executive summary narrative generation
- Remediation SQL generation / batch scripts
- TUI redesign

**If done early:** Ship it. Do not expand into Directive B-F scope.

## Ship Definition

1. PR opened with all changes
2. `make check` exits 0 (lint + mypy + import-linter + tests + coverage)
3. `grep` verification for AC-1 returns 0 matches
4. Manual smoke test: `snowfort audit scan --manifest` against test account produces
   JSON with `category`, `context`, `blast_radius`, `quick_win` fields
5. PR merged to main

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Backfilling `RuleExecutionError` surfaces previously-hidden failures as ERRORED | High | This is correct behavior. Document in release notes. |
| `Violation` frozen dataclass gaining `category` field breaks `asdict()` serialization | Low | Default value ensures backward compat. Test serialization explicitly. |
| SSO detection threshold (50%) misfires during SSO migration | Medium | Make threshold configurable in `SecurityConventions`. Document in conventions reference. |
| `adjusted_score` diverges wildly from `compliance_score`, confusing users | Medium | Always show both. Label clearly: "Raw" vs "Adjusted (actionable only)". |
| Old audit cache files missing new fields crash on load | Low | Default missing fields on deserialization. Test explicitly in AC-5. |

## Process

**Test-Driven Development at all times and in all places.** For every acceptance
criterion: write the failing test first, then implement until it passes, then
refactor. No implementation without a red test. No PR without green tests.

## Dependencies

- None. This project has no external dependencies. It modifies only existing code
  and adds new fields with defaults.

## Related Directives

- [Directive B: Warehouse Sizing & Cost Optimization](../directives/warehouse-sizing.md)
- [Directive C: RBAC Topology & Role Hierarchy](../directives/rbac-topology.md)
- [Directive D: Sensitive Data Detection](../directives/sensitive-data-detection.md)
- [Directive E: IaC Drift + dbt Grants](../directives/iac-drift-dbt-grants.md)
- [Directive F: Cortex AI Governance](../directives/cortex-ai-governance.md)
