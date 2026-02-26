# Snowfort Audit: Snowflake WAF Scorecard

**Snowfort Audit** is a Policy-as-Code (PaC) and **Well-Architected Framework (WAF)** compliance tool for Snowflake. It audits your Snowflake environment against 83 deterministic rules across Security, Cost, Performance, Reliability, Operations, and Governance — through both static analysis and runtime inspection.

## Key Concepts

### 1. Dual-Mode Inspection
*   **Offline Mode (`--offline`)**: Statically analyzes project files (`manifest.yml`, SQL scripts, Jinja) for configuration errors and best practice violations. **No Snowflake connection required.**
*   **Online Mode (Default)**: Connects to your live Snowflake account to inspect runtime configurations, usage history, object states, and tag compliance.

### 2. The WAF Scorecard
Every audit run generates a **Snowarch WAF Scorecard**, providing a 0-100 health score for each architectural pillar and an overall project grade (A–F). This output is designed for FinOps and Security team reviews.

### 3. Verification Gateway
Snowarch Audit acts as a **deterministic verification layer**: it reliably identifies WAF violations and remediation steps. Use it to validate that AI-generated or hand-written Snowflake code is safe, cost-efficient, and compliant—before or after deployment.

---

## Rule Suite — 83 rules across 7 WAF-aligned categories

| Category | Rules | Key Checks |
|:---|:---|:---|
| **Cost Optimization** | 17 | Zombie warehouses, auto-suspend, elephant queries, statement timeouts, QAS eligibility, materialized view waste, data transfer, clustering/SOS cost-benefit |
| **Security** | 20 | Admin exposure, MFA enforcement, network perimeter, public grants, service user key-pair, scope isolation, read-only integrity, masking/RAP coverage, SSO, CIS scanner |
| **Performance** | 15 | Remote/local spillage, workload efficiency "Pincer", cache contention, query queuing, partition pruning, clustering quality, Dynamic Table lag, Gen2/Snowpark pivot |
| **Operations** | 12 | Resource monitors, mandatory tagging, IaC drift readiness, alert configuration, observability infrastructure, event tables, Data Metric Functions |
| **Reliability** | 8 | Replication gaps, retention safety, failover completeness, replication lag, failed tasks, pipeline replication |
| **Governance** | 4 | Future grants anti-pattern, object documentation, account budget enforcement, sensitive data classification |
| **Static Analysis** | 7 | Hardcoded secrets, naked DROP statements, SQL anti-patterns, MERGE pattern, Dynamic Table complexity |

The full rule catalog with IDs, severities, and modes is in [`docs/RULES_CATALOG.md`](docs/RULES_CATALOG.md).

---

## 🛠 Usage

### Quick start (online scan)
1. Install: `pip install snowfort-audit` (or `pipx install snowfort-audit`).
2. **Run login with eval** so env vars are set in your shell: `eval $(snowfort login)`.
3. Run a scan: `snowfort audit scan`.

### Installation
```bash
pip install snowfort-audit
```

For local development (editable install with dev extras), use a single spec so pip does not treat the package twice:
```bash
pip install -e ".[dev]"
```

**Documentation:** [Severity & grading rubric](docs/SEVERITY_AND_GRADING.md) — how scores and rule severities are determined.

### Custom Rules (Extensibility)
You can extend `snowfort-audit` with your own custom rules by creating a Python package and registering it via entry points.

1. Create a package with your rule class (inheriting from `snowfort_audit.domain.rule_definitions.Rule`).
2. Expose a function that returns a list of your rules.
3. Register it in your `pyproject.toml`:

```toml
[project.entry-points."snowarch.audit.rules"]
my_rules = "my_package.rules:get_rules"
```

When you install your package in the same environment as `snowfort-audit`, your rules will automatically be included in the scan.

### 0. Run the examples (showcase)

**Offline:** A sample project with intentional violations is in `examples/offline_showcase/`. From the `packages/snowarch-audit` directory:
```bash
snowfort-audit scan --offline --path examples/offline_showcase
```
Use `-v` and `--manifest` for remediation details and JSON output.

