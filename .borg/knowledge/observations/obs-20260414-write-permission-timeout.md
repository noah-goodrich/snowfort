---
id: obs-20260414-write-permission-timeout
session_date: '2026-04-14'
project: snowfort
tool: claude-code
tags:
- claude-code
- permissions
- file-write
- cross-directory
- data-loss
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.863921+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-write-permission-timeout

## content

A ~4,500-word document composed entirely in-memory was lost when a write to an out-of-scope directory triggered a permission prompt that timed out after 10 minutes. Claude Code surfaced an interactive permission prompt for writes outside the session's working directory (`/Users/noah/dev/snowfort`), and the prompt expired before it could be acknowledged, silently discarding the output.

## resolution

Write output files to the same directory as the input file (within the established working directory). For snowfort sessions, target `/Users/noah/dev/snowfort/` rather than sibling directories like `/Users/noah/dev/cortex-handoffs/`. Establish the output path before beginning long-form composition.
