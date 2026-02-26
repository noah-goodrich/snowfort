---
name: snowfort-audit
description: Run Snowflake Well-Architected Framework audits and generate remediation code from violation instructions
tools:
  - shell
  - file_read
  - file_write
  - snowflake_execute
---

# Snowarch Audit – WAF Compliance and Remediation

## When to use this skill

- The user wants to audit a Snowflake project or account for Well-Architected Framework (WAF) compliance.
- The user wants to find and fix security, cost, performance, or governance issues in Snowflake.

## Capabilities

1. **Offline audit**: Run `snowfort-audit scan --offline --path . --manifest` to get JSON violations with rule_id, resource_name, message, severity, pillar, and remediation_instruction.
2. **Online audit**: Run `snowfort-audit scan --manifest` to audit the live Snowflake account.
3. **Remediation**: Use each violation remediation_instruction to generate SQL or Terraform fixes. Present fixes grouped by pillar and severity; optionally write remediation.sql or apply via snowflake_execute with user confirmation.

## Instructions

### Offline audit

1. Run: snowfort-audit scan --offline --path . --manifest
2. Parse the JSON. For each violation with remediation_instruction, generate the SQL (or Terraform) that implements that instruction using resource_name and message for context.
3. Present summary by pillar and severity; offer to write fixes to remediation.sql.

### Online audit

1. Run: snowfort-audit scan --manifest
2. Parse JSON and generate remediation SQL from remediation_instruction.
3. Offer to write remediation.sql or execute specific fixes via snowflake_execute after user confirmation.

### Best practices

- Group output by pillar and severity (CRITICAL first).
- Do not execute destructive SQL (DROP, REVOKE) without explicit user confirmation.
- Follow the remediation_instruction text; do not invent steps.

## Tool usage

- shell: Run snowfort-audit CLI commands.
- file_read: Read manifest.yml or SQL files.
- file_write: Write remediation.sql.
- snowflake_execute: Execute generated SQL only when the user explicitly confirms.
