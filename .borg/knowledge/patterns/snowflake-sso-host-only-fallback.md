---
id: snowflake-sso-host-only-fallback
project: snowfort
domain: infrastructure
tags:
- snowflake
- sso
- externalbrowser
- workers
- auth
preconditions: []
steps:
- 'Detect environment: check whether a browser can be opened (host) or not (container/CI).'
- 'On host: use externalbrowser authenticator; set SNOWFLAKE_AUTH_FORCE_SERVER_URL
  if the default callback URL is unreachable.'
- 'In container/CI: use key-pair or password auth passed via environment variables
  pre-resolved on the host.'
- When using externalbrowser (single-connection SSO token), pass --workers 1 to any
  parallel job runner to avoid concurrent connection attempts that exhaust the token.
- Disambiguate sso_enforced policy errors (SEC_015) from transient auth failures before
  retrying.
pitfalls:
- externalbrowser opens a localhost callback; if the Snowflake account is configured
  with a non-default redirect, the browser tab completes but the Python process hangs
  — set SNOWFLAKE_AUTH_FORCE_SERVER_URL to fix.
- Running multiple workers with a fresh SSO token causes all but the first connection
  to fail; always use --workers 1 with externalbrowser.
- An env-var default that already resolves to a non-SSO auth method silently short-circuits
  the SSO path — audit env defaults before assuming externalbrowser will run.
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.268251+00:00'
updated_at: '2026-06-18 02:54:48.268252+00:00'
---

# snowflake-sso-host-only-fallback

## description

Safely execute Snowflake SSO authentication on the host and fall back gracefully when running in constrained environments.
