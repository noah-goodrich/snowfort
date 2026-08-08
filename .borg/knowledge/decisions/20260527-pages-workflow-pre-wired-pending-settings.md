---
id: 20260527-pages-workflow-pre-wired-pending-settings
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- github-pages
- github-actions
- deployment
- pre-launch
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.942091+00:00'
updated_at: '2026-06-16 10:27:07.942092+00:00'
---

# 20260527-pages-workflow-pre-wired-pending-settings

## decision

Ship the Pages workflow and docs/site in the PR but leave activation gated on a manual Settings UI flip rather than automating the enable step

## context

GitHub Pages source cannot be set via workflow file or API without repo admin action; the site needed to be ready to go live immediately after Settings change

## reasoning

All deployable artifacts are pre-wired so the launch action is a single UI click; this avoids any post-merge 'now build the page' work while acknowledging the platform constraint
