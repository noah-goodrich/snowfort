---
id: obs-20260616-precommit-pytest-not-in-path
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- pre-commit
- pytest
- local-dev
- dx
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.932100+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-precommit-pytest-not-in-path

## content

`pytest` and `python` are not on PATH in the pre-commit hook environment, causing the `tests` and `sensitive-outputs` pre-commit hooks to fail on every local commit even when tests actually pass.

## resolution

Use `SKIP=sensitive-outputs,tests` prefix on every local commit. Long-term fix: configure pre-commit to use the virtualenv python explicitly, or remove the test hook from pre-commit and rely solely on CI for test enforcement. Low priority since CI is the authoritative gate.
