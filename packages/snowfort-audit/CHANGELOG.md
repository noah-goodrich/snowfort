# Changelog

All notable changes to snowfort-audit are documented here.

---

## [1.0.0] — 2026-04-10

### Summary
v1.0.0 is the production-stable release. Fixes silent error swallowing across all 116 rules, surfaces errored rule counts in scan output, adds GitHub Actions CI, and publishes to PyPI as `Development Status :: 5 - Production/Stable`.

### AC1 — Structured error handling across all rules
All 81 `except Exception` blocks in `domain/rules/` (security.py, cost.py, op_excellence.py, reliability.py, governance.py, workload.py, perf.py, cost_extensions.py, perf_extensions.py, strategy.py, ops.py, security_advanced.py) now raise `RuleExecutionError` or call `is_allowlisted_sf_error()` before returning `[]`. Zero bare `except Exception: return []` remaining.

### AC2 — Scan output surfaces errored rules
- `OnlineScanUseCase.errored_rules: list[str]` attribute populated after `execute()`.
- Sequential and parallel execution paths both track and log `ERRORED <rule_id>` for each failed rule.
- `report_findings` and `report_findings_guided` display `Warning: N rule(s) errored — results may be incomplete.` when rules errored.
- `--quiet` one-liner includes `, N rule(s) errored` suffix when applicable.

### AC3 — GitHub Actions CI workflow
`.github/workflows/ci.yml` runs `ruff check`, `mypy`, and `pytest --cov --cov-fail-under=80` on push/PR targeting `packages/snowfort-audit/**`.

### AC4 — PyPI publish
Version bumped to `1.0.0`. Development Status classifier changed to `5 - Production/Stable`.

### AC5 — Tests updated
76 tests updated: `_not_found_error()` helpers set `errno = 2003` for allowlisted errors; error-path tests assert `pytest.raises(RuleExecutionError)` instead of `== []`.

---

## [0.4.1] — 2026-04-10

### Documentation

- `docs/RULES_CATALOG.md` regenerated: 83 → 116 rules. Added all 32 rules shipped in v0.4.0 that were missing from the catalog (COST_017–033, GOV_005–009, OPS_013–014, REL_009–010, SEC_018–023). Updated all section counts.
- `docs/SMOKE_TEST.md` created: documents smoke-covered vs. unit-only test tiers for all 116 rules. Clarifies that Cortex cost rules (COST_016–033) are unit-only (seeding real usage costs real credits) and OPS_014 is opt-in unit-only.
- No code or rule changes from v0.4.0.

---

## [0.4.0] — 2026-04-09

### Summary
v0.4.0 closes production bugs surfaced by the INCLOUDCOUNSEL scan, adds 26 new rules, ships the Cortex AI cost governance rule pack, and completes all deferred work. Rule count: **116** (up from 90 in v0.3.0).

---

### A — Production Bug Fixes

- **SEC_001 grant-graph reachability fix** (`AdminExposureCheck`): Rewrote to use a recursive CTE over `GRANTS_TO_ROLES` + union of `GRANTS_TO_USERS`. The previous two-query union missed users reaching ACCOUNTADMIN via multi-hop role chains. INCLOUDCOUNSEL: 3 flagged → 7 actual.
- **Dropped-database DDL noise** (`_fetch_batch_ddl`): Added `DATABASES WHERE DELETED IS NULL` pre-filter so rules no longer attempt DDL fetches for dropped databases, eliminating spurious "object not found" telemetry noise.

### B — Rule Tuning

- **COST_012** `HighChurnPermanentTableCheck`: accepts `conventions.thresholds.high_churn.exclude_name_patterns` (default `()`) to suppress CDC staging table false positives.
- **COST_001** `AggressiveAutoSuspendCheck`: default threshold raised from 1s → 30s; also flags `auto_suspend > 3600s` (too permissive) as MEDIUM.
- **SEC_003** `NetworkPerimeterCheck`: severity downgraded from HIGH → LOW when `scan_context.sso_enforced = True`.
- **OPS_001** `MandatoryTaggingCheck`: severity CRITICAL → MEDIUM; excludes warehouses matching `conventions.thresholds.mandatory_tagging.exclude_warehouse_patterns` (default `("COMPUTE_SERVICE_WH_*",)`).
- **SEC_007** `ZombieUserCheck`: same SSO-aware severity downgrade as SEC_003.
- **SEC_011** `FederatedAuthenticationCheck`: excludes `TYPE='SERVICE'` users and users already flagged as zombies.

### C — Performance & Architecture

- **Generalized `ScanContext.get_or_fetch(view, window_days, fetcher)`**: single shared cache for all prefetched views. GRANTS queries (used by SEC_007/008/011, GOV_001) now execute **once** across all rules, not independently per-rule.
- **Keypair auth bootstrap** (`snowfort audit bootstrap --keypair [--dry-run]`): generates RSA-2048 keypair, writes private key with mode `0600` (never `/tmp`), prints `ALTER USER` SQL. Replaces MFA-blocked service accounts.
- **MFA detection warning**: scan startup detects MFA at connection time and emits a remediation hint pointing to `bootstrap --keypair`.
- **Column-name refactor**: all 15+ rule files migrated from magic tuple indices (`row[0]`) to `ScanContext.col()` helper. Zero behavioral change (verified by snapshot harness).

