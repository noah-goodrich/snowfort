# Dependency Audit for Snowflake Native App

## Current Dependencies vs Anaconda Channel Availability

| Dependency | In Anaconda Channel | Status | Action |
|---|---|---|---|
| click | Yes | CLI only | Not needed for Native App (Streamlit replaces CLI) |
| keyring | No | CLI only | Not needed for Native App (Snowpark handles auth) |
| pydantic | Yes | Required | OK |
| pyyaml | Yes | Required | OK |
| rich | No | CLI only | Not needed for Native App |
| textual | No | TUI only | Not needed for Native App |
| snowflake-connector-python | Yes (bundled) | Required for CLI | Replaced by Snowpark in Native App |
| sqlfluff | No | Required | Must be bundled or replaced |
| tomli | Yes (stdlib 3.11+) | Required | OK (stdlib) |
| pandas | Yes | Required | OK |
| plotly | Yes | Required for charts | OK |
| streamlit | Yes (bundled) | Required | OK (provided by Snowflake) |

## Strategy

### Tier 1: Drop for Native App (CLI-only deps)
- click, keyring, rich, textual: Only used by CLI/TUI interfaces
- snowflake-connector-python: Replaced by snowflake.snowpark in Native App

### Tier 2: Available in Anaconda (no action needed)
- pydantic, pyyaml, pandas, plotly, tomli

### Tier 3: Must be bundled or replaced
- sqlfluff: Heavy dependency (~50 sub-deps). Options:
  1. Bundle subset needed for SQL validation
  2. Replace with Snowflake's built-in SQL validation via Snowpark
  3. Make it optional (skip SQL linting rules in Native App)

## Recommended: Optional Dependencies

Create separate dependency groups:
- `[project.dependencies]` — core (pydantic, pyyaml, tomli)
- `[project.optional-dependencies.cli]` — click, rich, textual, keyring, snowflake-connector-python
- `[project.optional-dependencies.native-app]` — (empty, uses Snowpark provided by runtime)
- `[project.optional-dependencies.dev]` — pytest, ruff, pylint-clean-architecture
