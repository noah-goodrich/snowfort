---
id: 20260725-waf-article-publish-gate
date: '2026-07-25'
project: snowfort
domain: infrastructure
tags:
- snowfort-audit
- pipx
- publish-pipeline
- WAF-series
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-07-25 16:57:26.027320+00:00'
updated_at: '2026-07-25 17:54:08.360727+00:00'
---

# 20260725-waf-article-publish-gate

## decision

Drafting proceeds in parallel with snowfort tooling work, but publish is hard-gated on snowfort being pipx-installable and `snowfort audit scan` running clean for a new user.

## context

WAF Article 1 references snowfort as a live tool readers can use. Publishing before the tool works as described would undermine credibility and create support burden.

## reasoning

The article's core claim is 'live-state scan vs. self-report questionnaire.' That claim is hollow if a reader cannot actually run the tool. Draft-in-parallel avoids blocking creative work, but the publish gate protects the article's integrity.
