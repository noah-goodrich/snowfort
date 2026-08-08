---
id: obs-20260616-mutable-default-dict-counter
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- python
- closures
- mutable-default
- simplify
category: gotcha
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.932442+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260616-mutable-default-dict-counter

## content

A mutable dict was being used as a counter inside a closure (to work around Python's closure variable binding rules for integers), which is a known but obscure Python pattern. The `/simplify` pass replaced it with `nonlocal` on a plain integer, which is cleaner and more idiomatic in Python 3.

## resolution

Prefer `nonlocal counter_var` over `counter = {'n': 0}` / `counter['n'] += 1` pattern in closures. The mutable-dict trick predates `nonlocal` (added in Python 3.0) and should not appear in new Python 3 code.
