---
id: 20260501-snowfort-real-vs-demo-triage-required
date: '2026-06-16'
project: snowfort
domain: security-audit
tags:
- snowfort
- cortex-audit
- demo-objects
- triage
alternatives: []
applies_to: []
confidence: 0.85
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:02.252402+00:00'
updated_at: '2026-06-16 10:27:02.252403+00:00'
---

# 20260501-snowfort-real-vs-demo-triage-required

## decision

Do not auto-remediate Cortex CRITICAL findings until user confirms which findings target real objects vs demo/chaos fixtures

## context

Cortex audit returned 4 CRITICAL findings including BAD_ADMIN_USER (MFA disabled) and PRD_BAD_DB (no replication). These names pattern-match test fixture naming conventions.

## reasoning

Remediating demo objects wastes time and could alter intentionally broken fixtures used for testing. Remediating real findings without user awareness violates change-control. The 10-minute background audit cannot distinguish context.
