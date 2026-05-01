# Smoke Test Coverage

This document classifies every built-in rule by its test coverage tier:

- **Smoke-covered** — seeded via `demo_setup.sql` / validated by `scripts/smoke_test.sh`
- **Unit-only** — verified by unit tests in `tests/unit/` only; no live Snowflake seeding

Rules in the "unit-only" tier either (a) require real service usage that costs credits to seed, (b) check for account-level parameters that cannot be safely toggled in a shared sandbox, or (c) are opt-in rules that require external inputs.

---

## Cost Optimization (COST)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| COST_001 | Aggressive Auto-Suspend | Smoke | Seeded warehouse has no auto_suspend |
| COST_002 | Zombie Warehouses | Unit-only | Requires 7+ days of no usage history |
| COST_003 | Cloud Services Ratio | Unit-only | Requires real credit history |
| COST_004 | Runaway Query Protection | Unit-only | Account-level parameter |
| COST_005 | Multi-Cluster Safeguard | Unit-only | Offline rule |
| COST_006 | Underutilized Warehouse | Unit-only | Requires 7-day usage history |
| COST_007 | Stale Table Detection | Unit-only | Requires 90-day query history |
| COST_008 | Staging Table Type | Unit-only | Naming-based |
| COST_009 | Per-Warehouse Statement Timeout | Unit-only | Parameter check |
| COST_010 | QAS Eligibility | Unit-only | Requires query history |
| COST_011 | Workload Heterogeneity | Unit-only | Requires query history |
| COST_012 | High-Churn Permanent Tables | Unit-only | Requires DML history |
| COST_013 | Unused Materialized View | Unit-only | Requires 30-day usage history |
| COST_014 | Automatic Clustering Cost/Benefit | Unit-only | Requires credit history |
| COST_015 | Search Optimization Cost/Benefit | Unit-only | Requires credit history |
| COST_045 | Data Transfer Monitoring | Unit-only | Requires transfer history |
| COST_046 | Isolation Pivot | Unit-only | Requires query history |
| COST_017 | Cortex AI Model Allowlist | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_018 | Cortex AI Query Tag Coverage | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_019 | Cortex AI Per-User Spend | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_020 | Cortex AI SQL Adoption | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_021 | Cortex Code CLI Per-User Limit | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_022 | Cortex Code CLI Zombie Usage | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_023 | Cortex Code CLI Credit Spike | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_024 | Cortex Agent Budget Enforcement | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_025 | Cortex Agent Spend Cap | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_026 | Cortex Agent Tag Coverage | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_027 | Snowflake Intelligence Daily Spend | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_028 | Snowflake Intelligence Governance | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_029 | Cortex Search Consumption Breakdown | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_030 | Cortex Search Zombie Service | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_031 | Cortex Analyst Per-User Quota | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_032 | Cortex Analyst Without Budget | **Unit-only** | Seeding Cortex usage costs real credits |
| COST_033 | Cortex Document Processing Spend | **Unit-only** | Seeding Cortex usage costs real credits |

---

## Security (SEC)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| SEC_001 | Admin Exposure | Unit-only | Grant-graph reachability; seeding ACCOUNTADMIN grants too permissive |
| SEC_002 | MFA Enforcement | Unit-only | Account-level user configuration |
| SEC_003 | Network Perimeter | Unit-only | Network policy parameter |
| SEC_004 | Public Grants | Unit-only | Requires grant state inspection |
| SEC_005 | User Ownership | Unit-only | Object ownership inspection |
| SEC_006 | Service User Security | Unit-only | User attribute inspection |
| SEC_007 | Zombie Users | Unit-only | Requires login history |
| SEC_007_ROLE | Service Role Scope | Unit-only | Requires grant state |
| SEC_007_USER | Service User Scope | Unit-only | Requires grant state |
| SEC_008 | Zombie Roles | Unit-only | Requires grant state |
| SEC_008_ROLE | Read-Only Role Integrity | Unit-only | Requires grant state |
| SEC_008_USER | Read-Only User Integrity | Unit-only | Requires grant state |
| SEC_009 | Data Masking Policy Coverage | Unit-only | Requires tag + policy state |
| SEC_010 | Row Access Policy Coverage | Unit-only | Requires policy state |
| SEC_011 | Federated Authentication | Unit-only | User attribute inspection |
| SEC_012 | Password Policy | Unit-only | Account-level policy |
| SEC_013 | Data Exfiltration Prevention | Unit-only | Account parameters |
| SEC_014 | Private Connectivity | Unit-only | Network policy inspection |
| SEC_015 | SSO Coverage | Unit-only | User attribute inspection |
| SEC_016 | MFA Account Enforcement | Unit-only | Account parameter |
| SEC_017 | CIS Benchmark Scanner | Unit-only | Trust Center inspection |
| SEC_018 | Programmatic Access Token Governance | Unit-only | PAT table inspection |
| SEC_019 | AI_REDACT Policy Coverage | Unit-only | Tag + policy cross-reference |
| SEC_020 | Authorization Policy Coverage | Unit-only | Warehouse attribute inspection |
| SEC_021 | Trust Center Findings | Unit-only | Trust Center view inspection |
| SEC_022 | PrivateLink Enforcement | Unit-only | Account parameter + system function |
| SEC_023 | Snowpark Container Services Security | Unit-only | SHOW SERVICES output |

---

