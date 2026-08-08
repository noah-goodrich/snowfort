---
id: 20260414-clerk-in-front-of-mcp
date: '2026-06-16'
project: snowfort
domain: architecture
tags:
- oauth
- clerk
- mcp
- identity
- snowflake
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.892696+00:00'
updated_at: '2026-06-16 10:27:07.892698+00:00'
---

# 20260414-clerk-in-front-of-mcp

## decision

Validate Clerk-in-front-of-MCP as the correct OAuth architecture for Snowflake-connected MCP servers

## context

Q3 OAuth/Identity — evaluating identity patterns for MCP servers that need Snowflake access

## reasoning

Clerk handles user-facing OIDC/OAuth flows and issues tokens; MCP server exchanges Clerk token for Snowflake-scoped credentials. This keeps Snowflake auth internal and avoids exposing Snowflake OAuth endpoints to end users.
