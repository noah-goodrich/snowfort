---
id: obs-20260617-externalbrowser-force-server-url
session_date: '2026-06-18'
project: snowfort
tool: claude-code
tags:
- snowflake
- externalbrowser
- sso
- SNOWFLAKE_AUTH_FORCE_SERVER_URL
- callback
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.271252+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260617-externalbrowser-force-server-url

## content

externalbrowser SSO completes in the browser but the Python connector hangs waiting for the localhost callback when the Snowflake account's redirect URL does not match the connector's expected server URL. No timeout error is raised promptly — the process just stalls.

## resolution

Set SNOWFLAKE_AUTH_FORCE_SERVER_URL to the correct local callback address so the connector listens on the right endpoint. Document this env var alongside any externalbrowser setup instructions.
