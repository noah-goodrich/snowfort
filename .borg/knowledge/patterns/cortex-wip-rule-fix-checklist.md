---
id: cortex-wip-rule-fix-checklist
project: snowfort
domain: architecture
tags:
- snowflake
- cortex
- cost-rules
- sql
- testing
preconditions: []
steps:
- Identify the affected rule IDs and locate their definitions in domain/rules/
- Check TABLE_STORAGE_METRICS (and similar system views) queries for missing SQL_EXCLUDE_SYSTEM_AND_SNOWFORT
  in WHERE clause
- Check unbounded queries (no LIMIT) that could return massive result sets — add ORDER
  BY <meaningful_column> DESC + LIMIT N
- Check time-window constants on ACCESS_HISTORY or similar audit views — validate
  against usage pattern requirements (quarterly vs. monthly)
- Update the rules snapshot file to reflect the fixed SQL
- Run full test suite (all ~1038 tests) to confirm no regressions before opening PR
pitfalls:
- Forgetting to update the snapshot file after fixing rule SQL will cause snapshot-diff
  tests to fail
- SQL_EXCLUDE_SYSTEM_AND_SNOWFORT must be applied consistently across all rules touching
  TABLE_STORAGE_METRICS — a partial fix leaves sister rules broken
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.920259+00:00'
updated_at: '2026-06-16 10:27:07.920260+00:00'
---

# cortex-wip-rule-fix-checklist

## description

Checklist for fixing Cortex WIP rule SQL issues (filter gaps, missing ORDER BY/LIMIT, window sizes)
