---
id: 20260414-terraform-overkill-current-scale
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- terraform
- iac
- snowflake
- scale
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.891027+00:00'
updated_at: '2026-06-16 10:27:07.891029+00:00'
---

# 20260414-terraform-overkill-current-scale

## decision

Do not adopt Terraform for Snowflake IaC at current solo/pre-revenue scale; use schematized SQL scripts instead

## context

Q4 IaC evaluation — whether to use Terraform (snowflake provider), Permifrost, or SQL scripts for Snowflake object management

## reasoning

Terraform adds state management overhead, provider versioning complexity, and CI/CD pipeline requirements that are disproportionate to the object count being managed. SQL scripts in a four-stage pattern (create, grant, seed, teardown) are auditable, portable, and require no external tooling.
