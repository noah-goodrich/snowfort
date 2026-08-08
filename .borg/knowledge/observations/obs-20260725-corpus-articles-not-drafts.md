---
id: obs-20260725-corpus-articles-not-drafts
session_date: '2026-07-25'
project: snowfort
tool: claude-code
tags:
- noah-writing-voice
- corpus
- WAF-series
- article-pipeline
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-07-25 16:57:26.028062+00:00'
updated_at: '2026-07-25 17:54:08.585417+00:00'
---

# obs-20260725-corpus-articles-not-drafts

## content

The corpus articles used by the noah-writing-voice skill for calibration are already-published pieces, NOT unpublished drafts. There are zero existing WAF article drafts anywhere in the repo. A future session that searches for 'existing WAF drafts' will find nothing and should conclude Article 1 is from scratch — not that drafts are missing or lost.

## resolution

Confirmed by explicit search during session. Start WAF Article 1 from blank; do not spend time hunting for drafts.
