---
id: 20260414-snowflake-warehouse-per-project
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- snowflake
- warehouses
- cost-attribution
- multi-tenant
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.885410+00:00'
updated_at: '2026-06-16 10:27:07.885413+00:00'
---

# 20260414-snowflake-warehouse-per-project

## decision

Use per-project warehouses rather than a shared warehouse for Snowflake projects

## context

Evaluating account setup strategy for multiple projects (waypoint, wallpaper-kit, future apps) on a single Snowflake account

## reasoning

Per-project warehouses enable clean cost attribution at the warehouse level without requiring resource monitors or custom tagging. At small scale the cost difference is negligible, and the operational clarity outweighs any savings from warehouse sharing.
