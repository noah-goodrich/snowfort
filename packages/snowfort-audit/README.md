# snowfort-audit

**Your Snowflake account is bleeding money in places you can't see. snowfort scans it and shows you
where.** It also checks security, performance, reliability, operations, and governance: 164
deterministic checks in total. The output is a 0-100 score, a letter grade (A through F), and a
list of things to fix.

## Install

```bash
pipx install snowfort-audit
```

`pip install snowfort-audit` also works. pipx is recommended because it keeps the CLI in its own
isolated environment.

## 5-minute quickstart

```bash
# 1) Set Snowflake connection environment variables in your current shell.
eval "$(snowfort login)"

# 2) Run the scan.
snowfort audit scan

# 3) Or write a JSON manifest for CI / downstream tooling.
snowfort audit scan --manifest > scan.json
```

`snowfort login` will ask for your account, user, role, and how you authenticate. Pick one:

- **mfa**: password + Snowflake MFA prompt.
- **keypair**: RSA key-pair (JWT). Recommended for service accounts.
- **pat**: programmatic access token.
- **externalbrowser**: SSO via your browser.

If you want to try snowfort without a Snowflake account at all, scan a folder of SQL files instead:

```bash
snowfort audit scan --offline --path examples/offline_showcase
```

## Sample output

```text
╭─ Snowflake Well-Architected Scorecard for my-account ─╮
│ Score: 78/100 (C)                                     │
╰───────────────────────────────────────────────────────╯
        Pillar Breakdown
┌──────────────┬───────┬───────┬───────────┐
│ Pillar       │ Score │ Grade │ Status    │
├──────────────┼───────┼───────┼───────────┤
│ Security     │ 71    │ C     │ Attention │
│ Cost         │ 64    │ D     │ Attention │
│ Reliability  │ 92    │ A     │ Healthy   │
│ Performance  │ 88    │ B     │ Healthy   │
│ Operations   │ 79    │ C     │ Attention │
│ Governance   │ 81    │ B     │ Healthy   │
└──────────────┴───────┴───────┴───────────┘

Violations (47):
 Severity   Rule       Resource          Message
 CRITICAL   SEC_002    USER_BOB          MFA not enabled on ACCOUNTADMIN.
 HIGH       COST_002   WH_REPORTING_OLD  Warehouse unused for 142 days.
 ...
```

Add `-v` to see remediation instructions per violation.

## What snowfort is for

snowfort is a **Policy-as-Code (PaC)** scanner aligned to the Snowflake **Well-Architected
Framework (WAF)**. It runs against either a live Snowflake account or a folder of SQL files, and it
produces a scorecard you can act on.

### Two modes

- **Offline mode** (`--offline`): statically analyzes project files (`manifest.yml`, SQL scripts,
  Jinja). No Snowflake connection required. Good for CI/CD pre-deploy gates.
- **Online mode** (default): connects to your live account and inspects runtime config, usage
  history, object state, and tag compliance.

### Six WAF pillars + static analysis

Every scan produces a per-pillar grade and an overall grade. _Rule count last verified 2026-05-26._

| Pillar           | Rules | Examples                                                                                  |
|:-----------------|:------|:------------------------------------------------------------------------------------------|
| **Cost**         | 47    | Zombie warehouses, auto-suspend, Cortex AI/Code/Agents spend, credit budgets, clone sprawl|
| **Security**     | 49    | Admin exposure, MFA, network perimeter, PAT governance, Trust Center, PrivateLink         |
| **Performance**  | 19    | Spillage, workload efficiency, cache contention, queuing, partition pruning, DT lag       |
| **Operations**   | 16    | Resource monitors, tagging, IaC drift, Permifrost drift, sandbox sprawl, alerting         |
| **Reliability**  | 10    | Replication gaps, retention safety, failover completeness, Dynamic Table refresh lag      |
| **Governance**   | 16    | Future grants, object docs, account budget, sensitive-data classification, share risk     |
| **Static (SQL)** | 7     | Hardcoded secrets, naked DROP, SQL anti-patterns, MERGE pattern, Dynamic Table complexity |

The full rule catalog with IDs, severities, and modes is in
[`docs/RULES_CATALOG.md`](docs/RULES_CATALOG.md).

### Output format

Every violation in the JSON manifest includes:

- `rule_id`: e.g. `COST_002`, `SEC_016`.
- `resource_name`: the warehouse, table, role, or user that failed.
- `message`: human-readable description of the violation.
- `severity`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- `pillar`: which WAF pillar the rule belongs to.
- `remediation_instruction`: actionable text suitable for a human or an LLM to generate the fix.

## More CLI commands

```bash
# Faster online scan: parallel workers (multiple Snowflake connections).
snowfort audit scan --workers 4

# List every rule with severity and pillar.
snowfort audit rules

# Generate inputs for the Snowflake pricing calculator.
snowfort audit calculator-inputs > pricing.json

# AI-augmented executive summary using Snowflake Cortex.
snowfort audit scan --cortex

# Persist scan results into SNOWFORT.AUDIT.SCAN_* tables for the dashboard.
snowfort audit scan --persist

# Deploy the Streamlit-in-Snowflake dashboard.
snowfort audit deploy-dashboard
```

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for concurrency notes and native-app vs client-side
behavior.

## Custom rules (extensibility)

You can add your own rules without forking snowfort. Write a Python package, register it via entry
points, and snowfort picks it up automatically.

1. Create a class that inherits from `snowfort_audit.domain.rule_definitions.Rule`.
2. Expose a function that returns a list of your rules.
3. Register it in your `pyproject.toml`:

   ```toml
   [project.entry-points."snowarch.audit.rules"]
   my_rules = "my_package.rules:get_rules"
   ```

Install your package in the same environment as `snowfort-audit` and your rules show up in the next
scan.

## Remediation

Violations carry an optional `remediation_instruction` field. snowfort itself is the
**diagnostician**: it doesn't apply fixes. The intended flow is:

- Pipe the JSON manifest to your IaC tooling.
- Or hand it to [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) or
  another LLM and ask it to generate the fix.
- Or read the manifest in a CI job and block deploys on `CRITICAL` violations.

See [docs/DEFERRED_WORK.md](docs/DEFERRED_WORK.md) for the planned Cortex Code Skill.

## Local development

```bash
# Editable install with dev dependencies (single spec so pip doesn't double-resolve).
pip install -e ".[dev]"

# Run the test suite + coverage gate.
make test
make coverage-check
```

## License

MIT. Built by Noah Goodrich.
