---
id: 20260414-terraform-overkill-dcm-sql
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- terraform
- snowflake
- iac
- dcm
- permifrost
- sql-migrations
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.860764+00:00'
updated_at: '2026-06-16 10:27:07.860764+00:00'
---

# 20260414-terraform-overkill-dcm-sql

## decision

Skip Terraform at current scale; use DCM Projects (Preview, March 2026) + raw SQL (init.sql/apply.sql)

## context

Evaluating IaC tool selection for Snowflake resource management

## reasoning

Terraform introduces provider dependency and state management overhead that isn't justified at current scale. DCM Projects (native Snowflake IaC, in Preview as of March 2026) is sufficient, and raw SQL scripts remain fully auditable.
