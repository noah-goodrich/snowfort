---
id: obs-20260616-pr-merge-order-with-branch-protection
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- github
- branch-protection
- merge-ordering
- ci-cd
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.922282+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-pr-merge-order-with-branch-protection

## content

After enabling branch protection requiring 1 PR review + `test` status check, even no-code archive/doc PRs (like PR #13) are blocked until CI passes and a reviewer approves. This can surprise teams who expect trivial PRs to merge instantly.

## resolution

Account for this in merge queue planning — schedule doc/archive PRs with enough lead time for a reviewer pass. Consider whether the `test` check is necessary for paths that contain only markdown files (could use path-filtered required checks if GitHub supports it).
