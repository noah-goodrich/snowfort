---
id: obs-20260617-externalbrowser-env-default-short-circuit
session_date: '2026-06-18'
project: snowfort
tool: claude-code
tags:
- snowflake
- externalbrowser
- sso
- authentication
- environment-variables
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.269125+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260617-externalbrowser-env-default-short-circuit

## content

If an environment variable that selects the Snowflake auth method is already set (e.g. SNOWFLAKE_AUTHENTICATOR=snowflake), the code path that would invoke externalbrowser is silently skipped. The developer sees no error — auth simply uses the env-var value — making it appear that SSO configuration is broken when it was never attempted.

## resolution

Before debugging externalbrowser failures, explicitly check (and temporarily unset) any SNOWFLAKE_AUTHENTICATOR or equivalent env var to confirm the SSO branch is actually being entered.
