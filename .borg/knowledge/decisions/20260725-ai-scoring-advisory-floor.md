---
id: 20260725-ai-scoring-advisory-floor
date: '2026-07-25'
project: snowfort
domain: content-quality
tags:
- noah-writing-voice
- ai-scoring
- publish-pipeline
- claude-plugins
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-07-25 16:57:26.024929+00:00'
updated_at: '2026-07-25 17:54:08.360727+00:00'
---

# 20260725-ai-scoring-advisory-floor

## decision

Replace hard gate of 75 with advisory-with-teeth floor of 65: run scorer, report score + flags, auto-revise top flags, but no hard block on publish.

## context

The noah-writing-voice skill had a hard publish gate of 75. The 2026-05-23 corpus validation revealed the scorer has category errors (Cat 1 staccato + Cat 8 em-dash are inverted against Noah's actual rhythm), causing it to fail Noah's own published work (Long Game Part 2 scored 65). Needed to unblock WAF article drafting without waiting for a full scorer redesign.

## reasoning

The failure is a scorer design error, not a content quality problem. Hard-blocking publish on a broken metric punishes good writing. Advisory mode preserves the scoring signal while allowing human override. Full redesign is scoped to claude-plugins, not snowfort — separating concerns avoids scope creep.
