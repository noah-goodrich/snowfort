---
id: obs-20260501-snowfort-demo-objects-in-audit-results
session_date: '2026-06-11'
project: snowfort
tool: cursor
tags:
- snowfort
- cortex
- audit
- demo-objects
- test-fixtures
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 22:41:19.368257+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260501-snowfort-demo-objects-in-audit-results

## content

Cortex audit results included CRITICAL findings for objects named BAD_ADMIN_USER and PRD_BAD_DB — naming patterns strongly suggest these are demo/chaos objects from the snowfort-audit test fixture suite, not real production resources. Automated audit tools do not distinguish between real and demo objects.

## resolution

Before triaging any audit finding, cross-reference object names against known test fixture naming conventions. Establish a convention of prefixing all test/demo objects with DEMO_ or TEST_ (rather than BAD_ or PRD_BAD_) to make this distinction unambiguous in future audits.
