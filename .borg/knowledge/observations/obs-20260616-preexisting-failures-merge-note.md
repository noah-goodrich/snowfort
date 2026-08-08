---
id: obs-20260616-preexisting-failures-merge-note
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- testing
- test-failures
- merge-hygiene
- keypair-bootstrap
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.910126+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-preexisting-failures-merge-note

## content

4 pre-existing failures exist in test_keypair_bootstrap.py on the feat/trustworthy-output branch. They are unrelated to PR #1's ACs and were present before this work, but they exist on the branch at merge time.

## resolution

Document pre-existing unrelated failures explicitly in the merge record/PR notes. Do not let them block the merge, but ensure they are tracked so they aren't attributed to this PR's changes later.
