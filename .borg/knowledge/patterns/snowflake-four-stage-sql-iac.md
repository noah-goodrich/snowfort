---
id: snowflake-four-stage-sql-iac
project: snowfort
domain: infrastructure
tags:
- snowflake
- iac
- sql
- schema-management
preconditions: []
steps:
- create.sql — CREATE OR REPLACE for databases, schemas, warehouses, roles
- grant.sql — GRANT statements wiring roles to objects and users to roles
- seed.sql — Initial data, file format definitions, stage definitions, any bootstrap
  rows
- teardown.sql — DROP statements in reverse dependency order for full project removal
pitfalls:
- teardown.sql must respect dependency order (drop schemas before databases, revoke
  grants before dropping roles)
- CREATE OR REPLACE is idempotent for most objects but will reset grants on the replaced
  object — re-run grant.sql after any re-create
- Warehouses are not dropped by database teardown; must be explicitly included in
  teardown.sql
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.894895+00:00'
updated_at: '2026-06-16 10:27:07.894896+00:00'
---

# snowflake-four-stage-sql-iac

## description

Manage Snowflake object lifecycle with four schematized SQL script stages instead of Terraform, enabling full project setup and teardown without state management overhead
