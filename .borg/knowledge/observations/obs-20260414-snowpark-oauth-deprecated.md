---
id: obs-20260414-snowpark-oauth-deprecated
session_date: '2026-04-14'
project: snowfort
tool: claude-code
tags:
- snowflake
- snowpark
- oauth
- deprecated
- wif
- authentication
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.865249+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-snowpark-oauth-deprecated

## content

Snowpark OAuth authentication patterns found in archived codebases (budget-app, budget-app-legacy) are confirmed deprecated. WIF (Workload Identity Federation) is the current GA replacement for machine/service authentication to Snowflake as of August 2025.

## resolution

Do not copy Snowpark OAuth patterns from legacy repos. Use WIF for CI/CD and service identity; use key-pair auth only as fallback for environments that don't support OIDC federation.
