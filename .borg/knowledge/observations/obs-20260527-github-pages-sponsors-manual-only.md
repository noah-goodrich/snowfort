---
id: obs-20260527-github-pages-sponsors-manual-only
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- github-pages
- github-sponsors
- deployment
- launch-blockers
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.943959+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260527-github-pages-sponsors-manual-only

## content

Both GitHub Pages source selection and GitHub Sponsors program enrollment require manual action in the repository Settings UI. These cannot be triggered by committing workflow files or FUNDING.yml alone — the files are necessary but not sufficient. A launch that depends on both will have at least two mandatory human-in-the-loop steps that no amount of pre-wiring can eliminate.

## resolution

Document these as explicit launch blockers in the session handoff. Pre-wire all artifacts (workflow, docs/site, FUNDING.yml) so the human action is a single click with no follow-up build work required.
