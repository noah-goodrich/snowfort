---
id: devcontainer-pat-snowflake-auth-setup
project: snowfort
domain: infrastructure
tags:
- devcontainer
- snowflake
- pat
- authentication
- secrets
preconditions: []
steps:
- Add [PATAUTH] connection stanza to ~/.snowflake/connections.toml on the host
- Set SNOWFLAKE_DEFAULT_CONNECTION_NAME=PATAUTH in .devcontainer/.secrets.env
- Set SNOWFLAKE_TOKEN=<pat> in .devcontainer/.secrets.env
- Set SF_SKIP_TOKEN_FILE_PERMISSIONS_VERIFICATION=true in .devcontainer/.secrets.env
- Run chmod 0600 ~/.snowflake/connections.toml on the host (permanent fix — survives
  rebuilds)
pitfalls:
- Without chmod 0600 on connections.toml, the Snowflake connector emits a permissions
  warning on every connection attempt
- SF_SKIP_TOKEN_FILE_PERMISSIONS_VERIFICATION=true is required inside the container
  because devcontainer file ownership often prevents the connector from verifying
  permissions itself
- If the vendor gateway doesn't read SNOWFLAKE_TOKEN from the env for pool workers,
  parallel connections silently fail and the pool degrades to 1 worker with no error
  — see pat-parallel-workers gotcha
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.908408+00:00'
updated_at: '2026-06-16 10:27:07.908408+00:00'
---

# devcontainer-pat-snowflake-auth-setup

## description

Configuring PAT-based Snowflake authentication inside a devcontainer so all tooling (including parallel connection pools) authenticates correctly
