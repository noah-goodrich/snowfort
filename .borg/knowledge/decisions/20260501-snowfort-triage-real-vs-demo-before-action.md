---
id: 20260501-snowfort-triage-real-vs-demo-before-action
date: '2026-06-11'
project: snowfort
domain: infrastructure
tags:
- snowfort
- cortex-audit
- security
- triage
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-11 22:41:19.365568+00:00'
updated_at: '2026-06-11 22:41:19.365568+00:00'
---

# 20260501-snowfort-triage-real-vs-demo-before-action

## decision

Hold on remediating CRITICAL findings BAD_ADMIN_USER (SEC_002) and PRD_BAD_DB (REL_001) until user confirms they are real vs demo/chaos objects

## context

Cortex audit returned 4 CRITICAL findings. BAD_ADMIN_USER and PRD_BAD_DB naming pattern strongly suggests they may be test fixtures from snowfort-audit's own demo/chaos suite rather than real production objects.

## reasoning

Acting on demo objects as if real would waste remediation effort and potentially corrupt test fixtures. User confirmation is cheap; mistaken remediation is not.
