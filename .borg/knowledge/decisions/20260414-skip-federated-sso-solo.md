---
id: 20260414-skip-federated-sso-solo
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- sso
- identity
- scale
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.894402+00:00'
updated_at: '2026-06-16 10:27:07.894403+00:00'
---

# 20260414-skip-federated-sso-solo

## decision

Skip federated SSO (SAML/SCIM) configuration in Snowflake at team-of-1 scale

## context

Q3 OAuth/Identity — evaluating whether to configure Snowflake federated SSO with an IdP

## reasoning

Federated SSO setup requires IdP configuration, Snowflake SAML integration, and ongoing user provisioning workflow. At team-of-1 the only user is the account admin; overhead is not justified.
