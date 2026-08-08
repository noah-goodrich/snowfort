---
id: obs-20260616-pat-pool-silent-degradation
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- pat
- connection-pool
- parallel-workers
- silent-failure
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.908826+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-pat-pool-silent-degradation

## content

When using PAT (programmatic_access_token) authentication with the snowflake_gateway connection pool, worker connections that don't receive the token credential silently fail and the pool falls back to 1 worker. There is no loud error — the audit just runs slower than expected and the pool size appears correct at initialization.

## resolution

In _build_connection_params, explicitly read the token from the options object and fall back to os.environ['SNOWFLAKE_TOKEN'] when authenticator == 'programmatic_access_token'. Add import os if missing.
