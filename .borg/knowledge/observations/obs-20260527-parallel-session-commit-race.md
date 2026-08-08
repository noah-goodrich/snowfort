---
id: obs-20260527-parallel-session-commit-race
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- git
- parallel-sessions
- claude-code
- commit-history
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.943515+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260527-parallel-session-commit-race

## content

Running multiple claude-code sessions concurrently on the same feature branch produces near-duplicate commit pairs. The session that commits second will have an identical or near-identical diff to the first session's commit for the same item, resulting in inflated commit counts (12 instead of 10 for 10 logical items).

## resolution

Accepted as tolerable when squash-on-merge is the merge strategy. If linear history per item is required, use interactive rebase fixup before opening the PR, or serialize sessions so only one writes to the branch at a time.
