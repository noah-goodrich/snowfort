---
id: cortex-audit-triage-workflow
project: snowfort
domain: infrastructure
tags:
- snowfort
- cortex
- audit
- security
- triage
preconditions: []
steps:
- Trigger Cortex audit (background run, expect ~10 min)
- Collect all findings grouped by severity (CRITICAL first)
- For each finding, check object names against known test fixture naming conventions
  (e.g. BAD_, DEMO_, TEST_ prefixes)
- Present findings to owner with real-vs-demo classification hypothesis
- Get owner confirmation on each classification before beginning remediation
- 'For confirmed real findings, prioritize: SEC (security) > REL (reliability) > GOV
  (governance)'
pitfalls:
- Test fixture objects (chaos/demo) may surface as CRITICAL findings — their names
  often hint at this but not always
- Treating a demo object as real and remediating it can corrupt test infrastructure
- MFA and budget findings (SEC_016, GOV_003) are almost always real — don't defer
  these pending confirmation
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 22:41:19.366260+00:00'
updated_at: '2026-06-11 22:41:19.366261+00:00'
---

# cortex-audit-triage-workflow

## description

Run a Cortex security/reliability audit and triage findings for real vs demo/test objects before acting
