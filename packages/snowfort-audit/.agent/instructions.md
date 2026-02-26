# Snowfort-Audit Agent Instructions

## Project Overview

Snowfort-audit is a Clean Architecture WAF (Well-Architected Framework) auditor for Snowflake.
It scans Snowflake accounts for cost, performance, security, and governance issues.

## Architecture

This project follows **Clean Architecture** with strict layer boundaries:

```
src/snowfort_audit/
  domain/          # Business rules, entities, protocols. NO I/O, NO framework imports.
  use_cases/       # Application-specific orchestration. May import domain only.
  infrastructure/  # External systems (Snowflake, filesystem). Implements domain protocols.
  interface/       # CLI (click), TUI (textual), Streamlit. Entry points and presentation.
  di/              # Dependency injection container. Wires infrastructure to domain protocols.
```

### Layer Rules (enforced by pylint-clean-architecture)

| Layer          | May Import                    | Must NOT Import     |
|----------------|-------------------------------|---------------------|
| Domain         | stdlib only (typing, dataclasses, abc, enum, etc.) | Infrastructure, Interface, UseCase |
| UseCase        | Domain                        | Infrastructure, Interface |
| Infrastructure | Domain, UseCase               | Interface           |
| Interface      | Domain, UseCase               | Infrastructure (use DI) |

### Key Violations to Avoid

- **W9001**: Do not import across layer boundaries (e.g., domain importing infrastructure)
- **W9004**: Do not import I/O modules (requests, os, subprocess) in domain/use_case
- **W9013**: Do not call print(), open(), subprocess.run() in domain/use_case
- **W9301**: Do not instantiate Gateway/Repository/Client classes in domain/use_case -- inject via constructor
- **W9201**: Infrastructure classes must inherit from a domain Protocol
- **W9601**: Domain entities must use @dataclass(frozen=True), no attribute assignment outside __init__

## Workflow

### Before making changes

1. Read the file(s) you plan to modify
2. Understand which architectural layer they belong to
3. Check existing tests for the area

### After making changes

Always run `make check` to verify:
- Linting passes (ruff + pylint-clean-architecture rules)
- All tests pass
- Coverage stays >= 80%

If `make check` fails, fix the issues before considering the task complete.

### Adding a New Rule

1. Create the rule class in `src/snowfort_audit/domain/rules/` (inheriting from base Rule)
2. Register it in the appropriate pillar
3. Write tests in `tests/unit/`
4. Run `make check`

### Running Individual Steps

```bash
make lint           # Ruff + architecture check only
make test           # Tests only
make coverage       # Full coverage report
make coverage-check # Tests with 80% threshold enforcement
```

## Code Style

- Python 3.12+
- Line length: 120
- Uppercase SQL keywords (SELECT, FROM, WHERE)
- Explicit column lists, no SELECT *
- Type hints on all public functions
- Frozen dataclasses for domain entities
- Protocols (typing.Protocol) for abstractions, not ABC
