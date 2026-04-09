# Snowfort Audit Skill

This skill teaches Cortex Code to run a Snowflake WAF audit, parse the findings, and generate remediation suggestions from the `remediation_instruction` field in each violation.

## Invocation

When a user asks to "audit the account", "run a security scan", "check compliance", or "find Snowflake issues", use this skill.

## Steps

### 1. Run the audit and export findings as JSON

```bash
snowfort audit scan --manifest
```

This writes a machine-readable manifest (JSON array of findings) to stdout. Each finding has:

- `rule_id` — e.g. `SEC_001`, `COST_001`
- `rule_name` — human-readable name
- `pillar` — `SECURITY`, `COST`, `RELIABILITY`, `PERFORMANCE`, `GOVERNANCE`, `OPERATIONS`
- `severity` — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- `resource` — the affected Snowflake object (role, warehouse, table, user, etc.)
- `message` — what was found
- `remediation_instruction` — exact SQL or configuration change to fix the issue

### 2. Parse and triage findings

Filter to CRITICAL and HIGH severity first:

```bash
snowfort audit scan --manifest | python3 -c "
import json, sys
findings = json.load(sys.stdin)
critical_high = [f for f in findings if f['severity'] in ('CRITICAL', 'HIGH')]
for f in sorted(critical_high, key=lambda x: x['severity']):
    print(f\"{f['severity']:8} {f['rule_id']:12} {f['resource']}: {f['message']}\")
"
```

### 3. Generate remediation SQL

For each finding, the `remediation_instruction` field contains the SQL or action to fix it. To extract all remediation steps:

```bash
snowfort audit scan --manifest | python3 -c "
import json, sys
findings = json.load(sys.stdin)
for f in findings:
    if f.get('remediation_instruction'):
        print(f\"-- {f['rule_id']} | {f['resource']}\")
        print(f[\"remediation_instruction\"])
        print()
"
```

### 4. Export a full YAML report

```bash
snowfort audit show -o report.yaml
```

The YAML report includes a `cortex_summary` block (if the scan was run with `--cortex`) with:
- `tl_dr` — one-sentence executive summary
- `top_risks` — list of top 3 risks
- `quick_wins` — list of quick remediation wins

## Example Prompts

- "Run the Snowflake audit and show me critical findings"
- "What are the top security risks in my Snowflake account?"
- "Generate SQL to fix all COST violations"
- "Export a compliance report as YAML"
- "Check if ACCOUNTADMIN is overgranted"

## CLI Reference

```
snowfort audit scan [OPTIONS]
  --workers INT       Parallel workers (default: 4)
  --cortex            Generate AI executive summary via Cortex
  --manifest          Output findings as JSON to stdout
  --rule TEXT         Filter to specific rule IDs (repeatable)
  --profile           Show per-rule timing table

snowfort audit show [OPTIONS]
  -o FILE             Export YAML report to file
  --re-scan           Run a fresh scan before showing

snowfort audit rules
  List all rule IDs, names, pillars, and severities

snowfort audit bootstrap --keypair
  Generate RSA keypair for service account auth (avoids MFA blocks)
```

## Notes

- The first scan on a cold Snowflake account may take 2-5 minutes; results are cached at `.snowfort/audit_cache.json`
- Subsequent `snowfort audit show` calls use the cache and are instant
- Rules are organized into 6 pillars: SECURITY, COST, RELIABILITY, PERFORMANCE, GOVERNANCE, OPERATIONS
- All SQL in `remediation_instruction` is idempotent and safe to run; review before applying to production
