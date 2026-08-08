---
id: obs-20260617-sso-token-single-connection
session_date: '2026-06-18'
project: snowfort
tool: claude-code
tags:
- snowflake
- externalbrowser
- sso
- workers
- concurrency
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.271758+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260617-sso-token-single-connection

## content

A freshly-obtained externalbrowser SSO token is single-use for the connection handshake. Spawning multiple parallel workers (e.g. --workers 4) causes all workers except the first to fail authentication, producing cryptic 'token already used' or connection errors.

## resolution

Always pass --workers 1 to any job runner when the auth method is externalbrowser. Document this constraint in the auth setup guide alongside the externalbrowser instructions.
