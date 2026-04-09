# Snowflake WAF Audit Briefing

**Date:** April 8, 2026
**Author:** Noah Goodrich + Cortex Code
**Audience:** Snowflake Admin Team, Data Platform Leadership
**Inputs:** snowfort-audit v0.1.0 scan results, INCLOUDCOUNSEL account

---

## Executive Summary

snowfort-audit v0.1.0 scanned 83 rules against the INCLOUDCOUNSEL account and scored it **3/100 (F)** with **3,764 total violations**. This score is misleading — it's inflated by volume, not severity.

**Strip the noise and the real finding count drops to ~454 meaningful violations.** Of the 3,764:
- 2,602 (69%) are expected CDC behavior in MSWI staging tables — not a problem
- 377 are zombie users — real but low severity with Okta SSO in place
- 331 are missing federated auth — needs triage (many are service accounts)

### What Actually Matters

| Priority | Findings | Action |
|----------|----------|--------|
| **P0 — Do Now** | MFA not enforced account-wide (SEC_016). **7 ACCOUNTADMIN grants across 5 people** including 3 dormant bare-name accounts (SEC_001). 9 users without MFA (SEC_002). No account budget (GOV_003). No Cortex Code cost controls. Permifrost default_role drift (27/28 mismatches). | Active security and financial risk |
| **P1 — This Quarter** | No replication/DR (REL_001). 377 zombie users (SEC_007). 19 PUBLIC grants (SEC_004). 2-hour global query timeout (COST_004). | Real risk, not immediately exploitable |
| **P2 — Next Quarter** | No network policy (SEC_003). No tagging strategy (OPS_001). 8 warehouses with spillage (PERF_004). 331 non-federated users (SEC_011). | Defense-in-depth, optimization |
| **P3 — Backlog** | Auto-suspend tuning. Documentation coverage. Alert configuration. Event table. DMFs. | Governance improvements |
| **Ignore** | 2,602 high-churn MSWI table violations (COST_012) | Expected CDC behavior |

### Top 5 Recommendations

