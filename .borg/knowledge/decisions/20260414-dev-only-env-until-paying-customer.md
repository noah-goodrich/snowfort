---
id: 20260414-dev-only-env-until-paying-customer
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- environments
- dev-prod
- staging
- cost
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.861202+00:00'
updated_at: '2026-06-16 10:27:07.861202+00:00'
---

# 20260414-dev-only-env-until-paying-customer

## decision

Maintain DEV-only until first paying customer; add PRD at first paying customer; add STG at first team member

## context

Deciding on multi-environment Snowflake setup during early-stage development

## reasoning

Three-environment setup is premature and adds cost and operational overhead with no return at Stage 1. Phased environment introduction aligns infrastructure cost to business milestones.
