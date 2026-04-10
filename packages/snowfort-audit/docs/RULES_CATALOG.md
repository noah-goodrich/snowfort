# Snowfort-Audit Rule Catalog (WAF-Aligned)

This catalog lists all 116 built-in rules. Generated from `get_all_rules()` on 2026-04-10.

## Cost Optimization (COST) — 34 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| COST_001 | Aggressive Auto-Suspend | Flags warehouses with loose suspend settings. | MEDIUM | Offline/Online |
| COST_002 | Zombie Warehouses | Flags unused warehouses > 7 days. | HIGH | Online |
| COST_003 | Cloud Services Ratio | Flags if cloud service credits > 10% of total compute. | MEDIUM | Online |
| COST_004 | Runaway Query Protection | Flags account-level statement timeout > 1 hour. | HIGH | Online |
| COST_005 | Multi-Cluster Safeguard | Checks scaling policy on MCWs. | LOW | Offline |
| COST_006 | Underutilized Warehouse | Identifies over-provisioned warehouses with low load. | LOW | Online |
| COST_007 | Stale Table Detection | Large tables not queried in 90+ days. | MEDIUM | Online |
| COST_008 | Staging Table Type | Permanent staging-named tables with fail-safe cost. | MEDIUM | Online |
| COST_009 | Per-Warehouse Statement Timeout | Warehouses with default 48h or no timeout. | MEDIUM | Online |
| COST_010 | QAS Eligibility | Recommends enabling Query Acceleration for eligible warehouses. | MEDIUM | Online |
| COST_011 | Workload Heterogeneity | Detects mixed workloads via variance analysis. | MEDIUM | Online |
| COST_012 | High-Churn Permanent Tables | Permanent tables with high DML churn (consider transient). | MEDIUM | Online |
| COST_012 | Isolation Pivot | Recommends isolating Elephant queries. | MEDIUM | Online |
| COST_013 | Unused Materialized View | MVs refreshed but not queried in 30 days. | MEDIUM | Online |
| COST_014 | Automatic Clustering Cost/Benefit | High clustering credits; review vs pruning benefit. | MEDIUM | Online |
| COST_015 | Search Optimization Cost/Benefit | High SOS credits; review index usage. | MEDIUM | Online |
| COST_016 | Data Transfer Monitoring | High cross-region/egress transfer in 7 days. | MEDIUM | Online |
| COST_017 | Cortex AI Model Allowlist | Cortex AI function calls using non-allowlisted models. | MEDIUM | Online |
| COST_018 | Cortex AI Query Tag Coverage | Cortex AI rows with no QUERY_TAG (>20% untagged). | MEDIUM | Online |
| COST_019 | Cortex AI Per-User Spend | Top users by credits; outlier >3x median. | MEDIUM | Online |
| COST_020 | Cortex AI SQL Adoption | Continued use of deprecated CORTEX_FUNCTIONS_USAGE_HISTORY view. | LOW | Online |
| COST_021 | Cortex Code CLI Per-User Limit | Users approaching or exceeding CLI daily credit limit. | MEDIUM | Online |
| COST_022 | Cortex Code CLI Zombie Usage | Users with CORTEX_USER role but zero CLI usage for 30 days. | LOW | Online |
| COST_023 | Cortex Code CLI Credit Spike | Day-over-day >5x credit increase. | HIGH | Online |
| COST_024 | Cortex Agent Budget Enforcement | Agents without a Snowflake Budget attached. | HIGH | Online |
| COST_025 | Cortex Agent Spend Cap | Per-agent credits exceeding configured threshold. | HIGH | Online |
| COST_026 | Cortex Agent Tag Coverage | Agents with null AGENT_TAGS (no cost-center attribution). | MEDIUM | Online |
| COST_027 | Snowflake Intelligence Daily Spend | Intelligence daily spend exceeds threshold. | HIGH | Online |
| COST_028 | Snowflake Intelligence Governance | Intelligence running without cost-center tag attribution. | MEDIUM | Online |
| COST_029 | Cortex Search Consumption Breakdown | SERVING/EMBED token split unexpected or cap breach. | MEDIUM | Online |
| COST_030 | Cortex Search Zombie Service | Zero-serving services still consuming BATCH refresh credits. | MEDIUM | Online |
| COST_031 | Cortex Analyst Per-User Quota | Users exceeding configured daily analyst request quota. | MEDIUM | Online |
| COST_032 | Cortex Analyst Without Budget | ENABLE_CORTEX_ANALYST=TRUE with no account budget set. | HIGH | Online |
| COST_033 | Cortex Document Processing Spend | AI_PARSE_DOCUMENT + AI_EXTRACT aggregate spend exceeds threshold. | MEDIUM | Online |

> **Note:** COST_012 has two implementations (High-Churn Permanent Tables and Isolation Pivot)
> sharing the same rule ID. Both run during online scans.
>
> **Note:** Cortex cost rules (COST_016–033) are unit-tested only — seeding real Cortex usage
> incurs real credits. See `docs/SMOKE_TEST.md` for the full coverage tier breakdown.

