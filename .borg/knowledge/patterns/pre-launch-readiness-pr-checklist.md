---
id: pre-launch-readiness-pr-checklist
project: snowfort
domain: infrastructure
tags:
- pre-launch
- open-source
- github
- release-process
preconditions: []
steps:
- Rewrite README with stranger-first hook and install command in first 50 lines
- Add CONTRIBUTING.md (~500 words, ELI10 audience, in/out-of-scope rule guidance)
- Add SECURITY.md with GitHub Security Advisories as primary channel, email fallback,
  SLO commitments
- Add .github/FUNDING.yml pointing at maintainer's GitHub Sponsors handle
- Reconcile all rule counts across all documentation files to a single source of truth
- Add response-time SLO as verbatim spec language in README Support section
- Add auto-label issues workflow (regex-based, no external dependencies)
- Add pipx smoke-test workflow (matrix OS × Python version; installs from built wheel)
- Build static landing page in docs/site with GitHub Actions Pages workflow
- Disable any rules with high false-positive risk as default_disabled
pitfalls:
- Rule counts drift across multiple documentation files (RULES_CATALOG, PERFORMANCE_STRATEGIES,
  STRATEGIC_ANALYSIS, EXECUTIVE_SUMMARY, README) — all must be updated in the same
  PR or counts diverge immediately
- GitHub Pages and GitHub Sponsors cannot be enabled programmatically; budget time
  for manual Settings UI actions that block the launch even after all code is merged
- pipx smoke-test must build from the wheel (not editable install) to catch packaging
  issues that pytest alone won't surface
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.943042+00:00'
updated_at: '2026-06-16 10:27:07.943042+00:00'
---

# pre-launch-readiness-pr-checklist

## description

Structured 10-item checklist for taking a private developer tool to public open-source launch, covering documentation, security, funding, CI, and landing page
