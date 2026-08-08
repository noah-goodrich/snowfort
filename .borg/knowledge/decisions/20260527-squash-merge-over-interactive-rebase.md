---
id: 20260527-squash-merge-over-interactive-rebase
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- git
- pr-workflow
- merge-strategy
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.940756+00:00'
updated_at: '2026-06-16 10:27:07.940756+00:00'
---

# 20260527-squash-merge-over-interactive-rebase

## decision

Use squash-on-merge for PR #22 rather than interactive rebase to collapse 12 commits to 1

## context

A parallel-session race condition produced near-duplicate commit pairs on the feature branch, resulting in 12 commits for 10 logical items

## reasoning

Squash-on-merge is simpler to execute and achieves the same clean history result without requiring manual interactive rebase steps. The duplicate commits were an artifact of parallel sessions, not intentional history worth preserving.
