---
id: obs-20260414-create-or-replace-resets-grants
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- sql
- grants
- idempotency
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.902282+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-create-or-replace-resets-grants

## content

In Snowflake, `CREATE OR REPLACE` on an object (table, view, schema) resets all existing grants on that object. Running create.sql a second time without re-running grant.sql leaves the object with no grants, silently breaking downstream role access.

## resolution

Always run grant.sql immediately after create.sql in automation. Structure runbooks and CI scripts to treat create+grant as an atomic pair, not independent steps.
