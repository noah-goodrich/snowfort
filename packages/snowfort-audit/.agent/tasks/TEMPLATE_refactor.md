# Task: Refactor [MODULE] — [DESCRIPTION]
Date: YYYY-MM-DD
Status: pending

## Context
[WHY this refactor is needed. What problem it solves.]

## Subtasks
- [ ] 1. Verify baseline: `make check` passes before any changes

- [ ] 2. [Specific refactoring step 1]
  - File: [FILE]
  - Verify: `make check`

- [ ] 3. [Specific refactoring step 2]
  - File: [FILE]
  - Verify: `make check`

- [ ] 4. Update all call sites
  - Search: `rg "old_api_name" src/ tests/`
  - Update each file to use the new API
  - Verify: `make check`

- [ ] 5. Remove old code (no backward compatibility wrappers)
  - Verify: `make check`

## Acceptance Criteria
- `make check` passes
- No backward compatibility wrappers introduced
- All call sites updated to new API
- Coverage maintained or improved
