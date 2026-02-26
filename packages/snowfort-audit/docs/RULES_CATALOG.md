# Snowfort-Audit Rule Catalog (WAF-Aligned)

This catalog lists all 83 built-in rules. Generated from `get_all_rules()` on 2026-04-07.

## Cost Optimization (COST) — 17 rules

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

> **Note:** COST_012 has two implementations (High-Churn Permanent Tables and Isolation Pivot)
> sharing the same rule ID. Both run during online scans.

## Security (SEC) — 20 rules

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

## Reliability (REL) — 8 rules

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

## Operations (OPS) — 12 rules

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

## Governance (GOV) — 4 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| GOV_001 | Future Grants Anti-Pattern | Flags manual FUTURE GRANTS. | MEDIUM | Online |
| GOV_002 | Documentation Coverage | Production objects missing comments. | LOW | Online |
| GOV_003 | Account Budget Enforcement | No active Snowflake Budgets. | CRITICAL | Online |
| GOV_004 | Sensitive Data Classification | PII-like columns without classification tag. | MEDIUM | Online |

## Static Analysis (STAT) — 7 rules

| Rule ID | Name | Description | Severity | Mode |
|---------|------|-------------|----------|------|
| STAT_001 | Hardcoded Env Suffix | Flags _DEV/_PROD in code. | LOW | Offline |
| STAT_002 | Naked Drop Statement | Flags DROP TABLE/SCHEMA in scripts. | HIGH | Offline |
| STAT_003 | Secret Exposure | Hardcoded secrets/keys in code. | CRITICAL | Offline |
| STAT_004 | MERGE Pattern | INSERT INTO ... SELECT; recommend idempotent MERGE. | MEDIUM | Offline |
| STAT_005 | Dynamic Table Complexity | DT with >5 JOINs. | MEDIUM | Offline |
| STAT_006 | Anti-Pattern SQL | ORDER BY without LIMIT; OR in JOIN; UNION vs UNION ALL. | MEDIUM | Offline |
