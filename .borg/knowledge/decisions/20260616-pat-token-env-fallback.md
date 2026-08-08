---
id: 20260616-pat-token-env-fallback
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- pat
- authentication
- connection-pooling
- vendor
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.907456+00:00'
updated_at: '2026-06-16 10:27:07.907457+00:00'
---

# 20260616-pat-token-env-fallback

## decision

Modified _build_connection_params in snowflake_gateway.py to read PAT token from the options object first, then fall back to SNOWFLAKE_TOKEN env var when authenticator == programmatic_access_token

## context

Connection pool workers were failing silently when using PAT auth, causing the pool to degrade to 1 worker instead of the intended parallel count

## reasoning

Silent fallback to 1 worker is worse than a loud failure — the fix ensures all pool connections can authenticate, and env var fallback keeps devcontainer/CI ergonomics intact without requiring each connection options object to be manually wired
