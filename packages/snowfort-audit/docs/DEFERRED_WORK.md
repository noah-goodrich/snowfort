# Deferred / Later-Phase Work

Items from audit CLI and product discussions that are either deferred to a later phase or documented for continuity. Use this doc to pick up work when ready.

---

## Completed (was in original deferred list)

The following were implemented in the same pass as this doc update:

- **`show -o FILE --re-scan`** — One-command fresh scan + YAML export. Implemented: `show --re-scan` (optional `--offline`, `--account`, `--user`, `--role`, `--authenticator`, `--rules-dir`) runs a scan, updates cache, then shows or exports. Use `snowfort audit show -o report.yaml --re-scan` for one-shot fresh YAML.
- **`account_id` in cache** — Online scan now sets `account_id` in result metadata (via `SELECT CURRENT_ACCOUNT()`) before writing the cache, so exported YAML reports have the correct `account` field.
- **Link severity/grading doc** — README has a “Documentation” link to [Severity & grading rubric](SEVERITY_AND_GRADING.md). The `snowfort audit rules` command (list and single-rule view) prints a line pointing to `docs/SEVERITY_AND_GRADING.md`.

**Optional and not done:** Rename `rules` → `catalog` (product/UX preference; can be done later if desired).

---

## 1. Monorepo and why we removed “fix” commands

**Context:** The README and roadmap once described a `snowfort-audit fix` CLI (e.g. `snowfort-audit fix COST_001 "COMPUTE_WH"` to generate SQL or Terraform for a given violation). That command was not implemented in the current codebase, and the decision was to **not** add it as a first-class CLI.

**Rationale:** Fixes should be managed as **Infrastructure as Code (IaC)** through:

- **Admin tooling** (e.g. snowarch-admin or equivalent) for account-level and bootstrap changes.
- **Scaffold tooling** (e.g. snowarch-scaffold or equivalent) for generating project structure, configs, and remediation code.

The audit tool’s role is to **diagnose** (scan, report, export findings). Downstream tools (admin, scaffold, or an LLM/Cortex skill) consume `--manifest` JSON or the YAML report and **generate or apply** fixes. That keeps the audit package focused and avoids duplicating fix logic that belongs in IaC pipelines.

**Deferred / follow-up:**

- Remove or update README/roadmap text that still mentions `snowfort-audit fix` so it reflects “use admin/scaffold (or Cortex/LLM) to generate fixes from findings.”
- If a thin “fix” wrapper is ever desired, it should call into admin/scaffold or a shared library rather than embedding fix logic in snowfort-audit.

**References:** Discussion that “we want to manage the fixes as IaC through the admin and/or scaffold tools.”

---

## 2. Cortex Code Skill that uses Snowfort

**Context:** The README roadmap (v0.2) mentions a “Cortex Code Skill” that would teach [Snowflake Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) to run `snowfort-audit scan --manifest` and generate fixes from `remediation_instruction`. Violations in the JSON already include `rule_id`, `resource_name`, `message`, `severity`, `pillar`, and `remediation_instruction`, which are suitable for an LLM or skill.

**Deferred:** Create a Cortex Code skill (e.g. a `SKILL.md` or equivalent in `.cortex/skills/snowfort-audit/` or the appropriate location for your Cortex Code setup) that:

- Invokes or references `snowfort-audit` (e.g. run scan, consume `--manifest` output).
- Uses the violation payload (especially `remediation_instruction`) so Cortex Code can suggest or generate remediation (SQL, config changes, or tickets).

**Implementation notes:**

- Skill format and placement depend on the current Cortex Code skill contract (docs/source control).
- Audit side is ready: `snowfort audit scan --manifest` outputs machine-readable JSON; no code change required for a skill that parses it.
- Document in this repo how to run the audit and where to find the manifest schema (e.g. in docs or in the skill’s instructions).

**References:** README “v0.2: Cortex Code Skill (invoke audit + generate remediation from instructions).”

---

## 3. Cortex call to generate an executive summary report

**Context:** The CLI already supports `snowfort audit scan --cortex`, which uses `CortexSynthesizer` to produce an “Executive Summary (Cortex)” panel from the scan violations. The discussion was about **actually** making a Cortex (LLM) call to generate a proper executive summary report of the findings—e.g. for stakeholders or for inclusion in the YAML/export.

**Deferred:** Ensure or extend the Cortex integration so that:

- A Cortex (or equivalent LLM) call is made to synthesize findings into a short executive summary (narrative, prioritization, or recommended actions).
- That summary is either printed (as today), and/or written into the report (e.g. a field in the YAML export or a separate summary file).

**Implementation notes:**

- Current code: `CortexSynthesizer(cur).summarize(violations)` is used when `--cortex` is set and online; on failure it logs and continues. Verify that the Snowflake Cortex endpoint and permissions are correct so the call succeeds in target environments.
- If the summary should appear in the YAML report, add a field (e.g. `executive_summary`) to the report structure and populate it when `--cortex` (or a new flag like `--summary`) is used; may require passing the summary from scan into the report builder when writing cache or exporting.

**References:** “Actually being able to make a cortex code call ourselves to generate an execute summary report of the findings.”

---

## 4. Migrating snowfort-audit to a monorepo and PyPI deployment

**Context:** The goal is to move snowfort-audit into a monorepo layout and set up publishing to PyPI so the package can be installed with `pip install snowfort-audit` and kept up to date.

**Deferred:** Execute the migration and CI/CD for:

- Monorepo structure (where snowfort-audit lives relative to other packages, shared tooling, versioning).
- Build and publish to PyPI (automated or manual), including version bumping and possibly publishing from a `main` or `release` branch.

**Summary and step-by-step instructions** are in a separate doc so they can be used as a single checklist: **[MONOREPO_AND_PYPI.md](MONOREPO_AND_PYPI.md)**.

**References:** “Migrating snowfort-audit to a monorepo -> this one specifically I want the summary of and instructions for because I want to push it up as a mono-repo and get it set up and deploying through pypi.”

---

## Summary table

| # | Item | Status | Notes |
|---|------|--------|--------|
| — | `show --re-scan`, account_id, severity doc links | **Done** | Implemented |
| — | Rename `rules` → `catalog` | Optional | Product/UX preference |
| 1 | Monorepo & fix commands rationale | Doc only | README/roadmap cleanup for fix; fixes = IaC via admin/scaffold |
| 2 | Cortex Code Skill using snowfort | **Done (v0.4.0)** | `.cortex/skills/snowfort-audit/SKILL.md` ships in repo |
| 2b | Interactive Remediation Skill | **Directive written** | See [interactive-remediation-skill.md](plans/directives/interactive-remediation-skill.md) — passive SKILL.md done; interactive session skill pending |
| 3 | Cortex call for executive summary report | **Done (v0.4.0)** | `CortexSummary` dataclass; `cortex_summary:` block in YAML; `CortexSynthesizer.summarize_structured()` |
| 4 | Monorepo migration + PyPI deployment | **In progress** | Monorepo done; build artifacts ready; CI workflow in place; PyPI trusted publishing configured |

---

*Last updated: 2026-05-01 (rule ID duplicates resolved; interactive remediation directive drafted; PyPI build artifacts ready).*
