# Project Plan: Snowfort Audit — PyPI-Ready Release

*Established: 2026-04-03*

## Objective

Prepare snowfort-audit for public distribution: clean up git history, restore SSO login
support, fix build blockers, and make the package publishable to PyPI.

## Acceptance Criteria

- [ ] Git history is clean with logical, atomic commits
  - Verify: `git log --oneline` shows multiple descriptive commits
- [x] SSO/browser auth is exposed in the CLI login menu
  - Verify: `snowfort login --help` shows browser; login flow tests pass
  - Verified: 2026-04-07
- [x] Package builds cleanly from monorepo path
  - Verify: `python -m build` produces wheel + sdist in `dist/`
  - Verified: 2026-04-07 (snowfort_audit-0.1.0)
- [x] Dev dependency on `pytest-coverage-impact @ file:///` removed or made optional
  - Verify: `pip install -e ".[dev]"` works without local file path
  - Verified: 2026-04-07 (install succeeds)
- [x] `make check` passes (lint + mypy + tests + coverage >= 80%)
  - Verify: `make check` exits 0
  - Verified: 2026-04-07 (665 passed, 86.27% coverage)
- [x] Nothing breaks — all existing tests pass, CLI help works, offline scan runs
  - Verify: `pytest tests/ -v && snowfort audit --help`
  - Verified: 2026-04-07
- [x] Doc-code sync: RULES_CATALOG.md, README, and RULE_APPLICABILITY_MATRIX.md
      match the 83 rules in `get_all_rules()`
  - Verified: 2026-04-07

## Scope Boundaries

- NOT building the Cortex Code skill (separate project)
- NOT publishing to PyPI (just making it publishable)
- NOT restructuring the monorepo root
- If done early: Ship, don't expand.

## Ship Definition

Committed to main with clean git history + `make check` passes +
`python -m build` succeeds + SSO login works.

## Timeline

Target: this session
Estimated effort: 1 session, ~2-3 hours

## Risks

- Git history rewrite on initial WIP commit — low risk since no remote/branches
- `pytest-coverage-impact` removal may break `make coverage-impact` target
- Large unstaged diff requires care during git cleanup
