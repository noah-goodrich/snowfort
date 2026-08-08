---
id: snowflake-oauth-decision-tree
project: snowfort
domain: architecture
tags:
- snowflake
- oauth
- identity
- decision-tree
preconditions: []
steps:
- Human end user via web app → Clerk (or equivalent IdP) in front of MCP; Snowflake
  never sees end-user identity directly
- Backend service / scheduled job → WIF using cloud-provider workload identity; no
  stored key material
- Human developer / admin → Snowflake-native OAuth with short-lived tokens; or key
  pair for legacy tooling that doesn't support OAuth
pitfalls:
- WIF requires the Snowflake account to be configured with the correct external ID
  provider before any service can use it — don't assume it works out of the box
- Clerk tokens are not natively trusted by Snowflake; the MCP layer must perform the
  token exchange, not pass the Clerk JWT directly
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.895431+00:00'
updated_at: '2026-06-16 10:27:07.895432+00:00'
---

# snowflake-oauth-decision-tree

## description

Three-flavor decision tree for choosing the right Snowflake auth pattern based on actor type
