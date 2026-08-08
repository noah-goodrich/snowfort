---
id: obs-20260414-permifrost-dead
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- permifrost
- iac
- abandoned
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.899271+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-permifrost-dead

## content

Permifrost (the GitLab-originated Snowflake RBAC management tool) is effectively unmaintained as of the 2026 evaluation. It should not be adopted for new projects despite appearing in Snowflake community recommendations that may be cached in training data or older blog posts.

## resolution

Use the four-stage SQL IaC pattern for RBAC management at small scale. Evaluate Terraform snowflake provider only if object count justifies state management overhead.
