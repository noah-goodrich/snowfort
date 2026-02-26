# Opus Conductor Pattern

## Overview

Complex tasks are decomposed by an advanced model (Opus) into smaller subtasks
that cheaper models (Sonnet, Flash, Cortex Code) execute independently. Each
subtask ends with `make check` to verify correctness before moving on.

## When to Use

| Task Type | Model | Estimated Cost |
|---|---|---|
| New feature design | Opus | $2-5 |
| Task decomposition | Opus | $1-3 |
| Architectural review | Opus | $1-2 |
| Implement a function | Sonnet/Flash | $0.10-0.50 |
| Write tests | Sonnet/Flash | $0.10-0.30 |
| Fix lint errors | Flash | $0.05-0.10 |
| Scaffold from template | Flash | $0.02-0.05 |

## Workflow

1. **Trigger**: Human starts an Opus session with a high-level goal
2. **Read**: Opus reads `.agent/instructions.md`, codebase structure, `make check` output
3. **Plan**: Opus creates a task file in `.agent/tasks/` with specific subtasks
4. **Execute**: Each subtask is run by a cheaper model
5. **Verify**: Each subtask ends with `make check` -- red means fix, green means next
6. **Review**: (Optional) Opus reviews aggregate result for high-stakes changes

## Task File Format

Task files live in `.agent/tasks/` and use this format:

```markdown
# Task: <title>
Date: YYYY-MM-DD
Status: in_progress | completed | blocked

## Context
<1-3 sentences about what and why>

## Subtasks
- [ ] 1. <specific action> — File: `path/to/file.py` — Verify: `make check`
- [ ] 2. <specific action> — File: `path/to/file.py` — Verify: `make check`
- [x] 3. <completed action> — Done

## Acceptance Criteria
- `make check` passes (lint + test + coverage >= 80%)
- No new W9xxx violations introduced
- All modified files have corresponding test updates
```

## Rules for Worker Agents

1. Read `.agent/instructions.md` before starting
2. Work on exactly ONE subtask at a time
3. Run `make check` after each subtask
4. If `make check` fails, fix before moving to next subtask
5. Do not modify files outside the subtask scope
6. Do not make architectural decisions -- escalate to Opus
