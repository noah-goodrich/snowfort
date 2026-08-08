---
id: obs-20260414-cross-dir-permission-prompt
session_date: '2026-04-14'
project: snowfort
tool: claude-code
tags:
- claude-code
- permissions
- working-directory
- file-system
category: tool_behavior
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.864519+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-cross-dir-permission-prompt

## content

Claude Code requires an interactive permission confirmation for file writes to directories outside the session's established working directory. This prompt has a 10-minute timeout. If the user is not actively watching the terminal, the write silently fails — there is no retry or buffered output.

## resolution

Always confirm the output path is within the active working directory before beginning long-form generation tasks. If cross-directory writes are genuinely needed, either (a) expand the allowed directories before starting work, or (b) write to the working directory first and move the file afterward.
