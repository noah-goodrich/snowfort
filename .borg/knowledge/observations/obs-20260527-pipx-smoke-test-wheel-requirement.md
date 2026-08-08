---
id: obs-20260527-pipx-smoke-test-wheel-requirement
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- ci
- pipx
- packaging
- smoke-test
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.945730+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260527-pipx-smoke-test-wheel-requirement

## content

The pipx smoke-test workflow builds a wheel first and installs from it, rather than using `pip install -e .` or running pytest directly. This is intentional: it catches packaging errors (missing files in MANIFEST, incorrect entry_points, import failures in installed mode) that the regular test suite running in editable mode will not surface.

## resolution

Pattern to preserve: any CI workflow validating the user-facing install experience should build and install the wheel, not use the development install.
