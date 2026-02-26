# Code Coverage and Priorities to Reach 80%+

**Current status: >80% coverage achieved.** Use `make coverage-check` in CI to enforce.

## How to measure coverage and priorities

Run from the project root (after `pip install -e ".[dev]"`):

```bash
# Current coverage (terminal + HTML)
make coverage

# Coverage + ML impact report (prioritized list for new tests)
make coverage-impact
```

`make coverage-impact` writes **`coverage_impact.json`** and prints a **Top Functions by Priority** table. Use that table to add tests for **high score + low coverage** functions first.

To enforce 80% once you’re there:

```bash
pytest tests/ --cov=src/snowfort_audit --cov-fail-under=80 -q
```

---

## High-impact areas (structure-based priorities)

If you don’t have `coverage_impact.json` yet, use this order to get above 80% quickly.

### 1. Use cases (high impact, often under-tested)

- **`use_cases/offline_scan.py`** – `execute()`, `_scan_sql_files()`, `_analyze_single_sql_file()` (error paths).
- **`use_cases/online_scan.py`** – run with mocked gateway/cursor; cover success and error branches.
- **`use_cases/bootstrap.py`** – bootstrap flow with mocked governance/gateway.

**How:** Integration-style tests that call the use case with faked `FileSystemProtocol`, `ManifestRepositoryProtocol`, and/or `SnowflakeGateway` (or cursor), and assert on returned violations and telemetry.

### 2. CLI paths (interface layer)

- **`interface/cli.py`** – All `audit` subcommands: `scan` (offline + online), `fix`, `rules`, `login`, `demo-setup`, `calculator-inputs`, `bootstrap`. Cover both success and failure/abort paths (e.g. missing connection, user abort).

**How:** `tests/unit/test_cli.py` – use `CliRunner().invoke(main, [...])` and mock container/gateway/connection so no real Snowflake or filesystem is needed. Add one test per subcommand and for `--help` and invalid args.

### 3. New WAF rules (many rules, one test file)

- **Phase 2/3 rules** in `domain/rules/` (e.g. SEC_009/010, GOV_004, COST_007/008/013/016, REL_004–008, PERF_002/005/010–012, STAT_004–006, COST_010/014/015) – ensure each has at least one unit test that calls `check_online()` or `check_static()` with a mocked cursor or string.

**How:** In `tests/unit/test_rules_impl.py` (and/or one test file per rule file), add tests that mock `cursor.fetchall()` / `cursor.fetchone()` / `cursor.description` and assert on `rule.check_online(cursor)` or `rule.check_static(content, path)`.

### 4. Infrastructure

- **`infrastructure/rule_registry.py`** – `get_all_rules()`, `discover_custom_rules()`, `_load_and_inspect_module()`.
- **`infrastructure/remediation_engine.py`** – `suggest_fix()` for a few rule IDs.
- **`infrastructure/calculator_interrogator.py`** – with mocked cursor returning known rows.
- **`infrastructure/repositories/manifest.py`** – `load_definitions()` for a temp directory with a `manifest.yml`.

**How:** Unit tests with mocks; for manifest repo, use a temporary directory and a sample `manifest.yml`.

### 5. Domain

- **`domain/guided.py`** – `group_violations_by_concept()` with a fixed list of violations (already has tests; ensure edge cases).
- **`domain/financials.py`** – pricing/credit logic with different configs.
- **`di/container.py`** – resolve a few keys (e.g. rules, use cases) and assert type/behavior.

---

## Suggested order to reach 80%

1. Run **`make coverage-impact`** and open **`coverage_impact.json`** (or the printed table).
2. Add tests for the **top 10–20 functions** that have low or N/A coverage and high impact score.
3. Add the **use case tests** (offline/online scan, bootstrap) so those paths are covered.
4. Add **CLI tests** for every subcommand (mocked I/O).
5. Add **one test per new rule** (mock cursor or static input).
6. Re-run **`make coverage-impact`** and repeat until overall coverage is above 80%, then add **`--cov-fail-under=80`** to CI or `make coverage`.

---

## One-shot: add tests for the highest-impact missing code

After running `make coverage-impact`, inspect the **Top Functions by Priority** table:

- **Score** = impact × complexity; higher = better candidate for a new test.
- **Coverage %** = current coverage for that function; **N/A** or low = not (well) covered.

Add unit or integration tests that execute those functions (with mocks where needed), then re-run `make coverage-impact` until the overall coverage line shows **≥ 80%**.

---

## Prioritized list from `make coverage-impact` (latest run)

Use this order when adding tests to reach **>80% coverage**. Focus on **high priority + low coverage %** first.

| Priority | Score | Coverage % | File / area | Function / focus |
|----------|-------|------------|-------------|-------------------|
| 1 | 37.42 | 84.8% | _vendor/telemetry.py | RichTelemetry (error/debug paths) |
| 2 | 16.99 | **55.0%** | domain/rules/reliability.py | SchemaEvolutionCheck.check_online |
| 3 | 12.92 | **61.5%** | infrastructure/gateways/sql_validator.py | SqlFluffValidatorGateway.validate |
| 4–6 | 9–11 | **65.9%** | domain/rules/cost.py | AggressiveAutoSuspendCheck, MultiClusterSafeguardCheck |
| 7–9 | 8–9 | 76% | _vendor/snowflake_gateway.py, domain/rules/static.py | SnowflakeGateway, SecretExposure, DynamicTableComplexity, HardcodedEnv, NakedDrop, AntiPattern, MergePattern, SelectStar |
| 18 | 4.01 | **49.5%** | **use_cases/online_scan.py** | **OnlineScanUseCase.execute** (parallel path, SHOW VIEWS loop) |
| 20 | 3.54 | **49.5%** | use_cases/online_scan.py | OnlineScanUseCase._execute_parallel |
| 23 | 2.57 | **50.0%** | infrastructure/repositories/governance.py | SnowparkAuditRepository (get_latest_audit_result) |

**Highest leverage (low coverage + high impact):**

1. **use_cases/online_scan.py** (49% → target 70%+) – Add tests for: `_execute_parallel` (multi-worker), per-view rule loop, and error branches (cursor raises, SHOW VIEWS raises).
2. **domain/rules/reliability.py** (55%) – Add tests for: ReplicationLagMonitoringCheck, FailedTaskDetectionCheck, PipelineObjectReplicationCheck (mock cursor with fetchall).
3. **infrastructure/gateways/sql_validator.py** (62%) – Add tests for: `validate()` with invalid SQL and exception path; `SqlfluffSQLViolation.matches()` edge cases.
4. **infrastructure/repositories/governance.py** (50%) – Add tests for: GovernanceRepository.get_budget_alerts with mocked session.
5. **domain/rules/op_excellence.py** (69%) – Add tests for: EventTableConfigurationCheck (OPS_010), DataMetricFunctionsCoverageCheck (OPS_011), AlertExecutionReliabilityCheck (OPS_012).
6. **domain/rules/perf.py** (70%) – Add tests for: QueryLatencySLOCheck (PERF_013) with mock cursor returning P99 rows.
7. **domain/rules/security.py** (72%) – Add tests for: SSOCoverageCheck (SEC_015) with mock cursor (SSO majority + non-SSO users).

After adding tests, run:

```bash
make coverage-impact
pytest tests/ --cov=src/snowfort_audit --cov-fail-under=80 -q
```
