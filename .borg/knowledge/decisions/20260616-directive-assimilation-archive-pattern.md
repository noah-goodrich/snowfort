---
id: 20260616-directive-assimilation-archive-pattern
date: '2026-06-16'
project: snowfort
domain: architecture
tags:
- documentation
- directives
- workflow
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.930392+00:00'
updated_at: '2026-06-16 10:27:07.930392+00:00'
---

# 20260616-directive-assimilation-archive-pattern

## decision

Move completed directive docs to `assimilated/` with filename encoding the date and directive name, and mark all criteria `[x]` with a ship date inline

## context

Directive B (warehouse-sizing.md) was fully implemented across multiple PRs and needed to be closed out cleanly

## reasoning

Keeps the active `directives/` directory uncluttered while preserving the full record of what was shipped and when. Encoding date + name in filename makes the archive self-indexing without requiring a separate manifest.
