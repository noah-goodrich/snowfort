---
id: 20260414-wallpaper-kit-snowflake-rejection-correct
date: '2026-06-16'
project: snowfort
domain: architecture
tags:
- snowflake
- spcs
- postgres
- platform-fit
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
created_at: '2026-06-16 10:27:07.862419+00:00'
updated_at: '2026-06-16 10:27:07.862419+00:00'
---

# 20260414-wallpaper-kit-snowflake-rejection-correct

## decision

Confirmed the original rejection of Snowflake for wallpaper-kit was correct; SPCS unbundling is possible but not recommended

## context

Re-evaluating whether a previous architectural decision to not use Snowflake for wallpaper-kit was sound

## reasoning

4 of 5 original rejection arguments held. Nuance: SPCS adds $50/mo vs Postgres at $10/mo — unbundling Snowflake Cortex from SPCS is technically possible but the cost differential doesn't justify the complexity.
