---
id: 20260527-default-disabled-class-attribute-pattern
date: '2026-06-16'
project: snowfort
domain: architecture
tags:
- rules-engine
- audit-rules
- feature-flags
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.941220+00:00'
updated_at: '2026-06-16 10:27:07.941220+00:00'
---

# 20260527-default-disabled-class-attribute-pattern

## decision

Implement rule opt-out via a generic `default_disabled` class attribute rather than a one-off mechanism

## context

SEC_008 zombie-roles rule needed to be disabled by default to avoid false positives for common configurations, while remaining accessible via --rules SEC_008

## reasoning

A generic class attribute pattern is reusable across any future rules that need the same opt-out behavior, avoiding per-rule special-casing in the rules engine
