# Project Plan: Directive D — Sensitive Data Detection
*Established: 2026-04-30*

## Objective

Add 5 governance rules (GOV_030–034) that detect sensitive columns via configurable column-name
regex patterns, cross-reference against existing classification tags and masking policies, flag
only the unprotected gaps, and optionally sample content for confirmation.

## Acceptance Criteria

- [ ] `make check` green, coverage ≥ 80%.
  - Verify: `cd packages/snowfort-audit && ruff check src/ tests/ && .venv/bin/python -m pytest tests/ -q --cov=src/snowfort_audit --cov-fail-under=80`

- [ ] All 5 rules present in `sensitive_data.py` with correct IDs (GOV_030–034).
  - Verify: `grep '"GOV_03[0-4]"' src/snowfort_audit/domain/rules/sensitive_data.py | wc -l` → 5

- [ ] `SensitiveDataThresholds` + `ColumnPatternDef` in `conventions.py`; defaults cover all 10
  column patterns from directive spec (SSN, email, phone, DOB, salary, credit card, passport,
  password, address, IP).
  - Verify: `python -c "from snowfort_audit.domain.conventions import SensitiveDataThresholds; print(len(SensitiveDataThresholds().column_patterns))"` → 10

- [ ] ≥5 unit tests per rule (≥30 total) in `tests/unit/test_sensitive_data_rules.py`.
  - Verify: `pytest tests/unit/test_sensitive_data_rules.py -v | tail -5`

- [ ] `rules_snapshot.yaml` regenerated — GOV_030–034 present.
  - Verify: `grep "GOV_03[0-4]" tests/unit/fixtures/rules_snapshot.yaml | wc -l` → 5

- [ ] `scan_context=None` path returns `[]` for all 5 rules (no cursor required when prefetch
  data is available).
  - Verify: covered by `test_no_cursor_when_scan_context_set` test per rule

- [ ] Regex patterns precompiled at `__init__` time — no `re.compile()` inside `check_online`.
  - Verify: `grep "re.compile" src/snowfort_audit/domain/rules/sensitive_data.py` → only in `__init__`

- [ ] GOV_034 cursor SQL uses quoted identifiers + parameterized LIMIT — no f-string SQL
  interpolation of table/column metadata.
  - Verify: code review of `ContentBasedSensitiveDataCheck.check_online` — no f-string in
    `cursor.execute()` calls containing table/column names

## Scope Boundaries

- NOT building: cross-account sensitive data federation
- NOT building: automated remediation (apply masking policy) — detection only
- NOT building: integration with Snowflake's `SYSTEM$CLASSIFY` live API — we use
  `TAG_REFERENCES` (already-applied classification results only)
- If done early: ship, don't expand scope to Directive E/F

## Ship Definition

1. All acceptance criteria checked
2. `make check` passes
3. Snapshot regenerated and committed
4. Assimilated plan written to `docs/plans/assimilated/2026-04-30-directive-d-sensitive-data.md`

## Risks

- `ACCOUNT_USAGE.COLUMNS` can be very large on accounts with many tables — mitigated by
  precompiling regex and doing all matching in a single O(N×M) pass with M=10 patterns
- GOV_034 content sampling issues a SELECT against production tables — mitigated by opt-in
  default (`enable_content_sampling=False`) and TABLESAMPLE + LIMIT
- `TAG_REFERENCES` `DOMAIN='COLUMN'` key format differs from `tag_refs_index` — mitigated by
  using a dedicated `get_or_fetch("ACCOUNT_USAGE.TAG_REFERENCES_COLUMNS", 0, ...)` fetch with
  explicit column selection (not reusing the existing `tag_refs_index`)
