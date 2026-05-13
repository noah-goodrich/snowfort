# Directive E: IaC Drift Detection + dbt Grant Analysis

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** Medium. IaC drift creates false governance confidence — you think you're
managing access in code, but interactive changes have diverged. dbt grant analysis is
a targeted check that catches a common misconfiguration (grants to business roles
instead of functional roles).

---

## Objective

Detect what IaC tools are in play (pattern-based, not parsing), identify likely drift
indicators, and validate dbt grant patterns target functional roles. Provide an
interactive questionnaire mode where Cortex Code can ask the user about their IaC
setup to improve detection accuracy.

## Scope

### IaC Tool Detection

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| OPS_015 | IaC Tool Detection | Detect IaC tool presence via configurable indicators: MANAGED_BY tags, query comments (e.g., `/* terraform */`, `dbt`), service account naming patterns (e.g., `SVC_TERRAFORM`, `SVC_DBT`), and scheduled task patterns. Report detected tools as INFORMATIONAL. | INFORMATIONAL |
| OPS_016 | IaC Drift Indicators | Per detected tool, check for common drift signals. See table below. | varies |

**Per-tool drift indicators:**

| Tool | Drift Signal | Check Method |
|------|-------------|--------------|
| Terraform / Pulumi | Objects with MANAGED_BY tag but modified by non-service-account user in last 30 days | `ACCESS_HISTORY` + `TAG_REFERENCES` |
| Permifrost / Snowflake Grants | Roles/grants created interactively (not by service account) after IaC tool adoption date | `QUERY_HISTORY` filtered by DDL statements |
| dbt | Tables/views in dbt-managed schemas modified by non-dbt user | `QUERY_HISTORY` + schema pattern detection |
| SchemaChange | Migration scripts executed out of order or manually | `QUERY_HISTORY` + comment pattern detection |
| Generic | Objects without MANAGED_BY tag in databases that have >50% tagged objects | `TAG_REFERENCES` coverage gap |

### dbt Grant Analysis

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| GOV_025 | dbt Grant Target Validation | Detect dbt grant patterns (via `QUERY_HISTORY` comment parsing or `grants:` in dbt project config if path provided). Flag grants that target business roles directly instead of functional roles. dbt should grant to functional roles; business roles inherit via hierarchy. | MEDIUM |
| GOV_026 | dbt Schema Ownership | Detect schemas created by dbt service account. Flag if schema owner is the service account itself (anti-pattern) instead of a dedicated DBO role. | LOW |

### Interactive Questionnaire Mode

When run via Cortex Code (`--cortex` flag), the tool can output structured questions
in the manifest JSON that Cortex Code presents to the user:

```json
{
  "questionnaire": [
    {
      "id": "iac_tools",
      "question": "Which IaC tools manage your Snowflake account?",
      "options": ["Terraform", "Pulumi", "Permifrost", "dbt", "SchemaChange", "None", "Other"],
      "multi_select": true
    },
    {
      "id": "iac_adoption_date",
      "question": "When did you adopt IaC for Snowflake? (approximate)",
      "type": "date"
    },
    {
      "id": "dbt_project_path",
      "question": "Path to your dbt project (for grant analysis)?",
      "type": "path",
      "optional": true
    }
  ]
}
```

User responses refine the drift analysis:
- Known tools → targeted drift checks instead of broad detection
- Adoption date → only flag post-adoption interactive changes
- dbt path → parse `dbt_project.yml` for grant config instead of inferring from
  query history

### Conventions

```toml
[tool.snowfort.thresholds.iac_drift]
# Regex patterns for IaC service account names (configurable)
iac_service_account_pattern = "(?i)(SVC_TERRAFORM|SVC_PULUMI|SVC_DBT|SVC_SCHEMACHANGE|SVC_PERMIFROST|DATAOPS_)"
# Regex patterns for IaC query comments
iac_comment_patterns = [
    "(?i)terraform",
    "(?i)pulumi",
    "(?i)dbt",
    "(?i)schemachange",
    "(?i)permifrost",
]
# Minimum tag coverage to consider a database "IaC-managed"
managed_tag_coverage_threshold = 0.50
# Days to look back for drift detection
drift_lookback_days = 30

[tool.snowfort.thresholds.dbt_grants]
# Regex for functional role names (grants should target these)
functional_role_pattern = "(?i).*_(READ|WRITE|TRANSFORM|ANALYST|LOADER)$"
# Regex for business role names (grants should NOT target these directly)
business_role_pattern = "(?i).*_(TEAM|DEPT|BU|BUSINESS)$"
```

## Key Design Decisions

1. **Detection, not parsing.** We detect IaC tool presence via patterns and
   indicators. We do NOT parse Terraform state files, Pulumi stacks, or
   Permifrost specs. That's fragile and out of scope. The one exception is dbt
   `grants:` config — if a dbt project path is provided, we parse the YAML for
   grant targets.

2. **Pattern-based, not hard-coded.** All service account names, query comment
   patterns, and role names use configurable regex in conventions. No hard-coded
   tool names beyond the defaults.

3. **Interactive questionnaire is additive.** Without user input, rules still
   work — they just use broader heuristics. User answers narrow the scope and
   improve accuracy. The questionnaire is emitted in manifest JSON for Cortex
   Code to consume.

4. **Drift indicators are probabilistic, not definitive.** A non-service-account
   user modifying a tagged object is a *signal*, not proof of drift. Findings
   are `category=ACTIONABLE` with context explaining the heuristic.

5. **dbt grants analysis is security, not style.** Granting directly to business
   roles bypasses the functional-role layer and breaks least-privilege. This is
   a governance finding (GOV), not an operations finding.

## TDD Requirements

Every rule requires:
1. Unit test with mock `QUERY_HISTORY` / `TAG_REFERENCES` / `ACCESS_HISTORY`
   data asserting correct detection
2. Unit test: no IaC tools detected → OPS_015 reports INFORMATIONAL "No IaC
   tools detected; consider adopting infrastructure-as-code for Snowflake"
3. Unit test: configurable patterns from conventions override defaults

OPS_016 additionally requires:
4. Parametrized test per tool type: given mock data matching tool pattern,
   assert correct drift signal detection
5. Unit test: object modified by IaC service account → no drift finding
6. Unit test: object modified by human user → drift finding

GOV_025 additionally requires:
7. Unit test: grant to functional role → no violation
8. Unit test: grant to business role → violation with recommendation
9. Unit test: dbt project path provided → parse grants config

Questionnaire:
10. Unit test: `--cortex` flag → manifest includes `questionnaire` field
11. Unit test: questionnaire responses narrow drift analysis scope

## Ship Definition

1. PR with OPS_015, OPS_016, GOV_025, GOV_026
2. `make check` passes
3. Questionnaire JSON schema documented
4. Manual: run against test account with known IaC tools, verify detection

## Risks

| Risk | Mitigation |
|------|------------|
| `QUERY_HISTORY` comment parsing is fragile | Use as signal, not proof; combine with other indicators |
| IaC tools may use different service accounts than convention | Document how to configure; questionnaire mode lets user specify |
| dbt project path may not be accessible from Snowflake connection | Path is optional; fall back to query history analysis |
| Drift detection false positives from legitimate manual overrides | Category=ACTIONABLE with context explaining the heuristic; user can dismiss |
