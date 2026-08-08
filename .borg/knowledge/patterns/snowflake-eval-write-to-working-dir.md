---
id: snowflake-eval-write-to-working-dir
project: snowfort
domain: workflow
tags:
- claude-code
- file-write
- permissions
- long-form-generation
preconditions: []
steps:
- Confirm the session working directory (e.g., `/Users/noah/dev/snowfort`)
- Declare the output file path explicitly at session start, co-located with the input
  file in the working directory
- If the natural output path is outside the working directory, either expand allowed
  directories before beginning or plan a post-write move
- 'Begin long-form composition only after the output path is confirmed writable (optionally:
  create an empty placeholder file first to verify permissions)'
- Write the output file before ending the session; do not rely on conversation history
  as a buffer
pitfalls:
- Writing to a sibling directory (e.g., `/Users/noah/dev/cortex-handoffs/`) triggers
  a permission prompt with a 10-minute timeout — if unattended, all composed content
  is lost
- There is no automatic retry or recovery if the permission prompt times out; the
  content exists only in conversation history which does not persist across sessions
- Creating the output directory path implicitly (via a write to a non-existent directory)
  may also trigger the permission prompt
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.863062+00:00'
updated_at: '2026-06-16 10:27:07.863062+00:00'
---

# snowflake-eval-write-to-working-dir

## description

Safe pattern for producing long-form written output in Claude Code sessions — avoids permission timeout data loss by anchoring output to the working directory before beginning composition.
