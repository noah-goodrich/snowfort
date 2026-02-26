# Rule applicability by object level

Each row is a rule; each column is a Snowflake object level. **✓** = the rule evaluates or reports on that level; **—** = does not apply.

**Run per view?** = Should this rule be invoked once per view during the online view phase? Only **SQL_001** uses the view name (`_resource_name`) to run a per-view check (GET_DDL + static analysis). All other rules either have no `check_online` or run account-wide and ignore `_resource_name`.

| Rule ID | Rule name | org | account | database | schema | table | view | role | grant | Run per view? |
|---------|-----------|:---:|:-------:|:--------:|:------:|:-----:|:----:|:----:|:-----:|:--------------:|
| **Governance** |
| GOV_001 | Future Grants Anti-Pattern | — | ✓ | — | — | — | — | ✓ | ✓ | No |
| GOV_002 | Object Documentation (comments) | — | — | — | — | ✓ | ✓ | — | — | No |
| GOV_003 | Account Budget Enforcement | — | ✓ | — | — | — | — | — | — | No |
| GOV_004 | Sensitive Data Classification Coverage | — | — | — | — | ✓ | — | — | — | No |
| **Security** |
| SEC_001 | Admin Exposure | — | ✓ | — | — | — | — | ✓ | ✓ | No |
| SEC_002 | MFA Enforcement | — | ✓ | — | — | — | — | — | ✓ | No |
| SEC_003 | Network Perimeter | — | ✓ | — | — | — | — | — | — | No |
| SEC_004 | Public Grants | — | ✓ | — | — | — | — | — | ✓ | No |
| SEC_005 | User Ownership | — | ✓ | ✓ | — | — | — | — | — | No |
| SEC_006 | Service User Security | — | ✓ | — | — | — | — | — | — | No |
| SEC_007 | Zombie Users | — | ✓ | — | — | — | — | — | — | No |
| SEC_008 | Zombie Roles | — | ✓ | — | — | — | — | ✓ | ✓ | No |
| SEC_009 | Data Masking Policy Coverage | — | — | — | — | ✓ | ✓ | — | — | No |
| SEC_010 | Row Access Policy Coverage | — | — | — | — | ✓ | ✓ | — | — | No |
| SEC_011 | Federated Authentication | — | ✓ | — | — | — | — | — | — | No |
| SEC_012 | Password Policy | — | ✓ | — | — | — | — | — | — | No |
| SEC_013 | Data Exfiltration Prevention | — | ✓ | — | — | — | — | — | — | No |
| SEC_014 | Private Connectivity | — | ✓ | — | — | — | — | — | — | No |
| SEC_015 | SSO Coverage | — | ✓ | — | — | — | — | — | — | No |
| SEC_016 | MFA Account Enforcement | — | ✓ | — | — | — | — | — | — | No |
| SEC_017 | CIS Benchmark Scanner | — | ✓ | — | — | — | — | — | — | No |
| **Security advanced** |
| SEC_007_ROLE | Service Role Scope | — | ✓ | — | — | — | — | ✓ | ✓ | No |
| SEC_007_USER | Service User Scope | — | ✓ | — | — | — | — | — | ✓ | No |
| SEC_008_ROLE | Read-Only Role Integrity | — | ✓ | — | — | — | — | ✓ | ✓ | No |
| SEC_008_USER | Read-Only User Integrity | — | ✓ | — | — | — | — | — | ✓ | No |
| **Reliability** |
| REL_001 | Replication Gaps | — | ✓ | ✓ | — | — | — | — | — | No |
| REL_002 | Retention Safety | — | — | — | — | ✓ | — | — | — | No |
| REL_003 | Schema Instability (evolution) | — | — | — | — | ✓ | — | — | — | No |
| REL_004 | Failover Group Completeness | — | ✓ | — | — | — | — | — | — | No |
| REL_005 | Replication Lag Monitoring | — | ✓ | — | — | — | — | — | — | No |
| REL_006 | Adequate Time Travel Retention | — | — | — | — | ✓ | — | — | — | No |
| REL_007 | Failed Task Detection | — | ✓ | ✓ | ✓ | — | — | — | — | No |
| REL_008 | Pipeline Object Replication | — | ✓ | ✓ | — | — | — | — | — | No |
| **Cost** |
| COST_001 | Aggressive Auto-Suspend | — | ✓ | — | — | — | — | — | — | No |
| COST_002 | Zombie Warehouses | — | ✓ | — | — | — | — | — | — | No |
| COST_003 | Cloud Services Ratio | — | ✓ | — | — | — | — | — | — | No |
| COST_004 | Runaway Query Protection | — | ✓ | — | — | — | — | — | — | No |
| COST_005 | Multi-Cluster Safeguard | — | ✓ | — | — | — | — | — | — | No |
| COST_006 | Underutilized Warehouse | — | ✓ | — | — | — | — | — | — | No |
| COST_007 | Stale Table Detection | — | — | — | — | ✓ | — | — | — | No |
| COST_008 | Staging Table Type Optimization | — | — | — | — | ✓ | — | — | — | No |
| COST_009 | Per-Warehouse Statement Timeout | — | ✓ | — | — | — | — | — | — | No |
| COST_010 | QAS Eligibility Recommendation | — | ✓ | — | — | — | — | — | — | No |
| COST_011 | Workload Heterogeneity | — | ✓ | — | — | — | — | — | — | No |
| COST_012 | High-Churn Permanent Tables | — | — | — | — | ✓ | — | — | — | No |
| COST_013 | Unused Materialized View Detection | — | — | — | — | — | ✓ | — | — | No |
| COST_014 | Automatic Clustering Cost/Benefit | — | — | — | — | ✓ | — | — | — | No |
| COST_015 | Search Optimization Cost/Benefit | — | — | ✓ | ✓ | — | — | — | — | No |
| COST_016 | Data Transfer Monitoring | — | ✓ | — | — | — | — | — | — | No |
| **Strategy** (note: strategy module uses ID COST_012 as well) |
| COST_012 | Isolation Pivot (Elephant Detection) | — | ✓ | — | — | — | — | — | — | No |
| **Operations / op_excellence** |
| OP_001 | Resource Monitoring | — | ✓ | — | — | — | — | — | — | No |
| OP_002 | Object Documentation (DB comment) | — | — | ✓ | — | — | — | — | — | No |
| OPS_001 | Mandatory Tagging | — | ✓ | ✓ | — | — | — | — | — | No |
| OPS_003 | Alert Configuration | — | ✓ | — | — | — | — | — | — | No |
| OPS_005 | SLO Throttler (Oversized) | — | ✓ | — | — | — | — | — | — | No |
| OPS_006 | Resize Churn | — | ✓ | — | — | — | — | — | — | No |
| OPS_007 | Notification Integration | — | ✓ | — | — | — | — | — | — | No |
| OPS_008 | Observability Infrastructure | — | ✓ | ✓ | — | — | — | — | — | No |
| OPS_009 | IaC Drift Readiness | — | ✓ | ✓ | — | — | — | — | — | No |
| OPS_010 | Event Table Configuration | — | ✓ | — | — | — | — | — | — | No |
| OPS_011 | Data Metric Functions Coverage | — | ✓ | — | — | — | — | — | — | No |
| OPS_012 | Alert Execution Reliability | — | ✓ | — | — | — | — | — | — | No |
| **Performance** |
| PERF_001 | Cluster Key Validation | — | — | — | — | ✓ | — | — | — | No |
| PERF_002 | Query Queuing Detection | — | ✓ | — | — | — | — | — | — | No |
| PERF_003 | Remote Spillage | — | ✓ | — | — | — | — | — | — | No |
| PERF_004 | Local Spillage | — | ✓ | — | — | — | — | — | — | No |
| PERF_005 | Poor Partition Pruning Detection | — | — | — | — | ✓ | — | — | — | No |
| PERF_006 | Workload Efficiency (Oversized) | — | ✓ | — | — | — | — | — | — | No |
| PERF_007 | Gen 2 Upgrade Opportunity | — | ✓ | — | — | — | — | — | — | No |
| PERF_008 | Snowpark Optimization | — | ✓ | — | — | — | — | — | — | No |
| PERF_009 | Cache Contention | — | ✓ | — | — | — | — | — | — | No |
| PERF_010 | Dynamic Table Lag | — | — | ✓ | ✓ | ✓ | — | — | — | No |
| PERF_011 | Clustering Key Quality | — | — | — | — | ✓ | — | — | — | No |
| PERF_012 | Warehouse Workload Isolation | — | ✓ | — | — | — | — | — | — | No |
| PERF_013 | Query Latency SLO | — | ✓ | — | — | — | — | — | — | No |
| PERF_003_SMART | Spilling Memory (Undersized) | — | ✓ | — | — | — | — | — | — | No |
| **Static / SQL (file or view DDL)** |
| STAT_001 | Hardcoded Environment | — | — | — | — | — | — | — | — | No (static only) |
| STAT_002 | Naked Drop Statement | — | — | — | — | — | — | — | — | No (static only) |
| STAT_003 | Secret Exposure | — | — | — | — | — | — | — | — | No (static only) |
| **SQL_001** | **No SELECT *** | — | — | — | — | — | **✓** | — | — | **Yes** |
| STAT_004 | MERGE Pattern Recommendation | — | — | — | — | — | — | — | — | No (static only) |
| STAT_005 | Dynamic Table Complexity | — | — | — | — | — | — | — | — | No (static only) |
| STAT_006 | Anti-Pattern SQL Detection | — | — | — | — | — | — | — | — | No (static only) |

