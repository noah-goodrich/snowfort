# Task: Add New Audit Rule — [RULE_NAME]
Date: YYYY-MM-DD
Status: pending

## Context
Add a new [PILLAR] audit rule that checks for [DESCRIPTION].

## Subtasks
- [ ] 1. Create rule class in `src/snowfort_audit/domain/rules/[PILLAR].py`
  - Inherit from the base Rule class
  - Implement `check_offline()` with SQL query against ACCOUNT_USAGE views
  - Implement `check_online()` if real-time scanning is needed
  - Add severity, pillar, and description attributes
  - File: `src/snowfort_audit/domain/rules/[PILLAR].py`
  - Verify: `make lint`

- [ ] 2. Register rule in the pillar registry
  - File: `src/snowfort_audit/domain/registry.py` or appropriate location
  - Verify: `make lint`

- [ ] 3. Write unit tests
  - Test check_offline with mock cursor returning sample data
  - Test check_offline with empty result set (no findings)
  - Test edge cases (NULL values, missing columns)
  - File: `tests/unit/test_[PILLAR].py`
  - Verify: `make check`

## Acceptance Criteria
- `make check` passes
- Rule produces correct findings for known-bad data
- Rule produces no findings for known-good data
- Coverage for the new rule file >= 80%
