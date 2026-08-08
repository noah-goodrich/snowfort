---
id: 20260616-cost038-040-sql-exclude-system-snowfort
date: '2026-06-16'
project: snowfort
domain: code-quality
tags:
- snowflake
- cortex
- sql
- cost-rules
- filtering
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.919308+00:00'
updated_at: '2026-06-16 10:27:07.919309+00:00'
---

# 20260616-cost038-040-sql-exclude-system-snowfort

## decision

Add SQL_EXCLUDE_SYSTEM_AND_SNOWFORT filter to all three COST_038/039/040 TABLE_STORAGE_METRICS WHERE clauses

## context

Cortex WIP rules were querying TABLE_STORAGE_METRICS without excluding Snowflake system tables and the snowfort evaluation schema itself, producing noisy/incorrect results

## reasoning

System tables and the evaluation schema are not customer-owned objects; including them would skew cost attribution and generate false-positive recommendations
