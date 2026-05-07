---
name: snowfort-audit-interactive
description: >
  Interactive remediation planning session for Snowflake WAF audit findings.
  Runs the audit, triages findings conversationally, challenges false positives,
  builds a prioritized remediation plan, and optionally executes SQL fixes.
tools:
  - shell
  - file_read
  - file_write
  - snowflake_execute
---

# Snowfort Audit — Interactive Remediation Session

## When to use this skill

Invoke when the user says any of:
- "run interactive audit"
- "plan remediation"
- "help me fix the audit findings"
- "walk me through the audit"
- "audit triage session"
- "triage snowfort findings"

This skill drives a **multi-phase remediation session** — not a one-shot report. You will converse
with the user to filter, challenge, prioritize, and optionally execute fixes.

---

## Step 0 — Run the Audit and Load Findings

Run the audit with manifest output. The banner prints to stdout before the JSON, so extract the
JSON portion:

```bash
snowfort audit scan --manifest --no-tui --auto 2>/dev/null | sed -n '/^[\[{]/,$p' > /tmp/snowfort_manifest.json
```

If `sed` extraction fails, look for the first line starting with `{` or `[` in the output.

Parse the JSON. The manifest is `{"violations": [...], "metadata": {"account_id": ...}}`.
Each violation object has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | string | e.g. `SEC_003`, `COST_001` |
| `resource_name` | string | Affected Snowflake object |
| `message` | string | What was found |
| `severity` | string | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `pillar` | string | May be empty — derive from rule_id prefix: SEC→Security, COST→Cost, PERF→Performance, OPS→Operations, GOV→Governance, REL→Reliability |
| `remediation_instruction` | string or null | SQL or action to fix the issue |
| `remediation_key` | string or null | Stable identifier for the fix type |
| `category` | string | `ACTIONABLE`, `EXPECTED`, `INFORMATIONAL` |
| `context` | string | Rule rationale |
| `blast_radius` | int or null | null = Account-level, 1 = per-object |
| `quick_win` | bool | True if `remediation_key` is set |

Store the parsed violations in memory. This is your working dataset for all phases.

Print a summary to start the session:

```
Loaded N findings: X CRITICAL, Y HIGH, Z MEDIUM, W LOW
Pillars affected: Security (N), Cost (N), ...
Quick wins available: N findings with remediation SQL ready

What would you like to focus on? (e.g., "show critical findings", "focus on Security",
"what should I fix first?")
```

---

## Phase 1 — Conversational Triage

Answer user queries purely from the in-memory manifest. **Do not re-scan** unless the user
explicitly says "re-scan" or "run again".

### Supported query types

| User intent | Example | How to answer |
|-------------|---------|---------------|
| Filter by pillar | "show me Security findings" | Filter where `pillar` matches (case-insensitive) |
| Filter by severity | "what's CRITICAL?" | Filter where `severity` matches |
| Filter by resource | "anything about COMPUTE_WH?" | Filter where `resource_name` contains the substring |
| Filter by rule | "explain COST_001" | Find the violation, show `message`, `context`, `remediation_instruction` |
| Count / summary | "how many HIGH findings?" | Count and group by pillar |
| Worst first | "what should I fix first?" | Sort by severity DESC (CRITICAL→HIGH→MEDIUM→LOW), then by pillar priority (Security first) |
| Savings estimate | "which cost rules have savings?" | Filter findings where `message` contains `$`, `credit`, or `savings` |

### Output format for findings

When showing findings, use this format:

```
[SEVERITY] RULE_ID — resource_name
  Message: <message>
  Remediation: <remediation_instruction or "No automated fix available">
  Category: <category>
```

Group by pillar when showing more than 5 findings. Always show the count at the top.

---

## Phase 2 — Challenge Mode

When the user says "is this a false positive?", "why is this flagged?", "challenge this",
or "does this apply?":

### Standard challenge flow

1. **State the rationale**: Show the `context` field (rule rationale) and explain why this rule
   exists in the Well-Architected Framework.

2. **Ask**: "Does this apply to your environment? (yes / no / not sure)"

