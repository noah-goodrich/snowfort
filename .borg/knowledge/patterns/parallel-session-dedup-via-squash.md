---
id: parallel-session-dedup-via-squash
project: snowfort
domain: infrastructure
tags:
- git
- parallel-sessions
- claude-code
- merge-strategy
preconditions: []
steps:
- Allow parallel sessions to complete their work on the shared branch without intervention
- Open the PR normally; note the inflated commit count in the PR description
- Document the expected squashed result in the PR description so reviewers understand
  the history will collapse
- Select 'Squash and merge' when merging the PR
- Verify the merge commit message captures the full logical scope of all 10 items
pitfalls:
- If individual commits are referenced by other PRs or issues, squashing destroys
  those SHAs — confirm no external references before squashing
- Near-duplicate commits may introduce subtle divergences (e.g., one session's version
  of a file vs another's); review the final diff carefully before merging, not just
  the commit list
- Parallel sessions racing on the same branch can leave the working tree in an ambiguous
  state if both sessions are still active at review time — confirm all sessions are
  complete before merging
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.942589+00:00'
updated_at: '2026-06-16 10:27:07.942590+00:00'
---

# parallel-session-dedup-via-squash

## description

When multiple AI coding sessions run concurrently on the same branch and produce near-duplicate commits, use squash-on-merge at PR time to collapse all duplicates into a single clean commit without requiring interactive rebase cleanup
