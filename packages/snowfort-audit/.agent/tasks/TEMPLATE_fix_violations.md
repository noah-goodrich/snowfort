# Task: Fix Architecture Violations in [FILE]
Date: YYYY-MM-DD
Status: pending

## Context
`pylint --load-plugins=pylint_clean_architecture` reports [N] violations in [FILE].
This task fixes them while maintaining all existing behavior.

## Subtasks
- [ ] 1. Run current architecture check and record violations
  - Command: `pylint [FILE] --load-plugins=pylint_clean_architecture --disable=all --enable=W9001,W9004,W9013,W9301,W9201,W9003,W9014,W9601`
  - Record each violation code and line number

- [ ] 2. Fix each violation
  - W9004 (forbidden import): Move I/O logic behind a Protocol, inject via constructor
  - W9013 (I/O call): Replace direct print/open with injected port
  - W9301 (DI violation): Accept dependency via __init__ parameter instead of instantiating
  - W9601 (immutability): Add frozen=True to @dataclass, remove post-init assignment
  - File: [FILE]
  - Verify: `make lint`

- [ ] 3. Update tests for any changed interfaces
  - File: corresponding test file
  - Verify: `make check`

## Acceptance Criteria
- `make check` passes
- Zero W9xxx violations in [FILE]
- No behavior changes (all existing tests still pass)
