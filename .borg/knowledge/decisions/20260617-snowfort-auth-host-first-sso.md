---
id: 20260617-snowfort-auth-host-first-sso
date: '2026-06-18'
project: snowfort
domain: infrastructure
tags:
- snowflake
- authentication
- sso
- externalbrowser
- docker
- secrets
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: 20260618-0254-snowfort
created_at: '2026-06-18 02:54:48.266115+00:00'
updated_at: '2026-06-18 02:54:48.266118+00:00'
---

# 20260617-snowfort-auth-host-first-sso

## decision

All Snowflake authentication and secret management runs on the host, never inside containers. SSO/externalbrowser flows are host-only. Containers receive only pre-resolved credentials via environment variables.

## context

snowfort runs both host processes and Docker containers; Snowflake SSO (externalbrowser) opens a browser tab and requires network round-trips that containers cannot perform reliably.

## reasoning

Browser-based OAuth cannot complete inside a headless container. Secrets on the host avoid baking credentials into images or volumes. The env-var pass-through pattern keeps containers stateless and portable.
