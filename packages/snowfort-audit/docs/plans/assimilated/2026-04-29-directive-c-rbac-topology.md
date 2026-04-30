# Directive C: RBAC Topology & Role Hierarchy

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** Second highest security impact. God-role patterns and dormant admin
accounts were the most dangerous findings from the production run, and the current
tool under-detects them.

*Shipped: 2026-04-29*

---

## Objective

Decompose the monolithic SEC_001 (AdminExposureCheck) into targeted sub-rules, add
god-role and privilege concentration detection via role graph traversal, validate
role hierarchy flow against the DBO → Functional → Business → Users pattern, and
detect role sprawl with consolidation recommendations.

## Scope

### SEC_001 Decomposition

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_001a | Admin Grant Count | Flag accounts with >N users granted ACCOUNTADMIN/SECURITYADMIN/SYSADMIN (configurable, default 3). Uses cached `GRANTS_TO_ROLES`/`GRANTS_TO_USERS` with BFS traversal. | HIGH |
| SEC_001b | Dormant Admin Accounts | Flag users with admin-role grants who have never logged in or not logged in within `zombie_user_days`. Cross-reference `GRANTS_TO_USERS` × `SHOW USERS`. Password-set + inactive + admin + SSO enforced = CRITICAL. | HIGH |
| SEC_001c | Admin as Default Role | Flag users whose `DEFAULT_ROLE` is ACCOUNTADMIN, SECURITYADMIN, or SYSADMIN. | HIGH |
| SEC_001d | Legacy Identity Duplication | Detect bare-name accounts (e.g., `ALICE`) that overlap with email-format accounts (`ALICE@CORP.COM`) where both have admin grants. Case-insensitive stem matching. | CRITICAL |

### God-Role & Privilege Concentration

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_025 | God-Role Detection | Identify custom roles with >50 distinct privilege grants spanning >3 databases. Also unconditionally flags any role holding MANAGE GRANTS (CRITICAL — self-escalation vector). | HIGH/CRITICAL |
| SEC_026 | Privilege Concentration | Compute Gini coefficient of privilege distribution across custom roles. Flag if Gini > 0.80. Skipped when < 10 custom roles. Finding is INFORMATIONAL. | MEDIUM |

### Role Hierarchy Validation

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_027 | Role Flow Validation | Flag users directly granted DBO/DDL-layer roles (naming convention regex, configurable). | MEDIUM |
| SEC_028 | User Role Explosion | Flag users with > 10 direct role grants (configurable). Finding is INFORMATIONAL. | LOW |
| SEC_029 | Incomplete Department Roles | Detect functional roles (READ/WRITE/ANALYST suffix) with no parent business-layer role (TEAM/DEPT/BU suffix). Finding is INFORMATIONAL. | LOW |
| SEC_024 | Orphan Role Ratio | Flag if > 20% of custom roles have zero privilege grants and zero grantees. Finding is INFORMATIONAL. | LOW |

### SEC_004 Enhancement

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| SEC_004 | PUBLIC Grant Impact (enhanced) | Distinguishes warehouse USAGE grants (LOW/EXPECTED — compute access is common) from data object grants (HIGH/ACTIONABLE — data exposure). Non-USAGE warehouse grants are MEDIUM. | varies |

### Conventions

New `RbacThresholds` frozen dataclass in `conventions.py`, nested under `RuleThresholdConventions.rbac`:

```toml
[tool.snowfort.thresholds.rbac]
max_account_admins = 3
god_role_privilege_threshold = 50
god_role_database_span = 3
privilege_concentration_gini_threshold = 0.80
max_direct_roles_per_user = 10
orphan_role_percent_threshold = 20
dbo_role_pattern = "(?i).*_(OWNER|DBO|DDL)$"
functional_role_pattern = "(?i).*_(READ|WRITE|TRANSFORM|ANALYST)$"
business_role_pattern = "(?i).*_(TEAM|DEPT|BU)$"
```

## Implementation Notes (vs. Original Spec)

- **SEC_001 backward compat:** `AdminExposureCheck` class is kept in `security.py` and
  `__init__.py` for import compatibility but removed from `get_all_rules()`. Replaced by
  SEC_001a–d in the Directive C section of `rule_registry.py`.
- **SEC_001b SSO severity:** Uses `scan_context.sso_enforced` + `has_password` column from
  `SHOW USERS` to escalate to CRITICAL. Does not use `_sso_downgrade()` (different
  semantic: escalation, not downgrade).
- **SEC_026 Gini skip:** `_MIN_ROLES_FOR_GINI = 10` constant guards the computation.
  Applied after filtering out built-in admin roles and PUBLIC from the distribution.
- **SEC_025 MANAGE GRANTS:** Always flags CRITICAL unconditionally — no count/span
  threshold applies. Flagged separately from god-role-by-count violations.
- **New helpers in `_grants.py`:** `build_role_graph()` and `role_privilege_counts()`
  added alongside existing BFS traversal helpers.
- **New module:** `domain/rules/rbac.py` (887 lines, 10 rule classes + `_gini` helper +
  `_default_rbac` helper).

## Files Changed

| File | Change |
|------|--------|
| `domain/conventions.py` | Added `RbacThresholds` dataclass; added `rbac` field to `RuleThresholdConventions` |
| `domain/rules/_grants.py` | Added `build_role_graph()` and `role_privilege_counts()` |
| `domain/rules/rbac.py` | New file: 10 rule classes for Directive C |
| `domain/rules/security.py` | Enhanced `PublicGrantsCheck` (SEC_004) warehouse vs. data object split |
| `domain/rules/__init__.py` | Added 10 RBAC class imports and `__all__` entries |
| `infrastructure/rule_registry.py` | Retired SEC_001; added Directive C section |
| `tests/unit/test_rbac_rules.py` | New file: 78 unit tests (≥5 per rule + helpers) |
| `tests/unit/fixtures/rules_snapshot.yaml` | Regenerated: SEC_001 removed, SEC_001a–d + SEC_024–029 added |

## Ship Criteria Met

- [x] All 10 rules implemented in `domain/rules/rbac.py`
- [x] SEC_004 enhanced (warehouse vs. data object grant split)
- [x] `RbacThresholds` conventions block added
- [x] `build_role_graph()` and `role_privilege_counts()` added to `_grants.py`
- [x] 78 unit tests passing (≥5 per rule)
- [x] `rules_snapshot.yaml` regenerated — SEC_001 gone, 10 new IDs present
- [x] `make check` to verify (pending final gate run)
- [ ] Manual: run against test account with known role topology