3. **If no (false positive)**:
   - Mark the finding as accepted (add to `accepted[]` in the plan — see Phase 3).
   - Explain how to suppress it by adjusting thresholds in `pyproject.toml`:
     ```toml
     [tool.snowfort.conventions.thresholds]
     # Example: raise the auto_suspend threshold to allow 600s
     warehouse_auto_suspend_max_seconds = 600

     [tool.snowfort.conventions.thresholds.high_churn]
     # Example: raise churn threshold for CDC-heavy workloads
     row_churn_ratio = 200.0
     ```
   - Or by excluding the rule from future scans: `snowfort audit scan --rule <other_rules>`

4. **If not sure**: Run the investigation SQL for that rule (see table below).

### Investigation SQL for commonly challenged rules

When the user challenges a finding and wants to investigate, run the appropriate SQL:

**COST_001 — Auto-Suspend too long**
```sql
-- Check current auto_suspend setting
SHOW PARAMETERS LIKE 'AUTO_SUSPEND' IN WAREHOUSE <warehouse_name>;
-- Check query frequency to see if long suspend is justified
SELECT DATE_TRUNC('hour', START_TIME) AS hr, COUNT(*) AS queries
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE WAREHOUSE_NAME = '<warehouse_name>'
  AND START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY hr ORDER BY hr;
```

**COST_012 — High Churn Permanent Table**
```sql
-- Check if table name matches CDC/staging patterns
SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, ROW_COUNT, BYTES
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE TABLE_NAME ILIKE '%<resource_name>%' AND DELETED IS NULL;
-- If the table name contains CDC, STAGING, STG, RAW, or LANDING — it's likely expected churn.
-- Suppress via: [tool.snowfort.conventions.thresholds.high_churn] row_churn_ratio = 200.0
```

**SEC_003 — Network Perimeter / Network Policy**
```sql
-- Check if a network policy exists at all
SHOW NETWORK POLICIES;
-- Check if network policy is applied to the account
SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN ACCOUNT;
```

**SEC_004 / SEC_019 — MFA Enforcement**
```sql
-- Check which users have MFA enabled
SELECT NAME, LOGIN_NAME, HAS_MFA, EXT_AUTHN_DUO, DEFAULT_ROLE
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
WHERE DELETED_ON IS NULL
ORDER BY HAS_MFA ASC;
```

**SEC_007 — Zombie Users (no login in N days)**
```sql
-- Check actual last login times
SELECT u.NAME, u.LOGIN_NAME, u.DEFAULT_ROLE,
       MAX(lh.EVENT_TIMESTAMP) AS last_login
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY lh
  ON u.LOGIN_NAME = lh.USER_NAME
WHERE u.DELETED_ON IS NULL
GROUP BY u.NAME, u.LOGIN_NAME, u.DEFAULT_ROLE
ORDER BY last_login ASC NULLS FIRST;
-- Users with NULL last_login have never logged in.
-- Suppress threshold: [tool.snowfort.conventions.thresholds] zombie_user_days = 180
```

**OPS_001 — Resource Monitor Missing**
```sql
-- Check existing resource monitors
SHOW RESOURCE MONITORS;
-- Check if warehouses are covered
SELECT WAREHOUSE_NAME, RESOURCE_MONITOR
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES
WHERE DELETED_ON IS NULL;
```

**OPS_009 — IaC Drift Readiness (no MANAGED_BY tags)**
```sql
-- Check if any MANAGED_BY tags exist
SELECT DOMAIN, OBJECT_NAME, TAG_NAME, TAG_VALUE
FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE TAG_NAME ILIKE '%MANAGED%' OR TAG_NAME ILIKE '%SOURCE%' OR TAG_NAME ILIKE '%TERRAFORM%'
LIMIT 20;
```

**PERF_005 — Local Spillage**
```sql
-- Check which queries are spilling to local storage
SELECT QUERY_ID, WAREHOUSE_NAME, WAREHOUSE_SIZE,
       BYTES_SPILLED_TO_LOCAL_STORAGE, BYTES_SPILLED_TO_REMOTE_STORAGE,
       TOTAL_ELAPSED_TIME / 1000 AS elapsed_sec
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE BYTES_SPILLED_TO_LOCAL_STORAGE > 0
  AND START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY BYTES_SPILLED_TO_LOCAL_STORAGE DESC
LIMIT 10;
-- If spilling is from a small warehouse running large queries, upsize the warehouse.
```