## Security (SEC) — 26 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| SEC_001 | Admin Exposure | Flags if too many users have ACCOUNTADMIN. | CRITICAL | Online |
| SEC_002 | MFA Enforcement | Flags admin users without MFA enabled. | CRITICAL | Online |
| SEC_003 | Network Perimeter | Flags open (0.0.0.0/0) network policies. | CRITICAL | Online |
| SEC_004 | Public Grants | Flags extensive privileges granted to PUBLIC role. | HIGH | Online |
| SEC_005 | User Ownership | Flags objects owned by Users instead of Roles. | MEDIUM | Online |
| SEC_006 | Service User Security | Flags service users with passwords or missing RSA keys. | HIGH | Online |
| SEC_007 | Zombie Users | Flags inactive users (>90 days without login). | HIGH | Online |
| SEC_007_ROLE | Service Role Scope | Ensures SVC_ roles access at most 1 database. | HIGH | Online |
| SEC_007_USER | Service User Scope | Ensures service users access at most 1 database. | HIGH | Online |
| SEC_008 | Zombie Roles | Flags orphan or empty roles with no users or privileges. | LOW | Online |
| SEC_008_ROLE | Read-Only Role Integrity | Verifies _RO roles have no write privileges. | CRITICAL | Online |
| SEC_008_USER | Read-Only User Integrity | Verifies _RO users have no write privileges. | CRITICAL | Online |
| SEC_009 | Data Masking Policy Coverage | Tagged-sensitive columns without masking policy. | MEDIUM | Online |
| SEC_010 | Row Access Policy Coverage | Tables with sensitive data but no RAP. | MEDIUM | Online |
| SEC_011 | Federated Authentication | Users with password-only auth; recommend SSO/key-pair. | MEDIUM | Online |
| SEC_012 | Password Policy | No password policy defined in account. | MEDIUM | Online |
| SEC_013 | Data Exfiltration Prevention | PREVENT_UNLOAD_TO_INLINE_URL / storage integration params. | HIGH | Online |
| SEC_014 | Private Connectivity | No network policy; consider private link. | LOW | Online |
| SEC_015 | SSO Coverage | Non-SSO users in SSO-enabled account. | MEDIUM | Online |
| SEC_016 | MFA Account Enforcement | Account-level REQUIRE_MFA_FOR_ALL_USERS not enabled. | CRITICAL | Online |
| SEC_017 | CIS Benchmark Scanner | Trust Center CIS scanner package not enabled. | MEDIUM | Online |
| SEC_018 | Programmatic Access Token Governance | PATs with no expiry or expiry >90 days. | HIGH | Online |
| SEC_019 | AI_REDACT Policy Coverage | Sensitive-tagged columns without AI_REDACT masking policy. | MEDIUM | Online |
| SEC_020 | Authorization Policy Coverage | Warehouses lacking an authorization policy. | MEDIUM | Online |
| SEC_021 | Trust Center Findings | Unresolved HIGH/CRITICAL Trust Center findings. | HIGH | Online |
| SEC_022 | PrivateLink Enforcement | PrivateLink configured but public endpoint not restricted. | MEDIUM | Online |
| SEC_023 | Snowpark Container Services Security | SPCS services without a documentation comment. | MEDIUM | Online |

## Reliability (REL) — 10 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| REL_001 | Replication Gaps | Production databases not in replication group. | CRITICAL | Online |
| REL_002 | Retention Safety | Production tables with 0-day Time Travel. | HIGH | Online |
| REL_003 | Schema Instability | Tables with ENABLE_SCHEMA_EVOLUTION = TRUE. | HIGH | Offline/Online |
| REL_004 | Failover Group Completeness | Failover groups without account objects. | MEDIUM | Online |
| REL_005 | Replication Lag | Replication lag exceeds threshold. | MEDIUM | Online |
| REL_006 | Adequate Time Travel Retention | Production tables with only 1-day retention. | LOW | Online |
| REL_007 | Failed Task Detection | Recurring task failures in last 7 days. | MEDIUM | Online |
| REL_008 | Pipeline Object Replication | Production DBs with pipes not in replication group. | MEDIUM | Online |
| REL_009 | Dynamic Table Refresh Lag | Actual refresh lag >1.5x target lag. | MEDIUM | Online |
| REL_010 | Dynamic Table Failure Detection | Dynamic Tables in FAILED state in last 24 hours. | HIGH | Online |

