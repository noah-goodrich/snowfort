---
id: obs-20260501-cortex-audit-runtime
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowfort
- cortex
- audit
- runtime
category: performance
files_involved: []
confidence: 0.75
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:02.255317+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260501-cortex-audit-runtime

## content

Snowfort Cortex audit completed in approximately 10 minutes running in background. Returned 4 CRITICAL findings across SEC and REL and GOV categories.

## resolution

10-minute runtime is acceptable for background execution. Do not block foreground work on audit completion. Structure sessions to launch audit early, work on other tasks, then return to triage findings.
