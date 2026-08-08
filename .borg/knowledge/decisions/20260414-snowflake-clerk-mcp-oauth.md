---
id: 20260414-snowflake-clerk-mcp-oauth
date: '2026-06-16'
project: snowfort
domain: authentication
tags:
- oauth
- clerk
- snowflake
- mcp-server
- service-identity
- saml
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.859627+00:00'
updated_at: '2026-06-16 10:27:07.859628+00:00'
---

# 20260414-snowflake-clerk-mcp-oauth

## decision

Clerk handles human SSO (SAML2); MCP server uses key-pair/WIF for service identity; External OAuth reserved for delegated app access

## context

Determining correct OAuth architecture for a system where humans authenticate via Clerk and a backend MCP server authenticates to Snowflake

## reasoning

These are three distinct identity concerns requiring different mechanisms. Conflating them leads to over-engineering. Clerk-in-front-of-MCP-server is the right boundary — Clerk owns the human auth layer, Snowflake-native mechanisms own the service layer.
