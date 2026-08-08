---
id: obs-20260617-sec015-vs-transient-auth
session_date: '2026-06-18'
project: snowfort
tool: claude-code
tags:
- snowflake
- sso
- SEC_015
- sso_enforced
- error-handling
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.272573+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260617-sec015-vs-transient-auth

## content

Snowflake returns SEC_015 when an account policy enforces SSO and the client attempts a non-SSO auth method. This is a policy rejection, not a transient network or credential error. Retrying with the same non-SSO method will always fail.

## resolution

Detect SEC_015 specifically and surface it as a configuration error ('SSO is enforced on this account; switch to externalbrowser auth') rather than retrying or treating it as a transient failure.
