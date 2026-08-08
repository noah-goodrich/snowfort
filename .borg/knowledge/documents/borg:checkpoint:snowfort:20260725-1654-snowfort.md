---
id: borg:checkpoint:snowfort:20260725-1654-snowfort
source: borg
doc_type: checkpoint
project: snowfort
slug: 20260725-1654-snowfort
title: null
metadata: {}
tags: []
status: active
filed_date: null
shipped_date: null
fs_path: null
body_sha256: 2239824493ca3f8fc473b15f7c1a4e9781ce98888fca3674a611919c08d7dcdd
captured_at: '2026-07-25 16:54:14.548436+00:00'
deleted_at: null
created_at: '2026-07-25 16:54:14.549516+00:00'
updated_at: '2026-07-25 16:54:14.549517+00:00'
---

# borg:checkpoint:snowfort:20260725-1654-snowfort

## body

## 1. Goal

Resume the article series: resolve two open `noah-writing-voice` skill decisions, then propose the WAF Article 1
outline (the practical "how" companion to the published Long Game trilogy, built around snowfort) for Noah to
approve before drafting.

## 2. Accomplished

- Read the validation doc (`docs/research/2026-06-11-summit-2026-article-validation.md`) and located
  `RECOMMENDATIONS.md` at `/Users/noah/dev/claude-plugins/noah-writing-voice/validation/2026-05-23-corpus/`.
- Verified current skill state: `ai-scoring` still enforces a hard **75** gate, em-dash still banned, no era lock —
  none of the 2026-05-23 report's recommendations have been applied yet.
- Resolved the two decisions (Noah said "follow your recommendations"):
  - **ai-scoring publish threshold →** advisory-with-teeth, **floor 65** (run scorer, report score + flags,
    auto-revise top flags, no hard block). Rationale: the scorer has a category error (Cat 1 staccato + Cat 8
    em-dash inverted against Noah's real rhythm) that fails his own published work (Long Game Part 2 = 65). Full
    redesign is a separate `claude-plugins` task, not a snowfort-drone job.
  - **Voice-era lock →** do NOT lock globally. Use **Long Game era *mechanics*** (short sentences, high
    contractions, weight-bearing single-sentence landings, "Your move" CTA, italic "A Note on Process" coda) +
    **tooling-launch era *structure*** ("Origin Story / why I built snowfort" spine) for the technical WAF series.
- Answered Noah's four clarifying questions: (1) recommended path above; (2) problem = scorer category error, not
  the number; (3) **no existing WAF drafts** anywhere — corpus articles are already-published calibration material,
  not drafts, so Article 1 is from scratch; (4) agreed snowfort must be pipx-installable + clean `snowfort audit
  scan` before **publish** — draft can proceed in parallel, publish gated on readiness.
- Presented a full WAF Article 1 outline ("The Blueprint and the Inspection", working title): Origin-Story opening →
  the blueprint (5 pillars, Nov 2025) → the inspection (live state, 162 rules / 23 modules) → honest positioning
  (no "category of one"; contrast Trust Center / CoCo Governance Skills / AWS Custom WAF Lens) → CTA + series map.

## 3. Ready to Commit

Nothing new staged this session. The checkpoint file below is the only new artifact.

Pre-existing uncommitted changes (predate this session — leave to their owners, do NOT fold in): `.gitignore`,
`CLAUDE.md`, `docs/brainstorms/`, `docs/research/`. No `/simplify` needed — no source files were touched this
session (article/skill work only, no drafts written to disk yet).

## 4. Blockers

- **Central metaphor rejected.** Noah did not like any of the three proposed spines (building-code-vs-inspection,
  fire-warden lineage, annual-physical). The metaphor is load-bearing for the whole series, so drafting is blocked
  until a metaphor lands. This is the single open item.
- Decisions and outline structure are otherwise approved; only the metaphor is unresolved.

## 5. Next Session

- **Start here:** find a WAF-series central metaphor Noah likes — none of the three offered worked. Do NOT re-pitch
  the rejected three. Consider fresh angles (e.g. the tool-companion "Origin Story" framing itself as the spine
  rather than an external analogy; or ask Noah what metaphors *do* resonate before generating more). The metaphor
  must support the honest differentiator: **live-state scan vs. self-report questionnaire** across all five pillars.
- Once the metaphor lands, the rest of the outline is approved — proceed to draft using **Long Game mechanics +
  tooling-launch Origin-Story structure**, `snowflake-article` + `noah-voice` skills, ai-scoring advisory floor 65.
- Keep commits/PRs **generic** — this repo is PUBLIC.
- **Do not publish** until snowfort-audit is pipx-installable and `snowfort audit scan` runs clean for a new user;
  offer the readiness gap-list as a side deliverable as publish approaches.
- Key files: outline facts in `docs/research/2026-06-11-summit-2026-article-validation.md` (162 rules / 23 modules
  breakdown, positioning, competitor contrast); decision rationale in
  `/Users/noah/dev/claude-plugins/noah-writing-voice/validation/2026-05-23-corpus/RECOMMENDATIONS.md`.
