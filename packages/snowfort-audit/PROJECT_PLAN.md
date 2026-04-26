# Project Plan: SQL Column-Name Safety Net
*Established: 2026-04-25*

## Objective

Add a schema-fixture regression layer so SQL column-name mistakes in ACCOUNT_USAGE queries
are caught by `make check` instead of discovered against a live account. As a byproduct,
improve readability of the three highest-traffic rule files by naming cursor result columns
at the unpack point rather than referencing them by magic integer index.

## Background

Eight bugs were fixed in commit `5167e00` where rules queried ACCOUNT_USAGE views using
column names that don't exist (`USAGE_TIME`, `FINDING_TYPE`, `START_TIME` in the wrong
view, etc.). The shared prefetch paths (`scan_context.tables`, `tag_refs`, grants) are
already protected by `TC_*/TR_*/GTR_*` constants. The gap is in rule-owned queries that
run their own `cursor.execute()` against ACCOUNT_USAGE views with no validation layer.

## Acceptance Criteria

- [ ] AC-1: Schema fixture module exists
  - `tests/fixtures/account_usage_schema.py` exports
    `ACCOUNT_USAGE_SCHEMA: dict[str, frozenset[str]]` covering ≥ 13 views:
    the 8 that had bugs + 5 other commonly-used views.
  - Verify: `python -c "from tests.fixtures.account_usage_schema import
    ACCOUNT_USAGE_SCHEMA; assert len(ACCOUNT_USAGE_SCHEMA) >= 13"`

- [ ] AC-2: Column-name regression tests for all 8 previously-fixed rules
  - `tests/unit/test_sql_column_names.py` has ≥ 8 tests, each asserting a rule's
    SQL references only columns present in `ACCOUNT_USAGE_SCHEMA`. No new hardcoded
    `assert "COL" in sql` one-offs — all checked via the fixture dict.
  - Verify: `pytest tests/unit/test_sql_column_names.py -v` — all pass

- [ ] AC-3: Readability unpack pass on 3 highest-traffic files
  - `cost.py` (26 raw usages), `op_excellence.py` (17), `security.py` (12).
  - Every `row[N]` in a self-contained query gets a named variable at the unpack
    point (e.g., `wh_name, credit_usage = row[0], row[1]`).
  - Verify: `grep -c "row\[[0-9]\]"
    packages/snowfort-audit/src/snowfort_audit/domain/rules/{cost,op_excellence,security}.py`
    shows ≤ 4 each

- [ ] AC-4: Regression — nothing breaks
  - Verify: `docker exec -w /development/packages/snowfort-audit
    snowfort-snowfort-audit-app-1 make check` passes with ≥ 942 tests and
    coverage ≥ 80%

## Scope Boundaries

- NOT `cortex_cost.py` — its 25 usages span 18 tiny query functions across Cortex
  views that evolve with each Cortex product release; a fixture would go stale
  constantly
- NOT a SQL parser — use string search / regex on simple `SELECT col1, col2 FROM
  view` patterns only; CTEs and subqueries are out of scope
- NOT fixtures for undocumented internal views where column lists cannot be verified
  against public Snowflake docs
- If done early: ship what we have, don't expand to `cortex_cost.py` or remaining
  rule files

## Ship Definition

Branch off `feat/trustworthy-output` → PR opened → CI passes → merged into
`feat/trustworthy-output`

## Timeline

Target: 2 sessions (~2 hours each)
- Session 1: `account_usage_schema.py` fixture + `test_sql_column_names.py` (AC-1, AC-2)
- Session 2: Readability unpack pass on 3 files + `make check` cleanup (AC-3, AC-4)

## Risks

- **Fixture staleness**: Snowflake updates ACCOUNT_USAGE schemas without versioning.
  Mitigate: add a comment in the fixture linking to the Snowflake docs page and noting
  the date the column list was verified.
- **Unpack pass introduces subtle bugs**: Renaming `row[2]` to a variable at 50+ sites
  fails silently if the variable order doesn't match the SELECT list. Each site needs
  manual verification — no find-and-replace.
- **Regex column extraction misses aliases**: `COUNT(*) AS cnt` won't be caught by
  a naive column-name extractor. Constrain tests to direct column references only and
  document the limitation in the test module docstring.
