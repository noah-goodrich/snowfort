---
id: obs-20260725-ai-scorer-category-inversion
session_date: '2026-07-25'
project: snowfort
tool: claude-code
tags:
- noah-writing-voice
- ai-scoring
- claude-plugins
- calibration
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-07-25 16:57:26.028656+00:00'
updated_at: '2026-07-25 17:54:08.585417+00:00'
---

# obs-20260725-ai-scorer-category-inversion

## content

The noah-writing-voice ai-scorer has a category error where Cat 1 (staccato/short sentences) and Cat 8 (em-dash usage) are scored inverted relative to Noah's actual published style. Short punchy sentences and em-dash use are features of Noah's voice, but the scorer penalizes them. This causes the scorer to fail Noah's own Long Game Part 2 article (scores 65 against a hard gate of 75). The scorer was never recalibrated after the 2026-05-23 validation report identified this.

## resolution

Do not trust the raw ai-score as a quality signal without checking which categories drove the penalty. The 2026-05-23 RECOMMENDATIONS.md at `/Users/noah/dev/claude-plugins/noah-writing-voice/validation/2026-05-23-corpus/` documents the specific category errors. Full fix requires a scorer redesign scoped to the claude-plugins project.
