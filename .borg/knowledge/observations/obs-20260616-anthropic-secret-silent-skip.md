---
id: obs-20260616-anthropic-secret-silent-skip
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- github-actions
- anthropic
- secrets
- adversarial-review
- silent-failure
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.920623+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-anthropic-secret-silent-skip

## content

The adversarial-review.yml workflow using `anthropics/claude-code-action` will silently skip (not fail) if the ANTHROPIC_API_KEY repo secret is absent. There is no visible error in the GitHub Actions UI — the job simply exits 0 without performing any review.

## resolution

Run `gh secret set ANTHROPIC_API_KEY` against the repo before merging PR #11. Consider adding an explicit early `env` check step to the workflow that fails loudly if the secret is unset.
