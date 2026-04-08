# Project Plan: Snowfort Audit v0.2.0 — Performance Engineering

*Established: 2026-04-08*
*Shipped: 2026-04-08 — committed to main, pushed to GitHub*

## Objective

Implement all 4 performance strategies (shared query cache, N+1 elimination,
batch view DDL, SQL rewrites) plus per-rule timing instrumentation so
production scans complete in under 60 minutes.

## Acceptance Criteria

- [x] Per-rule timing: `--profile` flag prints per-rule execution time sorted
      by duration; works with sequential and parallel modes
  - Verify: `snowfort audit scan --offline --path examples/offline_showcase --profile`
    shows timing per rule
- [x] Shared query cache: common queries (SHOW WAREHOUSES, SHOW USERS,
      SHOW DATABASES, TAG_REFERENCES, TABLES) run once via ScanContext
  - Verify: With `--log-level DEBUG`, each shared query appears exactly once
- [x] N+1 elimination: COST_009, PERF_001, SEC_008 use batch queries instead
      of per-object loops
  - Verify: `--profile` shows these rules complete in <5s each
- [x] Batch view DDL: view-phase uses ACCOUNT_USAGE.VIEWS instead of per-view
      GET_DDL loop
  - Verify: view-phase timing is a single query, not N queries
- [x] SQL rewrites: COST_007 and COST_013 use CTE + LEFT JOIN instead of
      correlated NOT EXISTS with FLATTEN
  - Verify: no `NOT EXISTS ... LATERAL FLATTEN` pattern in rule source
- [x] Default workers changed from 1 to 4
  - Verify: `snowfort audit scan --help` shows `default=4`
- [x] Nothing breaks: `make check` passes (lint + mypy + tests + coverage >= 80%)
  - Verify: `make check` exits 0

## Scope Boundaries

- NOT building Snowflake persistence (SNOWFORT database writes)
- NOT adding bootstrap pre-flight check
- NOT adding new rules or closing Q1 2026 feature gaps
- If done early: Ship, don't expand.

## Ship Definition

Committed to main + `make check` passes + `--profile` works on offline scan +
version bumped to 0.2.0 + pushed to GitHub + PyPI release published.

## Timeline

Target: 3-4 sessions
- Session 1: Per-rule timing + default workers + batch view DDL (Strategy 3)
- Session 2: Shared query cache (Strategy 1) — ScanContext + rule refactors
- Session 3: N+1 elimination (Strategy 2) + SQL rewrites (Strategy 4)
- Session 4 (if needed): Fix breakage, tests, ship

## Risks

- ACCOUNT_USAGE.VIEWS may not be accessible with all role configs — need
  graceful fallback to per-view GET_DDL
- Shared query cache changes the Rule interface — every rule using SHOW
  WAREHOUSES etc. needs ScanContext. Biggest refactor, 15+ files.
- Parallel workers + shared cache must be thread-safe — ScanContext must
  be immutable/frozen

## Additional Work Shipped

Beyond the 7 acceptance criteria, this work included:

- Refactored OPS_001, OPS_009, REL_001 to extract private helpers, reducing
  McCabe complexity below ruff's C901 limit of 11
- Fixed mypy override compatibility for all 90 rules: base class Rule.check_online
  now uses `cursor` (non-prefixed) so subclasses are LSP-compatible
- Added `**_kw` to all scan_context methods for full kwargs pass-through
- ScanContext is frozen-by-convention (dataclass, all fields set at construction)
  to support thread-safe parallel worker execution