## Performance (PERF) — 15 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| PERF_001 | Cluster Key Validation | Large tables missing or poor clustering. | HIGH | Online |
| PERF_002 | Query Queuing Detection | Sustained queuing on warehouse. | MEDIUM | Online |
| PERF_003 | Remote Spillage | Critical remote spillage indicating undersized warehouse. | CRITICAL | Online |
| PERF_003_SMART | Spilling Memory (Undersized) | Smart pivot: undersized warehouses for Snowpark-optimized. | CRITICAL | Online |
| PERF_004 | Local Spillage | Local spillage warning. | HIGH | Online |
| PERF_005 | Poor Partition Pruning | Tables with low pruning ratio. | MEDIUM | Online |
| PERF_006 | Workload Efficiency | Oversized warehouses (Pincer analysis). | MEDIUM | Online |
| PERF_007 | Gen 2 Upgrade | DML-heavy workloads suitable for Gen 2. | LOW | Online |
| PERF_008 | Snowpark Optimization | Memory-bound workloads for Snowpark migration. | MEDIUM | Online |
| PERF_009 | Cache Contention | ETL queries evicting BI cache. | MEDIUM | Online |
| PERF_010 | Dynamic Table Lag | DTs exceeding TARGET_LAG repeatedly. | MEDIUM | Online |
| PERF_011 | Clustering Key Quality | Cluster key anti-patterns (>4 expr, MOD). | MEDIUM | Online |
| PERF_012 | Warehouse Workload Isolation | Mixed BI + ETL on same warehouse. | MEDIUM | Online |
| PERF_013 | Query Latency SLO | P99 latency exceeds threshold. | MEDIUM | Online |
| SQL_001 | No SELECT * | SELECT * in views/SQL files. | MEDIUM | Offline/Online |

## Operations (OPS) — 14 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| OP_001 | Resource Monitor | Missing resource monitors. | MEDIUM | Online |
| OP_002 | Object Comment | Databases/schemas missing comments. | LOW | Online |
| OPS_001 | Mandatory Tagging | Missing COST_CENTER, OWNER, ENVIRONMENT tags. | HIGH | Online |
| OPS_003 | Alert Configuration | No alerts or none resumed. | LOW | Online |
| OPS_005 | SLO Throttler | Warehouses significantly faster than SLO (oversized). | LOW | Online |
| OPS_006 | Resize Churn | Frequent manual resizing events. | LOW | Online |
| OPS_007 | Notification Integration | No notification integration for alerts. | LOW | Online |
| OPS_008 | Observability Infrastructure | No dedicated observability/monitoring database. | LOW | Online |
| OPS_009 | IaC Drift Readiness | Warehouses/DBs without MANAGED_BY tag. | LOW | Online |
| OPS_010 | Event Table Configuration | No customer-owned event table. | LOW | Online |
| OPS_011 | Data Metric Functions Coverage | No DMF references for data quality monitoring. | LOW | Online |
| OPS_012 | Alert Execution Reliability | Alert success rate below threshold over last 7 days. | MEDIUM | Online |
| OPS_013 | Developer Sandbox Sprawl | Dropped databases with Time Travel retention >7 days. | LOW | Online |
| OPS_014 | Permifrost Drift | Actual grants diverge from Permifrost YAML spec (opt-in via `--permifrost-spec`). | MEDIUM | Online |

## Governance (GOV) — 9 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| GOV_001 | Future Grants Anti-Pattern | Flags manual FUTURE GRANTS. | MEDIUM | Online |
| GOV_002 | Documentation Coverage | Production objects missing comments. | LOW | Online |
| GOV_003 | Account Budget Enforcement | No active Snowflake Budgets. | CRITICAL | Online |
| GOV_004 | Sensitive Data Classification | PII-like columns without classification tag. | MEDIUM | Online |
| GOV_005 | Masking Policy Coverage (Extended) | AI_CLASSIFY-tagged sensitive columns without masking policy. | MEDIUM | Online |
| GOV_006 | Inbound Share Risk | Inbound shares without owner tag or documentation. | MEDIUM | Online |
| GOV_007 | Outbound Share Risk | Outbound shares without expiration or per-consumer grants. | MEDIUM | Online |
| GOV_008 | Cross-Region Inference | CORTEX_ENABLED_CROSS_REGION enabled with data-residency-tagged objects present. | HIGH | Online |
| GOV_009 | Iceberg Table Governance | Iceberg tables missing catalog integration or retention policy. | MEDIUM | Online |

## Static Analysis (STAT) — 7 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| STAT_001 | Hardcoded Env Suffix | Flags _DEV/_PROD in code. | LOW | Offline |
| STAT_002 | Naked Drop Statement | Flags DROP TABLE/SCHEMA in scripts. | HIGH | Offline |
| STAT_003 | Secret Exposure | Hardcoded secrets/keys in code. | CRITICAL | Offline |
| STAT_004 | MERGE Pattern | INSERT INTO ... SELECT; recommend idempotent MERGE. | MEDIUM | Offline |
| STAT_005 | Dynamic Table Complexity | DT with >5 JOINs. | MEDIUM | Offline |
| STAT_006 | Anti-Pattern SQL | ORDER BY without LIMIT; OR in JOIN; UNION vs UNION ALL. | MEDIUM | Offline |
