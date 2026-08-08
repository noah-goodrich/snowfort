---
id: obs-20260616-stale-deleted-workflow-check
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- github-actions
- ci
- branch-protection
- workflow
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.931734+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-stale-deleted-workflow-check

## content

After deleting a GitHub Actions workflow file (adversarial-review.yml) in a merged PR, GitHub continues to display old failed runs of that workflow as a check on subsequent PRs. The check is not listed as 'required' so it does not block merges, but it appears as a failed check in the PR UI and causes confusion about whether CI is actually passing.

## resolution

Confirm the check is not in the required checks list — if not required, it is cosmetic noise only. The old run records should age out naturally. If they persist, inspect the Actions tab for any cached workflow definition that might still be triggering. No immediate action required as long as all required checks are green.