### D — New Coverage Rules

#### D1–D6: Cortex AI Cost Governance (18 rules, COST_016–033)
Full rule pack for Snowflake Cortex cost governance. Each rule targets a distinct Cortex feature and degrades gracefully (returns `[]`) when the target view is unavailable:

| Rule | Name | Feature |
|------|------|---------|
| COST_016 | CortexAIFunctionCreditBudgetCheck | AI Functions daily budget |
| COST_017 | CortexAIFunctionModelAllowlistCheck | Model allowlist enforcement |
| COST_018 | CortexAIFunctionQueryTagCoverageCheck | Chargeback tag hygiene |
| COST_019 | CortexAIFunctionPerUserSpendCheck | Per-user outlier detection |
| COST_020 | CortexAISQLAdoptionCheck | Deprecated view usage |
| COST_021 | CortexCodeCLIPerUserLimitCheck | CLI credit limit enforcement |
| COST_022 | CortexCodeCLIZombieUsageCheck | Zombie CLI users |
| COST_023 | CortexCodeCLICreditSpikeCheck | Day-over-day spike detection |
| COST_024 | CortexAgentBudgetEnforcementCheck | Agent budget enforcement |
| COST_025 | CortexAgentSpendCapCheck | Per-agent spend cap |
| COST_026 | CortexAgentTagCoverageCheck | Agent tag attribution |
| COST_027 | SnowflakeIntelligenceDailySpendCheck | Intelligence daily credits |
| COST_028 | SnowflakeIntelligenceGovernanceCheck | Intelligence cost-center tag |
| COST_029 | CortexSearchConsumptionBreakdownCheck | Search serving vs. refresh ratio |
| COST_030 | CortexSearchZombieServiceCheck | Zero-serving zombie services |
| COST_031 | CortexAnalystPerUserQuotaCheck | Analyst per-user quota |
| COST_032 | CortexAnalystEnabledWithoutBudgetCheck | Analyst with no account budget |
| COST_033 | CortexDocumentProcessingSpendCheck | Document processing spend |

#### D7–D12: Additional Coverage (8 rules)

| Rule | Name | Category |
|------|------|---------|
| REL_009 | DynamicTableRefreshLagCheck | Dynamic Tables |
| REL_010 | DynamicTableFailureDetectionCheck | Dynamic Tables |
| GOV_005 | MaskingPolicyCoverageExtendedCheck | AI_CLASSIFY-tagged columns |
| GOV_006 | InboundShareRiskCheck | Data Sharing |
| GOV_007 | OutboundShareRiskCheck | Data Sharing |
| GOV_008 | CrossRegionInferenceCheck | Cross-region Cortex inference |
| OPS_013 | DeveloperSandboxSprawlCheck | Dropped DB Time Travel waste |
| OPS_014 | PermifrostDriftCheck | Permifrost YAML spec drift (opt-in via `--permifrost-spec`) |

### E — Q1 2026 Feature Gap Rules (7 rules)

| Rule | Name | Feature |
|------|------|---------|
| SEC_018 | ProgrammaticAccessTokenCheck | PAT expiry governance |
| SEC_019 | AIRedactPolicyCoverageCheck | AI_REDACT masking policy coverage |
| SEC_020 | AuthorizationPolicyCheck | Authorization policy on warehouses |
| SEC_021 | TrustCenterExtensionsCheck | Trust Center HIGH/CRITICAL findings |
| SEC_022 | PrivateLinkOnlyEnforcementCheck | PrivateLink enforcement |
| SEC_023 | SnowparkContainerServicesSecurityCheck | SPCS service documentation |
| GOV_009 | IcebergTableGovernanceCheck | Iceberg catalog/retention/encryption |

### F — Deferred Work (shipped)

- **F1 Cortex Code Skill**: `.cortex/skills/snowfort-audit/SKILL.md` teaches Cortex Code to invoke `snowfort audit scan --manifest`, triage findings by severity, and generate remediation SQL from `remediation_instruction`.
- **F2 Structured Cortex summary in YAML**: `CortexSummary` dataclass (`tl_dr`, `top_risks`, `quick_wins`). `CortexSynthesizer.summarize_structured()` uses a structured prompt + regex parser. `AuditResult.cortex_summary` field. YAML reports include `cortex_summary:` block when `--cortex` is used.

---

## [0.3.0] — 2026-03-xx

- Log-dampened scoring formula (prevents high-volume low-severity violations from flooring the score).
- Performance: view-phase parallelization, batch DDL fetch, shared query cache.
- Added `--workers` flag (default 4), `--profile` timing table.
- 90 rules at release.

## [0.2.0] — 2026-02-xx

- Session 3 performance engineering: N+1 elimination, SQL rewrites.

## [0.1.0] — 2026-01-xx

- Initial release: 6-pillar WAF scan, offline + online modes, YAML export.