**PERF_006 — Remote Spillage / Warehouse Oversizing**
```sql
-- Check P50 vs P95 query duration spread (burst detection)
SELECT WAREHOUSE_NAME,
       APPROX_PERCENTILE(TOTAL_ELAPSED_TIME, 0.50) / 1000 AS p50_sec,
       APPROX_PERCENTILE(TOTAL_ELAPSED_TIME, 0.95) / 1000 AS p95_sec,
       COUNT(*) AS query_count
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME = '<warehouse_name>'
GROUP BY WAREHOUSE_NAME;
-- Large P95/P50 ratio suggests burst workload — may justify current sizing.
```

**GOV_001 — Object Documentation (missing comments)**
```sql
-- Check comment coverage for tables
SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COMMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE DELETED IS NULL AND COMMENT IS NULL
  AND TABLE_CATALOG NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA')
LIMIT 20;
```

Replace `<warehouse_name>` and `<resource_name>` with the actual resource from the finding.

---

## Phase 3 — Remediation Plan Builder

Maintain a plan in memory with three lists:

- **`remediate`** — findings to fix (with remediation SQL)
- **`deferred`** — findings postponed with a reason
- **`accepted`** — findings accepted as-is (false positives or by-design)

### Plan commands

| User intent | Example | Action |
|-------------|---------|--------|
| Add to plan | "add this to the plan" / "fix this" | Append finding to `remediate[]` |
| Defer | "defer this for next quarter" | Append to `deferred[]` with reason |
| Accept risk | "accept this, it's by design" | Append to `accepted[]` with reason |
| Show plan | "show the plan" / "what's in the plan?" | Print current plan state |
| Prioritize | "order by business impact" | Sort `remediate[]` by severity then estimated savings |
| Save plan | "save the plan" | Write `remediation_plan.yaml` (see schema below) |
| Clear plan | "start over" | Reset all three lists |

### Plan YAML schema

When the user says "save the plan", write `remediation_plan.yaml`:

```yaml
# remediation_plan.yaml — generated by snowfort interactive session
generated_at: "2026-05-01T09:00:00"
scan_summary:
  total_findings: 42
  critical: 3
  high: 11
  medium: 18
  low: 10

remediate:
  - rule_id: SEC_003
    rule_name: Network Perimeter
    severity: CRITICAL
    resource: Account
    message: "No Account-level Network Policy set"
    remediation_instruction: |
      CREATE NETWORK POLICY corp_network_policy
        ALLOWED_IP_LIST = ('203.0.113.0/24');
      ALTER ACCOUNT SET NETWORK_POLICY = corp_network_policy;
    notes: "Apply after VPN IP range confirmed with IT."

deferred:
  - rule_id: COST_006
    resource: ETL_WH
    reason: "Warehouse is intentionally oversized for Q2 ETL sprint. Revisit Q3."

accepted:
  - rule_id: COST_001
    resource: BI_WH
    reason: "BI_WH requires 300s suspend for Tableau cache warmth."
```

Use the actual findings data from the manifest. The `notes` field is optional — include it if the
user provided context during the session.

---

## Phase 4 — Execution Loop (Optional)

Only enter this phase if the user says "apply the plan", "run the fixes", "execute", or similar.
**Do not offer to execute unless asked.**

### Execution flow

1. Show all `remediation_instruction` SQL from `remediate[]` as a numbered list:
   ```
   1. [SEC_003] CREATE NETWORK POLICY ...
   2. [COST_001] ALTER WAREHOUSE ... SET AUTO_SUSPEND = 300;
   3. [PERF_005] ALTER WAREHOUSE ... SET WAREHOUSE_SIZE = 'LARGE';
   ```

2. Ask: "Apply all? (yes / pick numbers / no)"

3. For each confirmed item, execute via `sql_execute` tool.

4. After each execution, show the result and ask: "Mark as done? (yes / retry / skip)"

