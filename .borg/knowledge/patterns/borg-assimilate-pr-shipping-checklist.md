---
id: borg-assimilate-pr-shipping-checklist
project: snowfort
domain: process
tags:
- borg-assimilate
- pr-merge
- checklist
- collective-review
preconditions: []
steps:
- Complete all AC verifications (borg-assimilate checklist), confirm all green
- Run The Collective review (borg-collective-review skill) — required before merge,
  cannot be skipped
- 'Execute merge: gh pr merge <N> --merge --delete-branch'
- Archive PROJECT_PLAN.md to packages/<pkg>/docs/plans/assimilated/<date>-<slug>.md
- 'Pop any stashed work for the next branch: git checkout <next-branch> && git stash
  pop'
- Proceed with remaining PRs in prescribed merge order
pitfalls:
- The Collective review is a hard gate — the checklist being green does NOT mean you
  can merge; the review must still be run
- Pre-existing test failures on a branch should be explicitly noted in the merge record
  even if unrelated to the PR's ACs
- Stashed work (e.g. vendor fixes) can be forgotten across sessions — always check
  git stash list at session start
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.907963+00:00'
updated_at: '2026-06-16 10:27:07.907964+00:00'
---

# borg-assimilate-pr-shipping-checklist

## description

The full sequence for shipping a PR through the borg-assimilate process, from checklist completion to merge and archival
