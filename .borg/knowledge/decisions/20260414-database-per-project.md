---
id: 20260414-database-per-project
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- database-design
- isolation
- multi-project
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.893915+00:00'
updated_at: '2026-06-16 10:27:07.893916+00:00'
---

# 20260414-database-per-project

## decision

Use database-per-project isolation in Snowflake rather than schema-per-project within a shared database

## context

Q2 account setup — how to organize Snowflake objects across multiple projects on one account

## reasoning

Database-level isolation provides cleaner RBAC boundaries, makes cross-project access explicit (requires cross-database grants), and maps naturally to project lifecycle (drop database = full project teardown). Schema-per-project in a shared DB creates implicit coupling.
