---
id: obs-20260616-stash-cross-session-risk
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- git
- stash
- multi-branch
- session-continuity
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.909748+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-stash-cross-session-risk

## content

A vendor fix (snowflake_gateway.py PAT parallel worker fix) was completed but left in git stash on feat/sql-column-safety-net at session end. Cross-session stashes are easily forgotten, and the fix is required before that branch can be merged correctly.

## resolution

At the start of each session, run git stash list across relevant branches. The next session must: git checkout feat/sql-column-safety-net && git stash pop, then run /simplify on snowflake_gateway.py before committing.
