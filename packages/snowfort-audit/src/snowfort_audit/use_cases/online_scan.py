import ast
import inspect
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol, SnowflakeQueryProtocol
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.scan_context import ScanContext

from ..domain.rule_definitions import (
    EXCLUDED_DATABASES_DEFAULT,
    Rule,
    Violation,
)

# (rule_id, rule_name, duration_seconds)
RuleTiming = tuple[str, str, float]


def _is_system_or_tool_violation(v: Violation, include_snowfort_db: bool) -> bool:
    """True if this violation's resource is in SNOWFLAKE/SNOWFORT or Snowflake-managed and should be hidden."""
    r = (v.resource_name or "").strip().upper()
    if r.startswith("SNOWFLAKE") or r.startswith("SNOWFLAKE_SAMPLE_DATA") or "'SNOWFLAKE" in r:
        return True
    if not include_snowfort_db and (r.startswith("SNOWFORT") or "'SNOWFORT" in r):
        return True
    if r.startswith("SYSTEM$") or "'SYSTEM$" in r:
        return True
    return False


def _check_online_uses_resource_name(rule: Rule) -> bool:
    """True if rule.check_online uses its third parameter (view/resource name) in the method body.
    Signature is (self, cursor, _resource_name). Used to decide which rules to run per-view vs once at account level.
    Inspects the class method so it still works when the instance method is replaced (e.g. by a test mock).
    """
    method = getattr(type(rule), "check_online", None)
    if method is None:
        return False
    try:
        source = inspect.getsource(method)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        # Source unavailable (e.g. dynamically defined class). Fall back to
        # signature check: if method is overridden and has 3+ params, assume
        # it uses the resource name.
        base_method = getattr(Rule, "check_online", None)
        if method is not base_method:
            sig = inspect.signature(method)
            return len(sig.parameters) >= 3
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = node.args.args
            if len(args) < 3:
                return False
            param_name = args[2].arg  # (self, cursor, _resource_name)
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and child.id == param_name:
                    return True
            return False
    return False


def _run_rules_chunk(
    gateway: Any,
    rules_chunk: list[tuple[int, Rule]],
    worker_id: int,
    profile: bool = False,
    scan_context: ScanContext | None = None,
) -> tuple[list[Violation], list[RuleTiming]]:
    """Run a subset of rules on a dedicated connection. Used by parallel scan."""
    out: list[Violation] = []
    timings: list[RuleTiming] = []
    cursor = gateway.get_cursor_for_worker(worker_id)
    for _idx, rule in rules_chunk:
        t0 = time.perf_counter()
        try:
            found = rule.check_online(cursor, scan_context=scan_context)
            if found:
                out.extend(found)
        except Exception:
            # Rule normally catches and logs; if it raised, we continue (no telemetry in worker thread)
            pass
        if profile:
            timings.append((rule.id, rule.name, time.perf_counter() - t0))
    return out, timings


