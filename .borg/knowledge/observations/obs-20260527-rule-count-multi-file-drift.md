---
id: obs-20260527-rule-count-multi-file-drift
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- documentation
- rules-catalog
- maintenance-burden
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.944476+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260527-rule-count-multi-file-drift

## content

The snowfort rule count (164 as of this session) is duplicated in at least 5 separate documentation files: RULES_CATALOG, PERFORMANCE_STRATEGIES, STRATEGIC_ANALYSIS, EXECUTIVE_SUMMARY, and the package README. Each file uses slightly different formatting and context for the count. When the count changes, all 5 must be updated in the same commit or the documentation is immediately inconsistent.

## resolution

A dedicated reconciliation step was added to the pre-launch PR. Long-term mitigation would be generating the count programmatically from a single source (e.g., the rules registry) and injecting it into docs at build time. Currently this is a manual process requiring awareness of all 5 locations.
