# Directive C: RBAC Topology & Role Hierarchy

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** Second highest security impact. God-role patterns and dormant admin
accounts were the most dangerous findings from the production run, and the current
tool under-detects them.

---

## Objective

Decompose the monolithic SEC_001 (AdminExposureCheck) into targeted sub-rules, add
god-role and privilege concentration detection via role graph traversal, validate
role hierarchy flow against the DBO → Functional → Business → Users pattern, and
detect role sprawl with consolidation recommendations.

## Scope

### SEC_001 Decomposition

The current SEC_001 does too much and too little simultaneously. Decompose into:

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_001a | Admin Grant Count | Flag accounts with >N users granted ACCOUNTADMIN/SECURITYADMIN/SYSADMIN (configurable, default 3). Query `GRANTS_TO_USERS` in ACCOUNT_USAGE, not just active grants. | HIGH |
| SEC_001b | Dormant Admin Accounts | Flag users with admin-role grants who have never logged in or not logged in within `zombie_user_days`. Cross-reference `GRANTS_TO_USERS` × `LOGIN_HISTORY`. Password-set + never-logged-in + admin = CRITICAL. | CRITICAL |
| SEC_001c | Admin as Default Role | Flag users whose `DEFAULT_ROLE` is ACCOUNTADMIN or SECURITYADMIN. Admin roles should never be default. | HIGH |
| SEC_001d | Legacy Identity Duplication | Detect bare-name accounts (e.g., `JOHN_DOE`) that overlap with email-format accounts (e.g., `john.doe@company.com`) where both have admin grants. Common during SSO migration — the bare-name account becomes an unmonitored backdoor. | CRITICAL |

### God-Role & Privilege Concentration

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_025 | God-Role Detection | Identify custom roles with >N distinct privilege grants (configurable, default 50) spanning >M databases (default 3). A role that can do everything is a role that should not exist. Uses `GRANTS_TO_ROLES` graph traversal. | HIGH |
| SEC_026 | Privilege Concentration | Compute Gini coefficient of privilege distribution across roles. Flag if top 10% of roles hold >80% of all privileges. Recommend redistribution. | MEDIUM |

### Role Hierarchy Validation

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_027 | Role Flow Validation | Validate that role hierarchy follows DBO → Functional → Business → Users pattern. Flag roles that skip layers (e.g., user directly granted a DBO role). Detection via naming convention regex (configurable). | MEDIUM |
| SEC_028 | User Role Explosion | Flag users with >N direct role grants (configurable, default 10). When multiple users share the same sprawl pattern (same set of >N roles), recommend a consolidating business role. | LOW |
| SEC_029 | Incomplete Department Roles | Detect functional roles with no business role parent — orphaned in the hierarchy, likely bypassing access governance. | LOW |
| SEC_024 | Orphan Role Ratio | Flag if >N% of custom roles have zero grants to users or other roles (configurable, default 20%). Dead roles clutter the hierarchy and confuse auditors. | LOW |

### SEC_004 Enhancement

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_004 | PUBLIC Grant Impact (enhanced) | Existing rule finds PUBLIC grants. Enhance to distinguish warehouse grants (allow compute but not data access) from table/view grants (data exposure). Warehouse PUBLIC grants are EXPECTED in some architectures. Table/view PUBLIC grants are ACTIONABLE. | varies |

### Conventions

New convention block:
```toml
[tool.snowfort.thresholds.rbac]
max_account_admins = 3
god_role_privilege_threshold = 50
god_role_database_span = 3
privilege_concentration_gini_threshold = 0.80
max_direct_roles_per_user = 10
orphan_role_percent_threshold = 20
# Regex patterns for role hierarchy layers (configurable, not hard-coded)
dbo_role_pattern = "(?i).*_(OWNER|DBO|DDL)$"
functional_role_pattern = "(?i).*_(READ|WRITE|TRANSFORM|ANALYST)$"
business_role_pattern = "(?i).*_(TEAM|DEPT|BU)$"
```

## Key Design Decisions

1. **Graph traversal, not flat queries.** God-role detection and privilege
   concentration require walking the `GRANTS_TO_ROLES` hierarchy. Use
   `ScanContext.get_or_fetch()` to cache the grants graph once, then traverse
   in-memory for all RBAC rules.

2. **Role hierarchy detection via configurable regex patterns.** The DBO →
   Functional → Business → Users pattern is detected by matching role names
   against configurable regex in conventions. No hard-coded role name lists.
   Organizations with different naming can override patterns.

3. **SEC_001 decomposition preserves backward compatibility.** The original
   SEC_001 rule ID is retired. SEC_001a/b/c/d are new rule IDs. The
   `rules_snapshot.yaml` reflects this change.

4. **Gini coefficient for privilege concentration.** A single number that
   captures "how unevenly are privileges distributed?" Standard statistical
   measure, interpretable, comparable across accounts.

5. **Consolidation recommendations are INFORMATIONAL.** SEC_026 detects role
   sprawl and suggests a consolidating role, but the suggestion is
   `category=INFORMATIONAL` — it's a recommendation, not a violation.

## TDD Requirements

Every rule requires:
1. Unit test with mock grants graph asserting correct violation detection
2. Unit test with `sso_enforced=True/False` asserting severity adjustment
   (SEC_001b dormant accounts are more critical when SSO is on — password
   accounts become anomalous)
3. Unit test asserting configurable thresholds from conventions
4. Integration test: grants graph with known topology → correct hierarchy
   validation results

SEC_025/026 additionally require:
5. Unit test with synthetic privilege distributions asserting Gini calculation
6. Edge case: role with MANAGE GRANTS (can self-elevate) → always flagged
   regardless of grant count

## Ship Definition

1. PR with decomposed SEC_001 and all new RBAC rules
2. `make check` passes
3. Old SEC_001 removed from `rules_snapshot.yaml`, replaced by SEC_001a-d
4. Manual: run against test account, verify god-role detection works with
   known role topology

## Risks

| Risk | Mitigation |
|------|------------|
| `GRANTS_TO_ROLES` / `GRANTS_TO_USERS` can be very large | Aggregate server-side; fetch role-to-role and role-to-user edges only |
| Role naming varies wildly across organizations | All hierarchy detection is convention-regex based; document how to configure |
| Gini coefficient may not be meaningful with <10 roles | Skip privilege concentration check if <10 custom roles; note in finding |
| SEC_001 decomposition is a breaking change for users tracking rule IDs | Document in release notes; provide migration note in changelog |
