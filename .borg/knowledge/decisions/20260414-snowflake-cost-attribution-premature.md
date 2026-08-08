---
id: 20260414-snowflake-cost-attribution-premature
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- cost-attribution
- finops
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
created_at: '2026-06-16 10:27:07.889580+00:00'
updated_at: '2026-06-16 10:27:07.889583+00:00'
---

# 20260414-snowflake-cost-attribution-premature

## decision

Defer formal cost attribution tooling (resource monitors, query tags, DMFs) until monthly spend materially exceeds $60/mo

## context

Evaluating whether to implement Snowflake cost attribution patterns at current solo/pre-revenue scale

## reasoning

Cost attribution infrastructure has setup and maintenance cost. At $60/mo the variance you can detect is smaller than the time cost of building the system. Per-project warehouses provide sufficient coarse-grained attribution for now.
