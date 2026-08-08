---
id: 20260414-wif-replaces-rsa-cicd
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- wif
- workload-identity-federation
- ci-cd
- authentication
- oauth
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.860224+00:00'
updated_at: '2026-06-16 10:27:07.860225+00:00'
---

# 20260414-wif-replaces-rsa-cicd

## decision

Use WIF (Workload Identity Federation) instead of static RSA keys for CI/CD authentication to Snowflake

## context

Archived Snowpark OAuth patterns found during code review of budget-app and budget-app-legacy

## reasoning

WIF reached GA in August 2025, eliminating the need to manage rotating RSA key pairs for machine identity. Archived Snowpark OAuth patterns are confirmed deprecated.