1. **Enforce MFA at account level** — `ALTER ACCOUNT SET ENABLE_MFA_ENFORCEMENT = TRUE;` Review the 9 users without MFA first.
2. **Audit ACCOUNTADMIN grants** — 7 grants across 5 people, including 3 dormant bare-name accounts with passwords and ACCOUNTADMIN that have never logged in and are not disabled. See Appendix E for full breakdown.
3. **Set an account budget** — No spending guardrails exist at the account level.
4. **Set per-warehouse statement timeouts** — Global default is 7200s (2 hours). Drop to 1800s for production, 900s for ad-hoc.
5. **Clean up zombie users** — 377 stale accounts. Disable (don't drop) users inactive 90+ days.

For Cortex Code cost governance findings, see the companion document: [Cortex Code CLI: Cost Governance & Strategic Recommendations](snowfort-strategic-brief.md).

---

## Recommendations

### P0 — Implement Immediately

**1. Enforce MFA at account level**

```sql
ALTER ACCOUNT SET ENABLE_MFA_ENFORCEMENT = TRUE;
```

Review the 9 users flagged by SEC_002 and ensure MFA is enabled before enforcement.

**2. Audit ACCOUNTADMIN grants**

Manual investigation found **7 ACCOUNTADMIN grants across 5 distinct people** — significantly worse than the 3 flagged by snowfort-audit. See Appendix E for the full breakdown.

**Immediate actions (P0):**
- **Disable the 3 dormant bare-name accounts** (EJONES, JKETTERER, TCHOEDAK) — these have passwords set, ACCOUNTADMIN granted, have never logged in, and are not disabled. They are free attack surface.
- **Change default roles for DMURRAY@ONTRA.AI and EJONES@ONTRA.AI** — both default to ACCOUNTADMIN. No one should default to ACCOUNTADMIN.

**This quarter (P1):**
- Consolidate duplicate identities (e.g., EJONES and EJONES@ONTRA.AI both have ACCOUNTADMIN)
- Evaluate whether RAFFI@ONTRA.AI and KSARTWELL@ONTRA.AI still need ACCOUNTADMIN
- Consider implementing a "break-glass" pattern: ACCOUNTADMIN granted to a shared account, used only for emergency operations, with full audit logging

**3. Set an account budget**

```sql
-- Create and activate account budget
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!ACTIVATE();
-- Set monthly spending limit (adjust based on your contract)
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_SPENDING_LIMIT(50000);
-- Configure email notification
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_EMAIL_NOTIFICATIONS('admin@ontra.ai');
```

**4. Review PUBLIC grants**

Audit the 19 objects with PUBLIC grants. For each, determine if PUBLIC access is intentional (shared reference data) or accidental (over-grant). Revoke and re-grant to appropriate roles.

### P1 — This Quarter

**5. Clean up zombie users**

Query to identify candidates:
```sql
SELECT name, login_name, last_success_login, created_on, disabled
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
WHERE last_success_login < DATEADD('day', -90, CURRENT_DATE())
   OR last_success_login IS NULL
ORDER BY last_success_login ASC NULLS FIRST;
```

Disable (don't drop) users who haven't logged in for 90+ days. Review service accounts separately — they may use key-pair auth and never "log in."

**6. Set per-warehouse statement timeouts**

```sql
-- Production warehouses: 30 minutes max
ALTER WAREHOUSE DBT_WH SET STATEMENT_TIMEOUT_IN_SECONDS = 1800;
ALTER WAREHOUSE ETL_WH SET STATEMENT_TIMEOUT_IN_SECONDS = 1800;
ALTER WAREHOUSE ANALYTICS_WH SET STATEMENT_TIMEOUT_IN_SECONDS = 1800;

-- Developer/ad-hoc warehouses: 15 minutes
ALTER WAREHOUSE SNOW_INTELLIGENCE_WH SET STATEMENT_TIMEOUT_IN_SECONDS = 900;

-- Reduce global default from 7200s
ALTER ACCOUNT SET STATEMENT_TIMEOUT_IN_SECONDS = 3600;
```

**7. Evaluate replication for disaster recovery**

This is a business decision, not a technical one. The questions:
- What is the acceptable RPO (Recovery Point Objective)?
- What is the acceptable RTO (Recovery Time Objective)?
- Which databases are critical enough to replicate?
- What is the additional cost of a secondary account?

At minimum, configure replication for the PROD database.

### P2 — Next Quarter

**8. Implement network policy** — Add IP allowlisting as defense-in-depth alongside Okta SSO.

**9. Deploy mandatory tagging strategy** — Start with production warehouses and databases. Use tags for cost attribution by team.

**10. Investigate local spillage** — Profile the 8 warehouses with spillage. Determine if the issue is warehouse sizing or query optimization.

**11. Triage federated auth** — Break down the 331 non-federated users into: active humans (fix), service accounts (document), zombie overlap (clean up).

---

## Appendix A: Audit Scan Results

### What Failed

snowfort-audit v0.1.0 ran 83 rules against the INCLOUDCOUNSEL account. **82 of 83 rules completed successfully.** One rule failed with a SQL error:

| Rule | Error | Root Cause |
|------|-------|------------|
| `SEC_008: Zombie Roles` | `001003 (42000): SQL compilation error: syntax error line 1 at position 29 unexpected 'OPERATIONS'` | snowfort-audit generated SQL referencing `OPERATIONS` as a keyword or object name that doesn't exist in this account's Snowflake version/edition. This is a bug in snowfort-audit's SQL generation, not a problem with your account. |

### DDL Fetch Failures (Expected Noise)

During the `GOV_001: Future Grants Anti-Pattern` rule (and possibly `GOV_004`), snowfort-audit iterated through **7,088 views** in the account to check their DDL definitions. Thousands of these failed with:

```
Database 'DBT_MZUREK__DBT_STAGING_RAW_APP' does not exist or not authorized.
```

**Why this happened:** ACCOUNT_USAGE metadata retains references to objects in databases that have since been dropped. These are developer sandbox dbt databases (e.g., `DBT_MZUREK__*`, `DBT_MZUREK__INTERMEDIATE`, `DBT_MZUREK__REPORT`) that were created by dbt CI/CD runs and later cleaned up. The views no longer exist, but ACCOUNT_USAGE still references them.

**Impact:** None. These errors are expected noise. The rules still completed and produced valid results for existing objects. However, this did significantly slow the scan — the 7,088-view iteration is why the scan took over an hour. A future optimization would be for snowfort-audit to filter out views from non-existent databases before attempting DDL fetches.

### The `connections.toml` Permissions Warning

```
Bad owner or permissions on /Users/noahgoodrich/.snowflake/connections.toml
```

This is a local file permissions warning from the Snowflake Python connector, not a security issue. Fix with `chmod 0600 ~/.snowflake/connections.toml` or suppress with `SF_SKIP_TOKEN_FILE_PERMISSIONS_VERIFICATION=true`.

### Summary

The scan was successful. 82/83 rules ran cleanly. The one failure is a snowfort-audit bug (not an account issue), and the DDL fetch errors are expected metadata noise from dropped developer databases.

---

## Appendix B: Adversarial Review of Audit Results

### The F Grade in Context

snowfort-audit scored the account **3/100 (F)** with **3,764 total violations**. This sounds catastrophic. It is not. Here's why:

**The score is inflated by volume, not severity.** Of 3,764 violations:
- **2,602** (69%) are `COST_012: High-Churn Permanent Tables` and `COST_012: Isolation Pivot (Elephant Detection)` — overwhelmingly MSWI staging tables that are CDC/replication targets. These are **expected behavior**, not a problem.
- **377** are `SEC_007: Zombie Users` — likely stale Snowflake user accounts from departed employees or service accounts that were never cleaned up. Real finding, but LOW severity individually.
- **331** are `SEC_011: Federated Authentication` — users without SSO. Many may be service accounts that correctly use key-pair auth.

**Remove the noise and the real finding count drops to ~454 meaningful violations.**

### Findings I Agree Are Valid and Critical

| Rule | Severity | Finding | Why It's Real |
|------|----------|---------|---------------|
| `SEC_001: Admin Exposure` | CRITICAL | **7 ACCOUNTADMIN grants across 5 people.** snowfort-audit flagged 3, but manual investigation found 7 grants total — including 3 dormant bare-name accounts (EJONES, JKETTERER, TCHOEDAK) with passwords set, ACCOUNTADMIN granted, never logged in, and NOT disabled. See Appendix E. | Direct account takeover risk. The 3 dormant accounts are free attack surface — credentials that exist solely to be compromised. Two active users (DMURRAY, EJONES@ONTRA.AI) have ACCOUNTADMIN as their actual default role despite permifrost declaring otherwise. |
| `SEC_002: MFA Enforcement` | CRITICAL (x9) | 9 users without MFA | Combined with admin exposure, this is the highest-risk finding. A single compromised password = full account access. |
| `SEC_016: MFA Account Enforcement` | CRITICAL | MFA not enforced at account level | Account-level MFA enforcement is the only way to guarantee coverage. Per-user MFA has gaps (new users, service accounts). |
| `REL_001: Replication Gaps` | CRITICAL (x3) | No replication configured | Zero disaster recovery capability. If the account or region goes down, there is no failover. For a production data platform, this is a real risk. |
| `GOV_003: Account Budget Enforcement` | CRITICAL | No account budget | No spending guardrails at the account level. |
| `COST_004: Runaway Query Protection` | HIGH | Global timeout = 7200s (2 hours) | A single bad query can run for 2 hours burning credits. This should be 900-1800s for most warehouses. |
| `SEC_004: Public Grants` | HIGH (x19) | 19 objects with PUBLIC grants | Objects accessible to every user in the account. May be intentional for some (e.g., shared reference data), but likely includes over-grants. |
| `PERF_004: Local Spillage` | HIGH (x8) | 8 warehouses with local spill | Queries are exceeding memory and spilling to local disk. Indicates undersized warehouses or inefficient queries. Costs real money in extended execution time. |

### Findings That Are Red Herrings or Over-Classified

| Rule | Audit Severity | My Assessment | Why |
|------|---------------|---------------|-----|
| `COST_012: High-Churn Permanent Tables` | MEDIUM (x2,602) | **IGNORE** | These are overwhelmingly MSWI CDC staging tables (`MSWI.ICC_APP_PROD_*_STAGING.*`, `MSWI.ATLAS_*_STAGING.*`). Fail-safe bytes exceeding active bytes is the expected pattern for tables receiving frequent small inserts/updates via Fivetran or similar CDC tools. The data is being replicated correctly. Converting these to transient tables would save some fail-safe storage but risk data loss. |
| `COST_001: Aggressive Auto-Suspend` | MEDIUM (x8) | **MOSTLY IGNORE** | snowfort-audit's convention is 1s auto-suspend. That's aggressive to the point of being counterproductive — warehouses that suspend in 1s will cold-start on every query, consuming cloud services credits for provisioning. The current settings (6s for most warehouses, 45s for ANALYTICS_WH, 300s for SNOW_INTELLIGENCE_WH) are reasonable. Only SNOW_INTELLIGENCE_WH at 300s warrants review. |
| `SEC_003: Network Perimeter` | CRITICAL | **CONTEXT-DEPENDENT** | The audit flags no network policy. But if all access is via Okta SSO (which the login flow confirms — `ontra.okta.com`), the identity perimeter IS the network perimeter. A network policy adds defense-in-depth but is not as critical as the audit implies when SSO is already enforced. Recommend implementing one, but this is not a "the building is on fire" critical. |
| `OPS_001: Mandatory Tagging` | CRITICAL (x53) | **VALID BUT OVERSTATED** | Tagging is a governance best practice, not a security emergency. The 53 untagged warehouses include dev warehouses, CI/CD warehouses, and system-managed warehouses (COMPUTE_SERVICE_WH_*). Tagging production warehouses is the priority; tagging everything is nice-to-have. |
| `SEC_007: Zombie Users` | HIGH (x377) | **VALID, LOWER SEVERITY** | 377 is a lot of stale users. But with SSO/Okta as the identity provider, these users can't actually log in unless they have an active Okta account. The risk is lower than in a password-auth environment. Still should be cleaned up for hygiene, but this is not an active exploit vector. |
| `SEC_011: Federated Authentication` | MEDIUM (x331) | **NEEDS TRIAGE** | 331 users without federated auth. How many are service accounts (correctly using key-pair)? How many are former employees (zombie overlap with SEC_007)? How many are active humans not using SSO? The raw number is meaningless without this breakdown. |

### What the Audit Missed

snowfort-audit v0.1.0 has no rules for:

1. **AI/Cortex Cost Governance** — No assessment of Cortex Code, Cortex AI Functions, Cortex Agents, or Snowflake Intelligence spending. This is the fastest-growing cost category and has zero guardrails.

2. **Developer Sandbox Sprawl** — The DDL fetch failures reveal dozens of dropped `DBT_*` databases. Are new ones being created and abandoned? Is there a lifecycle policy? The audit can't tell.

3. **Data Sharing / Marketplace Risk** — No assessment of inbound or outbound shares, marketplace listings, or data exchange exposure.

4. **Cross-Region Inference** — CoCo requires cross-region inference. Is this enabled? What data residency implications does it create?

5. **Cortex Agent Resource Budgets** — Cortex Agents have their own budget mechanisms separate from warehouse resource monitors. Are they configured?

6. **Snowflake Intelligence Usage** — Is SI being used appropriately? Is it duplicating work that semantic views should handle?

7. **Dynamic Table Health** — No assessment of dynamic table refresh status, lag, or failures.

8. **Sensitive Data Classification** — `GOV_004` flags 50 tables without classification, but doesn't assess whether classified tables have appropriate masking policies applied.

9. **Permifrost / IaC Drift Detection** — No assessment of whether the declared permissions state (permifrost YAML) matches actual Snowflake state. Manual investigation found 27 of 28 data users have a different `default_role` in Snowflake than what permifrost declares. Permifrost's `meta.default_role` is effectively declarative fiction — likely overwritten by Okta SCIM on every login. See Appendix E.

---

## Appendix C: snowfort-audit Configuration

For faster future scans, use parallel workers:

```bash
snowfort audit scan --workers 4
```

The scan also supports `--manifest` for JSON output consumable by CI/CD:

```bash
snowfort audit scan --manifest > audit_results.json
```

---

## Appendix D: Key Data References

- **Audit report:** `/Users/noahgoodrich/dev/snowfort-audit-report.yaml`
- **snowfort-audit PyPI:** https://pypi.org/project/snowfort-audit/
- **Companion document (Cortex Code cost governance):** `snowfort-strategic-brief.md`

---

## Appendix E: ACCOUNTADMIN Exposure & Permifrost Drift (Manual Investigation)

*Findings from manual Snowflake queries on April 8, 2026. These go beyond what snowfort-audit flagged.*

### ACCOUNTADMIN Grants: 7 Grants Across 5 People

snowfort-audit's SEC_001 flagged 3 ACCOUNTADMIN users. Manual query of `SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS` found **7 grants across 5 distinct people**, including legacy bare-name accounts:

| User | Granted On | Default Role | Last Login | Status | Priority |
|------|-----------|-------------|------------|--------|----------|
| EJONES | 2024-10-09 | data | **Never** | Has password, NOT disabled | **P0 — Disable immediately** |
| JKETTERER | 2021-10-22 | RAD DATA | **Never** | Has password, NOT disabled | **P0 — Disable immediately** |
| TCHOEDAK | 2024-10-09 | data | **Never** | Has password, NOT disabled | **P0 — Disable immediately** |
| DMURRAY@ONTRA.AI | 2025-09-19 | ACCOUNTADMIN | Apr 8, 2026 | Active | **P1 — Change default role** |
| EJONES@ONTRA.AI | 2022-06-08 | ACCOUNTADMIN | Apr 1, 2026 | Active | **P1 — Change default role** |
| KSARTWELL@ONTRA.AI | 2025-08-22 | DATA_ENG_ADMIN | Active | Active | P2 — Evaluate need |
| RAFFI@ONTRA.AI | 2021-10-22 | PUBLIC | Jan 2026 | Active | P2 — Evaluate need |

**Key risks:**

1. **3 dormant bare-name accounts (EJONES, JKETTERER, TCHOEDAK)** have passwords set, ACCOUNTADMIN granted, have never logged in, and are not disabled. These are credentials that exist solely to be compromised. They should be disabled immediately.

2. **Legacy/Okta identity duplication**: EJONES exists as both a bare-name account (dormant, with ACCOUNTADMIN + password) and EJONES@ONTRA.AI (active, with ACCOUNTADMIN, last login Apr 1). This is likely a migration artifact where the Okta identity was created but the legacy identity was never cleaned up.

3. **DMURRAY and EJONES@ONTRA.AI default to ACCOUNTADMIN** in Snowflake, meaning every session they open starts with full admin privileges. Permifrost declares `default_role: data_admin` for both, but Snowflake ignores this (see drift analysis below).

### Permifrost `default_role` Drift: 27 of 28 Users Mismatched

Comparison of `meta.default_role` in `data_users.yml.j2` against actual `DEFAULT_ROLE` in `SNOWFLAKE.ACCOUNT_USAGE.USERS`:

**Only 1 of 28 users matches: ADOGGETT** (permifrost: `data`, actual: `DATA`).

| Pattern | Count | Examples |
|---------|-------|---------|
| Permifrost says X, Snowflake says PUBLIC | 10 | DARENSON, JSNYDER, PCHIU, ZSLAVIN, etc. |
| Permifrost says X, Snowflake says CLAUDE_DESKTOP_MCP | 3 | ASCHARIFKER, HGUAN, TSAKOTA |
| Permifrost says X, Snowflake says ACCOUNTADMIN | 2 | DMURRAY, EJONES |
| Permifrost says X, Snowflake says different role | 10 | NGOODRICH (data → DATA_ENG_ADMIN), etc. |
| No default_role in permifrost | 2 | TWONG, YLIU |

**Root cause:** Okta SCIM provisioning likely overwrites `DEFAULT_ROLE` on every login or sync. Permifrost's `meta.default_role` is declarative fiction — it has no enforcement mechanism against SCIM overwrites.

**Impact:** The `default_role` setting in permifrost YAML creates a false sense of governance. Anyone reviewing the YAML would believe DMURRAY defaults to `data_admin`, when in reality DMURRAY defaults to `ACCOUNTADMIN`.

**Recommendation:** Either fix the SCIM integration to respect permifrost's declared roles, or remove `meta.default_role` from permifrost to eliminate the false confidence. The current state is worse than having no declaration at all — it actively misleads.
