---
id: obs-20260527-default-disabled-test-coverage
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- testing
- rules-engine
- default-disabled
- test-count
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.944905+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260527-default-disabled-test-coverage

## content

Adding the `default_disabled` class attribute pattern to the rules engine required 2 new tests specifically validating that the filter behavior works correctly (rules with default_disabled=True are excluded from default runs but included when explicitly requested via --rules). Test count moved from 1326 to 1328. The filter behavior is non-obvious enough to warrant explicit regression tests.

## resolution

Tests were added as part of the same commit introducing the feature. Any future rule using default_disabled should verify both the exclusion behavior and the explicit-include behavior are tested.
