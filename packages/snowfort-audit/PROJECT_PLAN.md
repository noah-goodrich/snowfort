# Project Plan: Snowfort Audit v0.2.0 — Performance Engineering

*Established: 2026-04-08*

## Objective

Implement all 4 performance strategies (shared query cache, N+1 elimination,
batch view DDL, SQL rewrites) plus per-rule timing instrumentation so
production scans complete in under 60 minutes.

## Acceptance Criteria

- [ ] Per-rule timing: `--profile` flag prints per-rule execution time sorted
      by duration; works with sequential and parallel modes
  - Verify: `snowfort audit scan --offline --path examples/offline_showcase --profile`
    shows timing per rule
- [ ] Shared query cache: common queries (SHOW WAREHOUSES, SHOW USERS,
      SHOW DATABASES, TAG_REFERENCES, TABLES) run once via ScanContext
  - Verify: With `--log-level DEBUG`, each shared query appears exactly once
- [ ] N+1 elimination: COST_009, PERF_001, SEC_008 use batch queries instead
      of per-object loops
  - Verify: `--profile` shows these rules complete in <5s each
- [ ] Batch view DDL: view-phase uses ACCOUNT_USAGE.VIEWS instead of per-view
      GET_DDL loop
  - Verify: view-phase timing is a single query, not N queries
- [ ] SQL rewrites: COST_007 and COST_013 use CTE + LEFT JOIN instead of
      correlated NOT EXISTS with FLATTEN
  - Verify: no `NOT EXISTS ... LATERAL FLATTEN` pattern in rule source
- [ ] Default workers changed from 1 to 4
  - Verify: `snowfort audit scan --help` shows `default=4`
- [ ] Nothing breaks: `make check` passes (lint + mypy + tests + coverage >= 80%)
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
