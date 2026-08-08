---
id: new-audit-rule-implementation-checklist
project: snowfort
domain: testing
tags:
- audit-rules
- testing
- registry
- snapshot
preconditions: []
steps:
- Implement the check class in the appropriate domain module under `rules/`
- 'Write ≥5 unit tests covering: happy path, zero-results, edge cases, and at least
  one threshold boundary'
- Register the rule in `rule_registry.py`
- Run the full test suite and confirm ≥80% coverage gate passes
- Update the registry snapshot (golden file) to include the new rule ID
- Open PR with rule + tests + registry + snapshot as a single atomic commit
pitfalls:
- Forgetting to update the snapshot causes a snapshot-mismatch CI failure that looks
  like a test failure but is actually a golden-file drift
- Coverage gate is enforced as a required check — adding a rule without tests can
  drop coverage below 80% and block merge
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.931346+00:00'
updated_at: '2026-06-16 10:27:07.931346+00:00'
---

# new-audit-rule-implementation-checklist

## description

Complete checklist for shipping a new snowfort audit rule (e.g. COST_038/039/040 pattern)
