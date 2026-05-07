# Directive: Add "Running things" Section to CLAUDE.md

*Established: 2026-05-01*
*Parent plan: 2026-05-01-host-first-claude-delegation (borg-collective)*

## Why this exists

borg-collective shipped the host-first Claude switch on 2026-05-01: Claude sessions now run on
the host instead of inside each project's devcontainer, and dispatch env-dependent commands
into the container via `drone exec <project> -- <cmd>`. The container is now a build/test
target, not the Claude home.

snowfort does not yet have a top-level `CLAUDE.md`. Create one so host-Claude knows the
dispatch convention for the snowfort monorepo (currently active package:
`packages/snowfort-audit/`).

## What to do

Create `/Users/noah/dev/snowfort/CLAUDE.md` (repo root) with at least the section below.
Other monorepo-orienting context (per-package conventions, Cortex CLI integration notes) is
welcome but not required by this directive.

### Required section

```markdown
## Running things

Claude runs on the host; the snowfort devcontainer is a `drone exec` dispatch target.

The active package is `packages/snowfort-audit/` — most commands are scoped there.

- **Inside the container** (Python env, ruff, pytest, snowfort-audit's `make` targets):
  - `drone exec snowfort -- make -C packages/snowfort-audit check`
  - `drone exec snowfort -- python3 -m pytest packages/snowfort-audit/tests/ -x -q`
  - `drone exec snowfort -- ruff check --fix packages/snowfort-audit`

- **On the host** (everything else):
  - git, gh, ripgrep, jq, file edits — run directly.
  - `drone status`, `drone up snowfort`, `drone restart snowfort` — run directly.
  - Cortex CLI (`cortex search`, `cortex ...`) — run on host with the user's active
    Snowflake connection. Never proxy Cortex through the container.

If a command fails with "container down", `drone exec` will print
`snowfort: container down — running drone up`, bring the container up, and retry once.
```

## Acceptance Criteria

- [ ] `CLAUDE.md` exists at the repo root (`/Users/noah/dev/snowfort/CLAUDE.md`).
- [ ] Contains a `## Running things` section that explicitly distinguishes container-dispatched
      commands from host commands.
- [ ] Includes at least one concrete `drone exec snowfort -- <cmd>` example using a real
      command (`make check`, pytest, or ruff).
- [ ] Section explicitly notes that the Cortex CLI is host-only.
- [ ] A real session uses `drone exec snowfort -- make -C packages/snowfort-audit check`
      (or similar) successfully end-to-end.

## Out of scope

- Migrating the existing `packages/snowfort-audit/docs/directives/RULE_AUTHORING_CHECKLIST.md`
  or anything else inside the snowfort-audit package.
- Adding a per-package CLAUDE.md (e.g., `packages/snowfort-audit/CLAUDE.md`) — that's a
  follow-up if the monorepo grows.

## When to assimilate

When the acceptance criteria are met and one real session has dispatched a `drone exec snowfort`
command successfully. Move the file to `docs/plans/assimilated/`.
