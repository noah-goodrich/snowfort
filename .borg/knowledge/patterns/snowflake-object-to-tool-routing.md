---
id: snowflake-object-to-tool-routing
project: snowfort
domain: infrastructure
tags:
- snowflake
- iac
- terraform
- dbt
- tool-selection
preconditions: []
steps:
- Infrastructure objects (databases, warehouses, roles, users) → SQL IaC scripts (create/grant/teardown
  pattern)
- Transformation logic (views, stored procedures, UDFs used in pipelines) → dbt models
- Data quality rules → dbt tests or DMF (Data Metric Functions) if native Snowflake
  monitoring is needed
- Secrets and credentials → never in SQL scripts; use cloud secrets manager (AWS SSM,
  GCP Secret Manager) with WIF bridge
- 'Terraform only when: object count >50, multi-account, or CI/CD drift detection
  is required'
pitfalls:
- 'dbt scope creep: dbt should own transformation, not infrastructure creation — do
  not use dbt pre-hooks for warehouse or role management'
- Mixing tools for the same object type creates ownership ambiguity and state conflicts
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.896020+00:00'
updated_at: '2026-06-16 10:27:07.896024+00:00'
---

# snowflake-object-to-tool-routing

## description

Route Snowflake object types to the correct management tool based on object volatility and ownership semantics
