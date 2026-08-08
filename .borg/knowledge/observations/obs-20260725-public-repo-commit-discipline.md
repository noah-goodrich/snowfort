---
id: obs-20260725-public-repo-commit-discipline
session_date: '2026-07-25'
project: snowfort
tool: claude-code
tags:
- git
- public-repo
- commit-hygiene
category: gotcha
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-07-25 16:57:26.029553+00:00'
updated_at: '2026-07-25 17:54:08.585417+00:00'
---

# obs-20260725-public-repo-commit-discipline

## content

The snowfort repo is PUBLIC. Commit messages and PR descriptions must be kept generic — no client names, internal codenames, or strategic details should appear in git history. Pre-existing uncommitted changes (`.gitignore`, `CLAUDE.md`, `docs/brainstorms/`, `docs/research/`) predate this session and belong to their owners; they should not be folded into unrelated commits.

## resolution

Review all commit messages before pushing. Treat the repo as externally visible at all times. Coordinate with repo owner before committing pre-existing changes.
