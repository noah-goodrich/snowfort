---
id: obs-20260616-collective-review-hard-gate
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- borg-assimilate
- process
- collective-review
- merge-gate
category: domain_knowledge
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.909282+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-collective-review-hard-gate

## content

The Collective review is a mandatory hard gate in the borg-assimilate shipping process. Completing all AC verifications on the checklist (all green) does NOT authorize a merge — The Collective review must still be run as a separate step before gh pr merge is executed.

## resolution

Always run the borg-collective-review skill as the final step before merge, even when the checklist is fully green. Do not merge in the same session as checklist completion without confirming the review was run.
