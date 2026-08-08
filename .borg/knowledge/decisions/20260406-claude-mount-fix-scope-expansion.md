---
id: 20260406-claude-mount-fix-scope-expansion
date: '2026-06-11'
project: snowfort
domain: infrastructure
tags:
- devcontainer
- dotfiles
- claude
- docker-compose
- scope
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-11 20:31:24.651769+00:00'
updated_at: '2026-06-11 20:31:24.651770+00:00'
---

# 20260406-claude-mount-fix-scope-expansion

## decision

Fix the missing claude dotfiles mount in both snowfort and wallpaper-kit immediately rather than only snowfort (the original scope)

## context

While comparing snowfort to wallpaper-kit as a reference, the same missing ~/.config/dotfiles/claude volume mount was identified in both projects.

## reasoning

The gap was identical in both projects, wallpaper-kit was already open for comparison, and the fix was a single-line addition. Deferring wallpaper-kit would require a separate context-load later for a trivial change.
