---
id: 20260616-adversarial-review-path-triggers
date: '2026-06-16'
project: snowfort
domain: code-quality
tags:
- ci-cd
- github-actions
- adversarial-review
- claude
- path-filtering
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.917321+00:00'
updated_at: '2026-06-16 10:27:07.917322+00:00'
---

# 20260616-adversarial-review-path-triggers

## decision

Scope adversarial-review.yml to trigger only on changes to domain/rules/**, infrastructure/cortex*, use_cases/online_scan.py, and sql_safety.py rather than all PRs

## context

Adding AI-powered code review via Claude Opus to catch security/architecture issues; needed to balance thoroughness against API cost and noise

## reasoning

These paths represent the highest-risk surface area (business rules, Cortex infrastructure, SQL safety logic). Broad triggers would burn API quota on docs/test/config changes that don't need adversarial review.
