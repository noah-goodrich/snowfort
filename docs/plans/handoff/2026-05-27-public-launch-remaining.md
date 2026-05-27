# Handoff — Public launch remaining steps

**Created:** 2026-05-27
**For:** borg + Claude Code CLI continuation (and Noah's manual GitHub UI steps)
**Parent plan:** none (implicit `pre-launch-readiness` scope is covered by PR #22 itself —
no PROJECT_PLAN.md was materialized)

## Current state

PR #22 (`feat/pre-launch-readiness-2026-05-26` → `main`) is open with all 10 pre-launch items
shipped and 1328 tests passing. Working tree is clean. The branch contains the public landing
page (`docs/site`), Pages workflow (`.github/workflows/pages.yml`), `FUNDING.yml`,
`CONTRIBUTING.md`, `SECURITY.md`, response-time SLO, auto-label workflow, and the pipx
smoke-test workflow.

Full breakdown of what shipped is in the checkpoint at
`.borg/checkpoints/2026-05-27-0916.md`.

## What's blocked

All three remaining steps are gated on Noah and require GitHub UI actions — no further code
changes are needed for launch.

1. **PR #22 review + squash-merge.** Snowfort intentionally keeps review-required because
   it's the public-facing repo. Squash-on-merge collapses 12 commits → 1 and hides the two
   near-duplicate pairs from the parallel-session race.
2. **Enable GitHub Pages.** Repo Settings → Pages → Source = "GitHub Actions". Once enabled,
   `.github/workflows/pages.yml` runs and the site goes live at
   `https://noah-goodrich.github.io/snowfort/`.
3. **Enable GitHub Sponsors.** Repo Settings → enable Sponsors, then configure the 3 tiers
   in the sponsors dashboard ($5 / $25 / $500). The `FUNDING.yml`-driven Sponsor button
   activates once tiers exist.

## Next action

Recommended order (lowest risk first):

```sh
# 1. Review the PR diff one more time
gh pr view 22 --repo noah-goodrich/snowfort --web

# 2. Squash-merge
gh pr merge 22 --squash --delete-branch --repo noah-goodrich/snowfort

# 3. Enable Pages (must be done in browser — no gh CLI shortcut for the Source picker)
open "https://github.com/noah-goodrich/snowfort/settings/pages"

# 4. Enable Sponsors (browser)
open "https://github.com/sponsors/noah-goodrich/dashboard"
```

After (3) flips, the Pages workflow should fire automatically against `main` and publish
the landing page. After (4), confirm the Sponsor button appears on the repo home page.

## Open questions

- **Should `pre-launch-readiness` be promoted to an assimilated plan slug?** No
  `PROJECT_PLAN.md` exists because the scope was implicit and PR #22 covers it. Once #22
  merges, consider writing a minimal retrospective at
  `docs/plans/assimilated/2026-05-26-pre-launch-readiness.md` summarizing the 10 items shipped
  — useful when the next launch-style initiative kicks off and wants a reference.
- **Response-time SLO monitoring.** The 7-day acknowledgement SLO is documented in README and
  SECURITY.md. No tooling enforces it yet — first inbound issues will be the test. Decide
  later whether to wire a stale-issue bot or rely on manual triage.
- **Cortex AI Governance pillar follow-on work.** `docs/research/thread2-waf-framework/analysis.md`
  has more rule candidates than the current 164. Out of scope for launch; queue as the next
  initiative once the public launch settles.
