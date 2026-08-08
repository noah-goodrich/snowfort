---
id: 20260527-borg-state-separate-branch
date: '2026-06-16'
project: snowfort
domain: infrastructure
tags:
- git
- branching
- session-management
- borg
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.941630+00:00'
updated_at: '2026-06-16 10:27:07.941631+00:00'
---

# 20260527-borg-state-separate-branch

## decision

Land Borg state files (checkpoint + handoff) on a separate branch `chore/borg-state-2026-05-27` off main rather than including them in PR #22

## context

Session checkpoint and handoff documents needed to be committed, but PR #22 is a feature branch headed for public launch with squash-on-merge

## reasoning

Keeping operational/meta files out of the feature PR avoids polluting the squashed commit with non-feature content, and keeps the PR diff clean for review