class OnlineScanUseCase:
    """Orchestrates the live online scan of Snowflake account.
    Supports parallel execution with workers > 1 (multiple Snowflake connections).
    """

    def __init__(self, gateway: SnowflakeQueryProtocol, rules: list[Rule], telemetry: TelemetryPort):
        self.gateway = gateway
        self.rules = rules
        self.telemetry = telemetry
        self.profile_timings: list[RuleTiming] = []

    def execute(
        self,
        workers: int = 1,
        include_snowfort_db: bool = False,
        profile: bool = False,
    ) -> list[Violation]:
        """Scans a live Snowflake account for WAF violations.
        workers: 1 = sequential; >1 = parallel (if gateway supports it).
        include_snowfort_db: if True, include SNOWFORT DB in view-phase (auditing Snowfort itself).
        profile: if True, collect per-rule timing in self.profile_timings.
        Establishes one connection first; with MFA, extra connections may fail (fall back to 1 worker).
        """
        total = len(self.rules)
        self.telemetry.step("Engaging Online Sensors: Scanning live Snowflake environment...")
        self.profile_timings = []

        # Establish one good connection first so we don't spam multiple MFA/connection attempts in parallel
        try:
            _ = self.gateway.get_cursor()
        except (RuntimeError, ValueError, Exception) as e:
            self.telemetry.error(f"Failed to obtain Snowflake cursor: {e}")
            raise

        use_parallel = workers > 1 and hasattr(self.gateway, "get_cursor_for_worker")
        if use_parallel:
            # Try one extra connection in main thread; with MFA/TOTP it often fails (one-time code)
            try:
                _ = self.gateway.get_cursor_for_worker(1)
            except Exception:
                self.telemetry.info(
                    "  Multiple connections need a new MFA code each; using 1 worker. (Use --workers 1 with MFA.)"
                )
                use_parallel = False
                workers = 1

        # Prefetch shared queries once; workers share the immutable ScanContext.
        scan_context = self._prefetch(self.gateway.get_cursor())

        if use_parallel:
            self.telemetry.info(f"  Running {total} rules in parallel with {workers} workers.")
            violations, timings = self._execute_parallel(workers, profile, scan_context)
        else:
            self.telemetry.info(f"  Running {total} rules (--workers N for parallel, --log-level DEBUG for detail).")
            violations, timings = self._execute_sequential(profile, scan_context)

        violations, view_timings = self._execute_view_phase(violations, include_snowfort_db, profile)
        self.profile_timings = timings + view_timings

        before = len(violations)
        violations = [v for v in violations if not _is_system_or_tool_violation(v, include_snowfort_db)]
        if before > len(violations):
            self.telemetry.debug(f"  Filtered {before - len(violations)} violation(s) from system/tool databases.")

        self.telemetry.info(f"  Completed: {len(violations)} total violation(s) from {total} rules.")
        return violations

    def _execute_view_phase(
        self,
        violations: list[Violation],
        include_snowfort_db: bool,
        profile: bool = False,
    ) -> tuple[list[Violation], list[RuleTiming]]:
        """Run per-view rules using batch DDL from ACCOUNT_USAGE.VIEWS.
        Falls back to per-view GET_DDL if ACCOUNT_USAGE.VIEWS is unavailable.
        Returns (violations, timings).
        """
        excluded_dbs = EXCLUDED_DATABASES_DEFAULT - {"SNOWFORT"} if include_snowfort_db else EXCLUDED_DATABASES_DEFAULT
        excluded_db_like = frozenset(
            (
                "ACCOUNT_USAGE",
                "BCR_ROLLOUT",
                "DATA_SHARING_USAGE",
                "INFORMATION_SCHEMA",
                "LOCAL",
                "MONITORING",
                "ORGANIZATION_USAGE",
                "READER_ACCOUNT_USAGE",
                "SNOWPARK_CONNECT",
                "TELEMETRY",
                "TRUST_CENTER",
            )
        )
        timings: list[RuleTiming] = []
        try:
            cur: SnowflakeCursorProtocol = self.gateway.get_cursor()
            rules_for_view = [r for r in self.rules if _check_online_uses_resource_name(r)]
            if not rules_for_view:
                self.telemetry.info("  No rules use view name; skipping per-view phase.")
                return violations, timings

            # Strategy 3: try batch DDL via ACCOUNT_USAGE.VIEWS (one query instead of N GET_DDL calls)
            ddl_map: dict[str, str] | None = self._fetch_batch_ddl(cur, excluded_dbs, excluded_db_like)

            if ddl_map is not None:
                violations, timings = self._run_view_phase_batch(cur, violations, rules_for_view, ddl_map, profile)
            else:
                violations, timings = self._run_view_phase_fallback(
                    cur, violations, rules_for_view, excluded_dbs, excluded_db_like, profile
                )

        except (RuntimeError, ValueError) as e:
            self.telemetry.error(f"Failed to fetch views for online scan: {e}")
        return violations, timings

    def _fetch_batch_ddl(
        self,
        cur: SnowflakeCursorProtocol,
        excluded_dbs: frozenset,
        excluded_db_like: frozenset,
    ) -> dict[str, str] | None:
        """Query ACCOUNT_USAGE.VIEWS to get all view DDLs at once.
        Returns {view_name: ddl} dict, or None if unavailable (triggers fallback).
        """
        try:
            cur.execute(
                "SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, VIEW_DEFINITION"
                " FROM SNOWFLAKE.ACCOUNT_USAGE.VIEWS"
                " WHERE DELETED IS NULL AND VIEW_DEFINITION IS NOT NULL"
            )
            rows = cur.fetchall()
            ddl_map: dict[str, str] = {}
            for row in rows:
                if len(row) < 4:
                    continue
                catalog = (row[0] or "").upper()
                if catalog in excluded_dbs or catalog in excluded_db_like:
                    continue
                view_name = f"{row[0]}.{row[1]}.{row[2]}"
                ddl_map[view_name] = row[3] or ""
            self.telemetry.debug(f"  Batch DDL: fetched DDL for {len(ddl_map)} views via ACCOUNT_USAGE.VIEWS.")
            return ddl_map
        except Exception as e:
            self.telemetry.debug(f"  ACCOUNT_USAGE.VIEWS unavailable, falling back to per-view GET_DDL: {e}")
            return None

    def _run_view_phase_batch(
        self,
        cur: SnowflakeCursorProtocol,
        violations: list[Violation],
        rules_for_view: list[Rule],
        ddl_map: dict[str, str],
        profile: bool,
    ) -> tuple[list[Violation], list[RuleTiming]]:
        """Run view-scoped rules against pre-fetched DDLs (batch path)."""
        timings: list[RuleTiming] = []
        n_views = len(ddl_map)
        n_per_view = len(rules_for_view)
        if n_views == 0:
            self.telemetry.info("  No user views to check (system DBs excluded).")
            return violations, timings
        self.telemetry.info(f"  Checking {n_views} views with {n_per_view} view-scoped rule(s) (batch DDL)...")
        rule_elapsed: dict[str, float] = {}
        for view_name, ddl in ddl_map.items():
            for rule in rules_for_view:
                t0 = time.perf_counter()
                try:
                    found = rule.check_static(ddl, view_name)
                    if found:
                        violations.extend(found)
                except Exception as e:
                    self.telemetry.error(f"Rule execution failed: {e}")
                    self.telemetry.debug(f"      -> {rule.id} on {view_name}")
                if profile:
                    rule_elapsed[rule.id] = rule_elapsed.get(rule.id, 0.0) + (time.perf_counter() - t0)
        if profile:
            rule_name_map = {r.id: r.name for r in rules_for_view}
            timings = [(rid, rule_name_map[rid], elapsed) for rid, elapsed in rule_elapsed.items()]
        return violations, timings

    def _run_view_phase_fallback(
        self,
        cur: SnowflakeCursorProtocol,
        violations: list[Violation],
        rules_for_view: list[Rule],
        excluded_dbs: frozenset,
        excluded_db_like: frozenset,
        profile: bool,
    ) -> tuple[list[Violation], list[RuleTiming]]:
        """Run view-scoped rules via SHOW VIEWS + per-view GET_DDL (fallback path)."""
        timings: list[RuleTiming] = []
        cur.execute("SHOW VIEWS IN ACCOUNT")
        all_rows = cur.fetchall()
        DB_NAME_IDX, SCHEMA_NAME_IDX, VIEW_NAME_IDX = 4, 5, 1
        views = [
            r
            for r in all_rows
            if len(r) > max(DB_NAME_IDX, SCHEMA_NAME_IDX, VIEW_NAME_IDX)
            and (r[DB_NAME_IDX] or "").upper() not in excluded_dbs
            and (r[DB_NAME_IDX] or "").upper() not in excluded_db_like
        ]
        n_views = len(views)
        n_per_view = len(rules_for_view)
        if n_views == 0:
            self.telemetry.info("  No user views to check (SNOWFLAKE/SNOWFORT and system DBs excluded).")
            return violations, timings
        n_checks = n_views * n_per_view
        self.telemetry.info(f"  Checking {n_views} views with {n_per_view} view-scoped rule(s) (~{n_checks} checks)...")
        view_progress_interval = max(1, min(10, n_views // 10))
        rule_elapsed: dict[str, float] = {}
        for v_idx, view in enumerate(views):
            view_name = f"{view[DB_NAME_IDX]}.{view[SCHEMA_NAME_IDX]}.{view[VIEW_NAME_IDX]}"
            self.telemetry.debug(f"    View [{v_idx + 1}/{n_views}] {view_name}")
            if (v_idx + 1) % view_progress_interval == 0 or (v_idx + 1) == n_views:
                self.telemetry.info(f"  Checked {v_idx + 1}/{n_views} views...")
            for rule in rules_for_view:
                t0 = time.perf_counter()
                try:
                    found = rule.check_online(cur, view_name)
                    if found:
                        violations.extend(found)
                except Exception as e:
                    self.telemetry.error(f"Rule execution failed: {e}")
                    self.telemetry.debug(f"      -> {rule.id} on {view_name}")
                if profile:
                    rule_elapsed[rule.id] = rule_elapsed.get(rule.id, 0.0) + (time.perf_counter() - t0)
        if profile:
            rule_name_map = {r.id: r.name for r in rules_for_view}
            timings = [(rid, rule_name_map[rid], elapsed) for rid, elapsed in rule_elapsed.items()]
        return violations, timings

    def _prefetch(self, cursor: SnowflakeCursorProtocol) -> ScanContext:
        """Run shared queries once and return an immutable ScanContext for all rules."""
        ctx = ScanContext()

        def _show(label: str, sql: str, attr_rows: str, attr_cols: str) -> None:
            try:
                self.telemetry.debug(f"  [ScanContext] Prefetching {label}...")
                cursor.execute(sql)
                rows = tuple(cursor.fetchall())
                cols = {col[0].lower(): i for i, col in enumerate(cursor.description or [])}
                object.__setattr__(ctx, attr_rows, rows)
                object.__setattr__(ctx, attr_cols, cols)
            except Exception as e:
                self.telemetry.debug(f"  [ScanContext] {label} unavailable: {e}")

        def _query(label: str, sql: str, attr: str) -> None:
            try:
                self.telemetry.debug(f"  [ScanContext] Prefetching {label}...")
                cursor.execute(sql)
                object.__setattr__(ctx, attr, tuple(cursor.fetchall()))
            except Exception as e:
                self.telemetry.debug(f"  [ScanContext] {label} unavailable: {e}")

        _show("SHOW WAREHOUSES", "SHOW WAREHOUSES", "warehouses", "warehouses_cols")
        _show("SHOW USERS", "SHOW USERS", "users", "users_cols")
        _show("SHOW DATABASES", "SHOW DATABASES", "databases", "databases_cols")
        _show("SHOW ROLES", "SHOW ROLES", "roles", "roles_cols")
        _query(
            "TAG_REFERENCES",
            "SELECT DOMAIN, OBJECT_NAME, TAG_NAME, TAG_VALUE, COLUMN_NAME"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES"
            " WHERE OBJECT_DELETED IS NULL",
            "tag_refs",
        )
        _query(
            "ACCOUNT_USAGE.TABLES",
            "SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE,"
            " BYTES, ROW_COUNT, RETENTION_TIME, ENABLE_SCHEMA_EVOLUTION,"
            " CLUSTERING_KEY, COMMENT"
            " FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES"
            " WHERE DELETED IS NULL",
            "tables",
        )
        return ctx

    def _execute_sequential(
        self, profile: bool = False, scan_context: ScanContext | None = None
    ) -> tuple[list[Violation], list[RuleTiming]]:
        cur: SnowflakeCursorProtocol = self.gateway.get_cursor()
        violations: list[Violation] = []
        timings: list[RuleTiming] = []
        total = len(self.rules)
        for i, rule in enumerate(self.rules):
            self.telemetry.info(f"  [{i + 1}/{total}] {rule.id}: {rule.name}")
            t0 = time.perf_counter()
            try:
                found = rule.check_online(cur, scan_context=scan_context)
                if found:
                    violations.extend(found)
                    self.telemetry.debug(f"      -> {len(found)} violation(s)")
            except Exception as e:
                self.telemetry.error(f"Rule execution failed: {e}")
                self.telemetry.debug(f"      -> exception in {rule.id}")
            if profile:
                timings.append((rule.id, rule.name, time.perf_counter() - t0))
        return violations, timings

    def _execute_parallel(
        self, workers: int, profile: bool = False, scan_context: ScanContext | None = None
    ) -> tuple[list[Violation], list[RuleTiming]]:
        total = len(self.rules)
        # Partition rules: worker i gets indices i, i+workers, i+2*workers, ...
        chunks: list[list[tuple[int, Rule]]] = [[] for _ in range(workers)]
        for i, rule in enumerate(self.rules):
            chunks[i % workers].append((i, rule))

        violations: list[Violation] = []
        timings: list[RuleTiming] = []
        n_done = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_rules_chunk, self.gateway, chunks[w], w, profile, scan_context): w
                for w in range(workers)
                if chunks[w]
            }
            for fut in as_completed(futures):
                worker_id = futures[fut]
                try:
                    out, chunk_timings = fut.result()
                    violations.extend(out)
                    timings.extend(chunk_timings)
                except Exception as e:
                    self.telemetry.error(f"Rule execution failed: {e}")
                n_done += len(chunks[worker_id])
                self.telemetry.info(f"  Worker {worker_id + 1}/{workers}: {n_done}/{total} rules done.")
        return violations, timings
