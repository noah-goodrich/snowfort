---
id: obs-20260414-wif-requires-account-preconfiguration
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- wif
- authentication
- setup
category: gotcha
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.901822+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-wif-requires-account-preconfiguration

## content

Workload Identity Federation on Snowflake is not zero-config. The Snowflake account must have the external OAuth / WIF trust relationship configured (specifying the cloud provider's OIDC issuer) before any workload can authenticate using it. This is an account-level setting, not a per-service setting.

## resolution

Add WIF account configuration to the create.sql / account bootstrap step for any project intending to use service-to-Snowflake WIF auth. Document the issuer URL and audience values required for the target cloud provider.
