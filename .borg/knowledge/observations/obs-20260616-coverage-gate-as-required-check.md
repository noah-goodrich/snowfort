---
id: obs-20260616-coverage-gate-as-required-check
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- ci
- coverage
- branch-protection
- testing
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.932785+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-coverage-gate-as-required-check

## content

The 80% coverage gate is enforced as a GitHub required status check, not just a soft warning. This means adding new code without tests can cause a previously-passing branch to fail the gate and become unmergeable — even if no existing tests broke.

## resolution

When implementing new audit rules or modules, always write tests in the same PR as the implementation. Do not defer tests to a follow-up PR, as the coverage gate will block the follow-up's base branch from merging if coverage drops between PRs.
