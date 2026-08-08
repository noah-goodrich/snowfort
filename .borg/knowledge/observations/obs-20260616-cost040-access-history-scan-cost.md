---
id: obs-20260616-cost040-access-history-scan-cost
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- access-history
- query-cost
- cortex
- cost-rules
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.921820+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-cost040-access-history-scan-cost

## content

Snowflake's ACCESS_HISTORY view is expensive to query at scale. A 365-day window on a busy account can scan millions of rows. The COST_040 rule was using a 365-day window, which is both costly and unnecessary for identifying unused objects.

## resolution

Reduced to 90 days. When writing rules against ACCESS_HISTORY, default to the shortest window that satisfies the business intent. Add explicit LIMIT clauses and ORDER BY to prevent runaway result sets.
