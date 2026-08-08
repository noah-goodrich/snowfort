---
id: 20260616-coverage-gate-raise-85
date: '2026-06-16'
project: snowfort
domain: testing
tags:
- coverage
- ci-cd
- github-actions
- quality-gates
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.917765+00:00'
updated_at: '2026-06-16 10:27:07.917766+00:00'
---

# 20260616-coverage-gate-raise-85

## decision

Raise coverage gate from 80% to 85% as part of CI hardening PR #11

## context

Incrementally tightening quality gates alongside new SAST and regression checks

## reasoning

Bundling the coverage increase with other CI improvements reduces the number of PRs needed and signals a coordinated quality uplift rather than a one-off gate change
