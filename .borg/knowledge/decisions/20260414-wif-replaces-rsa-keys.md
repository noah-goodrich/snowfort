---
id: 20260414-wif-replaces-rsa-keys
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- wif
- rsa
- authentication
- security
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.893393+00:00'
updated_at: '2026-06-16 10:27:07.893393+00:00'
---

# 20260414-wif-replaces-rsa-keys

## decision

Use Workload Identity Federation (WIF) for service-to-Snowflake authentication instead of RSA key pairs

## context

Q3 OAuth/Identity — evaluating service authentication options for backend services accessing Snowflake

## reasoning

WIF allows services to authenticate using their cloud-provider identity (GCP SA, AWS role, etc.) without managing long-lived key material. Snowflake now supports WIF natively. Eliminates key rotation burden and reduces secret sprawl.
