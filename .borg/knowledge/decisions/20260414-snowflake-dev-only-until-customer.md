---
id: 20260414-snowflake-dev-only-until-customer
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- environments
- cost
- staging
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.887501+00:00'
updated_at: '2026-06-16 10:27:07.887504+00:00'
---

# 20260414-snowflake-dev-only-until-customer

## decision

Maintain DEV environment only on Snowflake until first paying customer; skip PROD provisioning

## context

Q2 account setup evaluation — whether to create dev/staging/prod environment tiers immediately

## reasoning

At ~$60/mo total Snowflake spend, the overhead of maintaining multiple environments exceeds the risk mitigation value. Promoting DEV to PROD at first customer is a clear, low-cost trigger.