---

## View phase subset for online scan

**Exact subset to run per view:** only **SQL_001 (SelectStarCheck)**.

- **SQL_001** is the only rule whose `check_online(cursor, view_name)` uses `_resource_name`: it calls `GET_DDL('VIEW', _resource_name)` and runs the static SELECT * check on that DDL. Running it once per view is correct and necessary.
- Every other rule with `check_online` either:
  - Ignores `_resource_name` and runs a single account-wide (or table/warehouse/role/grant) query, or
  - Has no `check_online` (static-only).

**Recommendation:** During the online view phase, call `check_online(cur, view_fqn)` only for rules that apply to views and use the view name. In the current codebase that is **only SQL_001**. All other rules should run once in the account-level phase (or table/warehouse/etc. phase), not inside it. This is implemented via introspection (`_check_online_uses_resource_name`) so no Rule property is required.

**View-phase database exclusion:** By default, views in **SNOWFLAKE**, **SNOWFLAKE_SAMPLE_DATA**, and **SNOWFORT** databases are excluded from the per-view phase. Use `--include-snowfort-db` when running the audit on the Snowfort project itself so the SNOWFORT database is included.

Implementing this requires (already done via introspection):
1. Adding an attribute on `Rule` (e.g. `applies_to: frozenset[str]` with values like `"account"`, `"view"`) or a boolean `run_per_view: bool`.
2. In the view loop, filtering to rules where `run_per_view` is true (or `"view" in rule.applies_to` and the rule uses `_resource_name`).
3. Running account/table/role/grant rules once before or after the view loop, not inside it.