## Reliability (REL)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| REL_001 | Replication Gaps | Unit-only | Replication group inspection |
| REL_002 | Retention Safety | Unit-only | Table parameter inspection |
| REL_003 | Schema Instability | Unit-only | Table parameter inspection |
| REL_004 | Failover Group Completeness | Unit-only | Failover group inspection |
| REL_005 | Replication Lag | Unit-only | Requires replication history |
| REL_006 | Adequate Time Travel Retention | Unit-only | Table parameter inspection |
| REL_007 | Failed Task Detection | Unit-only | Requires task run history |
| REL_008 | Pipeline Object Replication | Unit-only | Replication group inspection |
| REL_009 | Dynamic Table Refresh Lag | Unit-only | Requires refresh history |
| REL_010 | Dynamic Table Failure Detection | Unit-only | Requires refresh state |

---

## Performance (PERF)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| PERF_001 | Cluster Key Validation | Unit-only | Requires query history |
| PERF_002 | Query Queuing Detection | Unit-only | Requires load history |
| PERF_003 | Remote Spillage | Unit-only | Requires query profile history |
| PERF_003_SMART | Spilling Memory | Unit-only | Requires query profile history |
| PERF_004 | Local Spillage | Unit-only | Requires query profile history |
| PERF_005 | Poor Partition Pruning | Unit-only | Requires query history |
| PERF_006 | Workload Efficiency | Unit-only | Requires load + credit history |
| PERF_007 | Gen 2 Upgrade | Unit-only | Requires query history |
| PERF_008 | Snowpark Optimization | Unit-only | Requires query history |
| PERF_009 | Cache Contention | Unit-only | Requires query history |
| PERF_010 | Dynamic Table Lag | Unit-only | Requires refresh history |
| PERF_011 | Clustering Key Quality | Smoke | Seeded table with MOD() cluster key |
| PERF_012 | Warehouse Workload Isolation | Unit-only | Requires query history |
| PERF_013 | Query Latency SLO | Unit-only | Requires query history |
| SQL_001 | No SELECT * | Unit-only | Offline / view DDL inspection |

---

## Operations (OPS)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| OPS_002 | Resource Monitor | Unit-only | Account resource monitor inspection |
| OPS_004 | Object Comment | Unit-only | Object inspection |
| OPS_001 | Mandatory Tagging | Smoke | Seeded warehouses have no tags |
| OPS_003 | Alert Configuration | Unit-only | Alert state inspection |
| OPS_005 | SLO Throttler | Unit-only | Requires credit history |
| OPS_006 | Resize Churn | Unit-only | Requires warehouse event history |
| OPS_007 | Notification Integration | Unit-only | Integration state inspection |
| OPS_008 | Observability Infrastructure | Unit-only | Database name inspection |
| OPS_009 | IaC Drift Readiness | Unit-only | Tag inspection |
| OPS_010 | Event Table Configuration | Unit-only | Event table inspection |
| OPS_011 | Data Metric Functions Coverage | Unit-only | DMF reference inspection |
| OPS_012 | Alert Execution Reliability | Unit-only | Requires alert run history |
| OPS_013 | Developer Sandbox Sprawl | Unit-only | Requires dropped DB history |
| OPS_014 | Permifrost Drift | **Unit-only (opt-in)** | Only runs with `--permifrost-spec` flag; no live seeding |

---

## Governance (GOV)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| GOV_001 | Future Grants Anti-Pattern | Unit-only | Requires grant state |
| GOV_002 | Documentation Coverage | Smoke | Seeded via SNOWFORT_TEST_UNDOCUMENTED_DB |
| GOV_003 | Account Budget Enforcement | Unit-only | Account budget inspection |
| GOV_004 | Sensitive Data Classification | Smoke | Seeded via GOV_004 seed objects |
| GOV_005 | Masking Policy Coverage (Extended) | Unit-only | Requires tag + policy cross-reference |
| GOV_006 | Inbound Share Risk | Unit-only | Requires share state |
| GOV_007 | Outbound Share Risk | Unit-only | Requires share state |
| GOV_008 | Cross-Region Inference | Unit-only | Account parameter + tag inspection |
| GOV_009 | Iceberg Table Governance | Unit-only | Requires Iceberg table state |

---

## Static Analysis (STAT)

| Rule ID | Name | Coverage Tier | Notes |
|---------|------|---------------|-------|
| STAT_001 | Hardcoded Env Suffix | Unit-only | Offline / file inspection |
| STAT_002 | Naked Drop Statement | Unit-only | Offline / file inspection |
| STAT_003 | Secret Exposure | Unit-only | Offline / file inspection |
| STAT_004 | MERGE Pattern | Unit-only | Offline / file inspection |
| STAT_005 | Dynamic Table Complexity | Unit-only | Offline / DDL inspection |
| STAT_006 | Anti-Pattern SQL | Unit-only | Offline / file inspection |

---

## Smoke Test Coverage Summary

`scripts/smoke_test.sh` seeds the account with `snowfort audit demo-setup` and asserts a small
set of rules fire in the parallel scan output (Step 5). Currently spot-checked:

- `COST_001` — AggressiveAutoSuspendCheck
- `OPS_001` — MandatoryTaggingCheck
- `GOV_004` — ObjectDocumentationCheck (via SNOWFORT_TEST_UNDOCUMENTED_DB)

All other rules are verified exclusively through unit tests in `tests/unit/`. Coverage ≥ 80% is
enforced by `make check`.
