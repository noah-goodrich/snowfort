# Snowfort

Snowflake cost governance and WAF compliance auditor. Scans warehouse usage and resource configuration
against Snowflake Well-Architected Framework (WAF) policies, flags violations by severity and pillar,
and produces structured JSON manifests for triage and remediation guidance.

## Running things

Claude runs on the host; the snowfort devcontainer is a `drone exec` dispatch target.

- **Inside the container** (Python toolchain, Snowflake connectivity, test runner):
  - `drone exec snowfort -- make check` — full pre-merge gate (lint + mypy + tests + coverage ≥ 80%)
  - `drone exec snowfort -- make test` — run pytest only
  - `drone exec snowfort -- make lint` — ruff + pylint-clean-architecture + import-linter
  - `drone exec snowfort -- make mypy` — type checking
  - `drone exec snowfort -- make coverage` — full coverage report with HTML output
  - `drone exec snowfort -- make coverage-check` — enforce ≥ 80% threshold (used in CI gate)
  - `drone exec snowfort -- snowfort audit --help` — CLI entry point
  - `drone exec snowfort -- snowfort audit scan --manifest` — produce JSON violation manifest

- **On the host** (everything else):
  - git, gh, ripgrep, jq, file edits — run directly.
  - `drone status`, `drone up snowfort`, `drone restart snowfort` — run directly.
  - Snowflake queries and exploration — use `cortex` CLI directly on the host; no container needed.

If a command fails with "container down", `drone exec` will bring the container up and retry once.

## Current State

Single package: `packages/snowfort-audit/` — a Clean Architecture Python CLI (`snowfort audit`) that
connects to Snowflake, audits warehouse and resource configuration against WAF policy rules, and emits
violations structured by rule ID, severity, pillar, and remediation guidance.

Toolchain: Python ≥ 3.10, hatchling build, pytest + pytest-cov, ruff (lint), mypy (types),
pylint-clean-architecture (layer enforcement), import-linter (dependency contracts). All dev targets
are in `packages/snowfort-audit/Makefile`. The CLI entry point is `snowfort_audit.__main__:main`.

Cortex Code skills live in `packages/snowfort-audit/.cortex/skills/` and are auto-discovered when
the repo is the working directory.

## Learned

- NEVER run pytest, ruff, mypy, or any Python toolchain command directly on the host. Always use
  `drone exec snowfort -- <command>`. The host may not have the correct Python or venv, and
  pre-commit hooks are configured for the container environment.