5. After all items: suggest a verification re-scan:
   ```
   snowfort audit scan --rule SEC_003 --rule COST_001 --rule PERF_005 --no-tui --auto
   ```

### Safety rules — FOLLOW THESE STRICTLY

- **ACCOUNT-scoped DDL** (ALTER ACCOUNT, NETWORK POLICY, CREATE USER): Always show the SQL first,
  then ask: "This affects account-level security. Confirm execution? (yes / no)". Require explicit
  "yes".

- **DROP statements**: Always show the SQL first, then ask: "This will permanently delete an object.
  Are you sure? (yes / no)". Require explicit "yes".

- **GRANT / REVOKE on ACCOUNTADMIN**: Always warn: "This modifies admin-level privileges. Confirm?
  (yes / no)".

- **Always show SQL before executing.** Never execute silently.

- **If execution fails**: Show the error, suggest the fix (common: insufficient privileges, object
  doesn't exist), and ask if the user wants to retry or skip.

---

## Phase 5 — Session Output

When the user says "done", "exit", "save and quit", or the conversation ends naturally:

1. **Write the plan** if not already saved:
   ```
   Writing remediation_plan.yaml...
   ```

2. **Print commit suggestion**:
   ```
   git add remediation_plan.yaml
   git commit -m "chore: snowfort audit remediation plan $(date +%Y-%m-%d)"
   ```

3. **Print summary**:
   ```
   Session complete:
     Remediate: N findings queued
     Deferred:  M findings postponed
     Accepted:  K findings accepted as-is
     Executed:  E fixes applied (if any)
   ```

---

## Suppression Reference

When users want to permanently suppress a finding, explain the `pyproject.toml` convention override
mechanism. There is no per-rule exclusion — users adjust thresholds to make rules more permissive
for their environment.

### How to override thresholds

Add to the project's `pyproject.toml`:

```toml
[tool.snowfort.conventions.thresholds]
# Raise auto_suspend threshold (COST_001 won't flag warehouses ≤ 600s)
warehouse_auto_suspend_max_seconds = 600

# Increase zombie user window (SEC_007 won't flag users inactive < 180 days)
zombie_user_days = 180

[tool.snowfort.conventions.thresholds.high_churn]
# Raise churn ratio threshold for CDC-heavy environments
row_churn_ratio = 200.0

[tool.snowfort.conventions.thresholds.network_perimeter]
# Add trusted IP ranges that won't be flagged
trusted_ip_ranges = ["10.0.0.0/8", "172.16.0.0/12"]

[tool.snowfort.conventions.thresholds.mandatory_tagging]
# Override required tag names
required_tags = ["COST_CENTER", "TEAM"]

[tool.snowfort.conventions.thresholds.iac_drift]
# Custom IaC service account pattern
iac_service_account_pattern = "(?i)(SVC_|DEPLOY_|AUTOMATION_)"

[tool.snowfort.conventions.thresholds.dbt_grants]
# Custom functional role pattern
functional_role_pattern = "(?i).*_(ACCESS|READER|WRITER)$"
```

### How to skip specific rules

Use the `--rule` flag to run only specific rules (exclude by omission):

```bash
# Run everything except COST_001 and COST_012
snowfort audit scan --rule SEC_003 --rule SEC_004 --rule OPS_001
```

There is no `--exclude-rule` flag. To skip rules, specify only the ones you want.

---

## CLI Reference

```
snowfort audit scan [OPTIONS]
  --manifest          Output JSON manifest to stdout (agent-consumable)
  --no-tui            Skip interactive terminal UI
  --auto              Flat table output (no guided grouping)
  --rule TEXT         Run only these rule(s), repeatable
  --cortex            AI executive summary via Snowflake Cortex
  --verbose           Include remediation column in output
  --workers INT       Parallel workers (default: 4)
  --profile           Show per-rule timing after scan

snowfort audit show [OPTIONS]
  --pillar TEXT       Filter by pillar name
  --rule-id TEXT      Filter by rule ID
  --severity TEXT     Filter by severity
  --resource TEXT     Filter by resource name substring
  --count-only        Print only violation count
  -o FILE             Export YAML report

snowfort audit rules [RULE_ID]
  List all rules, or show detail for one rule by ID
```
