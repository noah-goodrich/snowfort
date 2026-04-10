# Project Plan: snowfort-audit v1.0.0
*Established: 2026-04-10*

## Objective

Ship snowfort-audit v1.0.0 as a production-quality, publicly installable Snowflake WAF auditor by fixing the silent error swallowing that makes scan output untrustworthy, adding CI to protect quality for contributors, and publishing to PyPI.

## Acceptance Criteria

- [ ] **AC1: All rules use structured error handling**
  Every `except Exception` block in `domain/rules/` either raises `RuleExecutionError` or calls `is_allowlisted_sf_error()` before returning `[]`. Zero bare `except Exception: return []` or `except Exception: pass` remaining. The `cortex_cost.py` pattern is the reference implementation.
  - Verify: `grep -rn "except Exception" src/snowfort_audit/domain/rules/ | grep -v "RuleExecutionError\|is_allowlisted_sf_error" | wc -l` returns 0

- [ ] **AC2: Scan output surfaces errored rules**
  When rules error during execution, the scan summary displays the count of `ERRORED` rules alongside violations (e.g., "42 violations, 3 rules errored"). Users are never shown a clean bill of health when rules silently failed.
  - Verify: Run a scan with insufficient permissions and confirm errored count appears in output

- [ ] **AC3: CI test workflow exists and passes**
  A GitHub Actions workflow runs `pytest`, `ruff check`, and `mypy` on push/PR against Python 3.12. Pre-commit hooks are no longer the sole quality gate.
  - Verify: `.github/workflows/ci.yml` exists and a push to a branch triggers green CI

- [ ] **AC4: Package is published to PyPI**
  `pip install snowfort-audit` works. Version is 1.0.0. Development Status classifier is `5 - Production/Stable`.
  - Verify: `pip install snowfort-audit` from a clean venv succeeds

- [ ] **AC5: Tests updated and passing**
  Tests that previously asserted error-swallowing behavior (`returns empty on error`) are updated to assert `RuleExecutionError` is raised. Coverage remains >= 80%.
  - Verify: `pytest tests/ --cov --cov-fail-under=80` passes

- [ ] **AC6: Nothing breaks**
  Existing offline scan, online scan, TUI, guided report, YAML export, `--manifest` JSON, and `--cortex` summary all continue to work. No regressions in scan results.
  - Verify: `scripts/smoke_test.sh` passes; offline scan against `examples/` produces expected violations

## Scope Boundaries

- **NOT building:** Streamlit app improvements, Native App packaging, declarative rule registry refactor
- **NOT building:** `ScanContext` frozenness fix, `Rule.__init__` parameter reduction, shared test fixtures in conftest.py
- **NOT building:** New rules — 116 is the rule count for v1.0
- If done early: Ship, don't expand.

## Ship Definition

1. All criteria pass locally
2. PR opened with all changes
3. CI workflow passes on the PR
4. Merged to main
5. GitHub Release created tagged `v1.0.0`
6. PyPI publish workflow runs and package is live

## Timeline

Target: 2-3 implementation sessions
Estimated effort: The error handling migration (AC1 + AC5) is the bulk — 72 sites across 10 rule files, mechanical but needs test validation after each file. CI workflow (AC3) is ~30 lines of YAML. PyPI publish (AC4) is one GitHub Release.

## Risks

1. **Error handling migration is mechanical but large** — 72 sites across 10+ rule files. Risk of introducing regressions if the allowlist check pattern isn't applied consistently. Mitigation: do it file-by-file with tests passing after each file.
2. **Some rules may legitimately need to swallow certain Snowflake errors** beyond errno 2003 — e.g., ACCOUNT_USAGE views that require specific roles or Enterprise-only features. Risk of breaking scans on accounts with limited permissions. Mitigation: expand `_ALLOWLISTED_SF_ERRNOS` if specific errno patterns emerge during testing.
3. **PyPI name squatting** — `snowfort-audit` may already be taken on PyPI. Mitigation: check availability before starting implementation work.

---

## Implementation Context (from Collective Review)

### The Problem

72 of 75 `except Exception` blocks across `domain/rules/` silently return `[]` on failure. Only `cortex_cost.py` (3 sites) uses the proper `RuleExecutionError` + `is_allowlisted_sf_error()` pattern defined in `rule_definitions.py:96-133`. This means a permission error, network timeout, or Snowflake schema change causes rules to report "no violations" — a false clean bill of health. An audit tool that silently hides its own failures is worse than no audit tool.

### The Reference Pattern (cortex_cost.py)

```python
try:
    cursor.execute(sql)
except Exception as exc:
    if is_allowlisted_sf_error(exc):
        return []
    raise RuleExecutionError(self.id, str(exc), cause=exc) from exc
```

### Files Requiring Error Handling Migration

| File | `except Exception` count | Notes |
|------|--------------------------|-------|
| `security.py` | 18 | All use `as e:` but return `[]` |
| `cost.py` | 16 | 7 bare `except Exception:` (no `as e:`) |
| `op_excellence.py` | 13 | 3 bare, 10 with `as e:` |
| `reliability.py` | 11 | 4 bare, 7 with `as e:` |
| `governance.py` | 8 | 2 bare, 6 with `as e:` |
| `workload.py` | 2 | Both with `as e:` |
| `perf.py` | 1 | With `as e:` |
| `cost_extensions.py` | 1 | With `as e:` |
| `perf_extensions.py` | 1 | With `as e:` |
| `strategy.py` | 1 | With `as e:` |
| `ops.py` | 1 | With `as e:` |

### CI Workflow Needed

Currently only `.github/workflows/publish-snowfort-audit.yml` exists (build + publish on release). Need a new `.github/workflows/ci.yml` that runs `pytest`, `ruff check`, and `mypy` on push/PR.

### Key Reference Files

- `src/snowfort_audit/domain/rule_definitions.py` — `RuleExecutionError`, `is_allowlisted_sf_error()`, `_ALLOWLISTED_SF_ERRNOS`
- `src/snowfort_audit/domain/rules/cortex_cost.py` — Reference pattern for proper error handling
- `src/snowfort_audit/use_cases/online_scan.py` — `OnlineScanUseCase` already catches `RuleExecutionError` and records `FindingStatus.ERRORED`
- `src/snowfort_audit/interface/cli/report.py` — Scan output rendering (needs to surface ERRORED count)
- `.github/workflows/publish-snowfort-audit.yml` — Existing workflow to reference for CI

*Plan locked. Do not modify acceptance criteria without explicit "I'm changing scope."*
