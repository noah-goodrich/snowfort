---
id: 20260616-branch-protection-deferred-checks
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- github
- branch-protection
- ci-cd
- sequencing
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.918779+00:00'
updated_at: '2026-06-16 10:27:07.918780+00:00'
---

# 20260616-branch-protection-deferred-checks

## decision

Apply branch protection to main with only the `test` required check initially, then expand required checks after PR #11 merges

## context

Can't add required status checks for CI jobs that don't yet exist on main; PR #11 adds architecture-lint, sensitive-outputs, bandit

## reasoning

Bootstrapping problem — required checks must exist in the repo's check history before GitHub allows them as branch protection requirements. Two-phase approach unblocks protection now without waiting.
