# Contributing to Snowfort

Thanks for thinking about contributing. This doc tells you how to do it in a way that
respects everyone's time, including yours.

## How to file a bug or feature request

Open a [GitHub issue](https://github.com/noah-goodrich/snowfort/issues/new). A useful
issue includes:

- What you ran (the full `snowfort audit ...` command).
- What you expected to happen.
- What actually happened (paste the error, the stack trace, or the misbehaving output).
- Your Snowflake edition (Standard, Enterprise, Business Critical, VPS).
- Your Python version and OS.

If you saw a SQL error from a specific rule, include the rule ID. That's the fastest path
to a fix because issues get auto-labeled by pillar and rule.

## How to submit a pull request

1. Fork the repo and create a topic branch off `main` (`feat/your-thing`,
   `fix/your-thing`, `docs/your-thing`).
2. Make the change. Keep PRs small and focused. One concern per PR is better than three.
3. Run the full pre-merge gate before pushing:

   ```bash
   drone exec snowfort -- make check
   ```

   That runs ruff, mypy, the test suite, the import-linter contracts, and the coverage
   check. CI runs the same gate, so if it passes locally it'll pass in CI.
4. Open the PR with a clear title and a description that says what you changed and why.
5. Be patient. Response time SLO is in the README's Support section.

## Scope: what's in and what's out

Snowfort is opinionated by design. To keep it small and maintainable, here's what fits
and what doesn't:

**In scope.** Bug fixes. New WAF rules with a clear pillar fit (Security, Cost,
Performance, Reliability, Operations, Governance). Documentation that helps a stranger
get to a first scan faster. Tests, performance work, and dependency hygiene.

**Out of scope.** Plugins that pull in heavy new dependencies (consider the
[custom-rules entry-point hook](packages/snowfort-audit/README.md#custom-rules-extensibility)
instead). Rules that score subjective architecture taste rather than measurable
configuration. UI work outside the existing Streamlit dashboard. Re-platforming to a
different language or framework. Anything that requires a paid Snowflake feature most
users don't have.

If you're unsure whether your idea fits, open an issue first. Cheaper than writing the
PR and finding out it can't be merged.

## Code style

- Python: black formatting, type hints on public functions.
- SQL: uppercase keywords, lowercase identifiers, CTEs over subqueries.
- New rules go in `packages/snowfort-audit/src/snowfort_audit/domain/rules/` and must
  inherit from `Rule`. Register them in
  `packages/snowfort-audit/src/snowfort_audit/infrastructure/rule_registry.py`.
- New rules need at least three unit tests (happy path, edge case, error path).
- All output is reviewed by the `sensitive-outputs` hook before it ships. If your rule
  surfaces field values from a Snowflake table, look at that hook first.

The clean-architecture import contracts (`import-linter`) will block PRs that violate
the layering. If you hit a contract violation and don't know how to satisfy it, ask in
the PR; it's almost always a sign the new code wants to live in a different module.

## Response-time SLO

See the [Support section in the README](README.md#support). It's an honest commitment
from a solo maintainer with a day job: 7-day target for triage, no fixed-window
guarantee on fixes. Security-tagged issues jump the line.

## License

By contributing you agree your work will be released under Snowfort's
[MIT license](LICENSE).

## Code of conduct

Be useful, be kind, no harassment. If something's off, email
[goodrich.noah@gmail.com](mailto:goodrich.noah@gmail.com).
