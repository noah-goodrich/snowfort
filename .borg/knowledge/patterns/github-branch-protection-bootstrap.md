---
id: github-branch-protection-bootstrap
project: snowfort
domain: infrastructure
tags:
- github
- branch-protection
- gh-cli
- ci-cd
- sequencing
preconditions: []
steps:
- 'Phase 1: Apply branch protection with only pre-existing required checks (e.g.,
  `test`) using `gh api repos/{owner}/{repo}/branches/main/protection`'
- Merge the PR that introduces the new CI jobs so those check names appear in the
  repo's status check history
- 'Phase 2: Run the `gh api` command again (or PATCH) to add the new check names (e.g.,
  architecture-lint, bandit, sensitive-outputs) to required_status_checks.contexts'
pitfalls:
- GitHub silently ignores or rejects required check names that have never run on the
  repo — always merge the CI PR first
- 'Branch protection requires the calling token to have admin repo permissions; PAT
  or GitHub App must have `administration: write`'
- After adding branch protection, even 'trivial' PRs like archive doc commits need
  a passing `test` check — factor this into merge ordering
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.919830+00:00'
updated_at: '2026-06-16 10:27:07.919830+00:00'
---

# github-branch-protection-bootstrap

## description

Two-phase approach to adding branch protection with required CI checks when the checks don't yet exist on the target branch
