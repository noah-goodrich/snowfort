---
id: obs-20260616-branch-protection-check-history-requirement
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- github
- branch-protection
- required-checks
- bootstrapping
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.920976+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-branch-protection-check-history-requirement

## content

GitHub branch protection required status checks can only reliably reference check names that have previously run on the repository. Attempting to add a required check for a job that exists only in an open PR (not yet merged to main) may be silently ignored or cause unpredictable behavior.

## resolution

Use the two-phase bootstrap pattern: protect with existing checks first, merge the CI PR, then expand required checks. Document the Phase 2 command in the PR body so it isn't forgotten post-merge.