**Online:** Seed a sandbox account with WAF violations, then run the online scan:
```bash
snowfort-audit demo-setup   # Creates bad warehouses, users, policies, etc. (uses ACCOUNTADMIN)
snowfort-audit scan         # Inspect live account and see the violations
```
From the monorepo root you can also run `snowarch-admin demo-setup` (it runs `packages/snowarch-audit/examples/generate_chaos.sql`).

**Faster online scan:** Use parallel workers (multiple Snowflake connections) to reduce run time:
```bash
snowfort audit scan --workers 4
```
See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for concurrency options and Native App vs client-side behavior.

### 1. Run Offline Scan (CI/CD)
Analyze your SQL scripts and project configuration definitions before deployment.
```bash
snowfort-audit scan --offline --path ./my-project
```

#### Example Output
The CLI renders a **Rich** scorecard: overall score and letter grade (A–F), per-pillar breakdown (Score, Grade, Status), and a violations table. Use `-v` for remediation instructions.

```text
╭─ Snowflake Well-Architected Scorecard for ./my-project ─╮
│ Score: 94/100 (A)                                       │
╰─────────────────────────────────────────────────────────╯
        Pillar Breakdown
┌──────────────┬───────┬───────┬──────────┐
│ Pillar       │ Score │ Grade │ Status   │
├──────────────┼───────┼───────┼──────────┤
│ Security     │ 94    │ A     │ Healthy  │
│ Cost         │ 100   │ A     │ Healthy  │
└──────────────┴───────┴───────┴──────────┘

Violations (2):
 Severity   Rule       Resource    Message
 ...
```

### 2. Set connection env (once per session for online scan)
**You must run `login` as an argument to `eval`** so the export lines are applied to your current shell; otherwise they are only printed and scan will not see them.

```bash
eval $(snowfort login)
# or: source <(snowfort login)
```

Prompt for account, user, role, and authenticator; the exports set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, etc. so the next `scan` uses them. Auth options in the menu: mfa (password+MFA), keypair (JWT), pat (token). If the variables are already set, `login` reuses them and prints the same exports.

### 3. Run Online Scan (Periodic)
Audit your live environment using the WAF Scorecard.
```bash
snowfort-audit scan
```

### 4. AI-Augmented Scan (Cortex)
Use Snowflake Cortex (LLM) to synthesize findings into an Executive Summary.
```bash
snowfort-audit scan --cortex
```

### 5. Planning Tools (Calculator)
Generate usage inputs for the [Snowflake Pricing Calculator](https://www.snowflake.com/pricing/calculator/).
```bash
snowfort-audit calculator-inputs > pricing_inputs.json
```

### 6. JSON Manifest (Integration)
Output machine-readable violations (including `pillar` and `remediation_instruction`) for CI or downstream tools (e.g. Cortex Code Skill).
```bash
snowfort-audit scan --offline --path . --manifest
```
Each violation in the JSON includes `rule_id`, `resource_name`, `message`, `severity`, `pillar`, and `remediation_instruction` (actionable text for an LLM or human to generate fixes).

---

## Remediation Instructions
Violations carry an optional **remediation_instruction**: human/LLM-readable text describing what to do. The audit is the *diagnostician*; fixes are intended to be managed as **IaC** via admin/scaffold tooling or by consuming `--manifest` output with [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) or another LLM. See [Deferred work](docs/DEFERRED_WORK.md) for Cortex Code Skill and fix strategy.

---

## Roadmap
- **Cortex Code Skill**: Invoke audit and generate remediation from `remediation_instruction` (see [Deferred work](docs/DEFERRED_WORK.md)).
- **v1.0**: Native App packaging, Streamlit dashboard polish, schema security for `AUDIT_RESULTS`. Monorepo and PyPI deployment: see [MONOREPO_AND_PYPI.md](docs/MONOREPO_AND_PYPI.md).

---

## Integrating with Deployments
`snowarch-deploy` automatically runs `snowfort-audit` in **Offline Mode** during the plan stage of your deployment pipeline, blocking deployments that violate critical WAF rules.
