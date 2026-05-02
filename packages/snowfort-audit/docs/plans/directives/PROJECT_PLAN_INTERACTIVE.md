# Project Plan: Interactive Remediation Skill (Cortex-Native)
*Established: 2026-05-01*

## Objective

Build a Cortex Code skill that drives an interactive remediation planning session: the agent runs
the audit, converses with the user to filter findings, challenge false positives, build a
prioritized remediation plan, and optionally execute SQL fixes with confirmation. Delivered as a
single SKILL.md file — no Python infrastructure changes.

## Acceptance Criteria

- [ ] New skill at `.cortex/skills/snowfort-audit-interactive/SKILL.md` covering all 5 phases
  - Verify: file exists and parses as valid Markdown
- [ ] Phase 1: Agent can answer all 7 triage query types from manifest JSON without re-scanning
  - Verify: manual test with real `--manifest` output
- [ ] Phase 2: Agent provides investigation SQL for ≥10 commonly-challenged rules
  - Verify: `grep -c 'Investigation SQL' SKILL.md` ≥ 10
- [ ] Phase 3: Agent builds valid `remediation_plan.yaml` matching the schema
  - Verify: YAML schema documented inline with example
- [ ] Phase 4: Agent refuses ACCOUNT-scoped DDL without double confirmation
  - Verify: safety rules documented and explicit in skill
- [ ] Phase 5: Agent writes plan file and prints commit suggestion on exit
  - Verify: exit instructions documented in skill
- [ ] Existing `SKILL.md` files are unchanged
  - Verify: `git diff .cortex/skills/snowfort-audit/ .cortex/skills/snowarch-audit/`
- [ ] Correctly references `pyproject.toml` conventions (not `snowfort.toml`) for suppression
  - Verify: `grep 'pyproject.toml' SKILL.md`

## Scope Boundaries

- NOT building: New CLI commands or flags
- NOT building: MCP server, agent definitions, or prompt templates in Python
- NOT building: RemediationProtocol implementation (the protocol exists in domain but is unused)
- NOT building: Per-rule exclusion mechanism (doesn't exist; use threshold overrides instead)
- If done early: Ship, don't expand.

## Ship Definition

1. SKILL.md file written and reviewed
2. Manual test: invoke skill with real scan, verify all 5 phases work
3. Existing skills unchanged

## Risks

- **Skill length**: The interactive skill is substantially longer than existing skills (~300-400
  lines). Risk that Cortex Code truncates or mishandles long skills. Mitigated by structured
  sections with clear headers.
- **Investigation SQL accuracy**: SQL queries for challenged rules must actually work on real
  accounts. Mitigated by using only SHOW commands and standard ACCOUNT_USAGE views.
- **Convention override docs**: The directive spec references `snowfort.toml` exclusions that
  don't exist. Corrected to use `pyproject.toml` `[tool.snowfort.conventions.thresholds]`.

## The Collective Review Summary

- **Scope Hawk**: Single file. No Python changes. Ship the skill, don't build RemediationProtocol.
- **Craftsperson**: Investigation SQL for challenged rules is where value lives. Get those right.
- **Performance Engineer**: No performance concerns — skill is pure agent instructions, no runtime.
- **Security Auditor**: Double-confirm safety rules for ACCOUNT-scoped DDL and DROP are critical.
- **Adult**: Write the skill file, test it with a real scan, ship it.
