---
id: 20260414-db-per-project-warehouse
date: '2026-06-16'
project: snowfort
domain: architecture
tags:
- snowflake
- multi-tenancy
- cost-attribution
- warehouse
- database-design
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.861872+00:00'
updated_at: '2026-06-16 10:27:07.861873+00:00'
---

# 20260414-db-per-project-warehouse

## decision

Use database-per-project with per-project warehouses; rely on ACCOUNT_USAGE views for cost attribution at current scale

## context

Designing Snowflake resource organization for a multi-project platform

## reasoning

Content-based naming validated as sufficient for organization. ACCOUNT_USAGE views provide adequate cost visibility at ~$60/mo total spend. Dedicated resource tagging adds governance overhead that isn't justified yet.
