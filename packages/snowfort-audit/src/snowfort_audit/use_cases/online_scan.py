import ast
import inspect
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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


_resource_name_cache: dict[type, bool] = {}


def _is_zombie_user(user: Any, cols: dict[str, int], now: datetime) -> bool:
    """Return True if user looks like a zombie (inactive >90d or never-logged-in >30d)."""
    idx_login = cols.get("last_success_login")
    idx_created = cols.get("created_on")
    if idx_login is None:
        return False
    last_login = user[idx_login]
    if last_login is None:
        if idx_created is None:
            return False
        created = user[idx_created]
        if created is None or not hasattr(created, "tzinfo"):
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).days > 30
    if not hasattr(last_login, "tzinfo"):
        return False
    if last_login.tzinfo is None:
        last_login = last_login.replace(tzinfo=timezone.utc)
    return (now - last_login).days > 90


def _derive_sso_and_zombies(
    users: tuple[Any, ...],
    cols: dict[str, int],
) -> tuple[bool, set[str]]:
    """Compute sso_enforced flag and zombie login set from prefetched SHOW USERS rows.

    sso_enforced is True when ≥50% of non-SERVICE users have ext_authn_uid set.
    zombie_logins contains lowercase usernames inactive >90 days or never-logged-in >30 days.
    """
    idx_uid = cols.get("ext_authn_uid")
    idx_type = cols.get("type")
    idx_name = cols.get("name")
    human_total = 0
    sso_count = 0
    zombie_logins: set[str] = set()
    now = datetime.now(timezone.utc)
    for user in users:
        user_type = str(user[idx_type] if idx_type is not None else "").upper()
        if user_type == "SERVICE":
            continue
        human_total += 1
        if idx_uid is not None and user[idx_uid]:
            sso_count += 1
        if idx_name is not None and _is_zombie_user(user, cols, now):
            zombie_logins.add(str(user[idx_name]).lower())
    sso_enforced = (sso_count / human_total >= 0.5) if human_total > 0 else False
    return sso_enforced, zombie_logins


def _class_uses_resource_name(cls: type) -> bool:
    """Cached per-class: True if cls.check_online uses its third parameter."""
    cached = _resource_name_cache.get(cls)
    if cached is not None:
        return cached
    result = _inspect_uses_resource_name(cls)
    _resource_name_cache[cls] = result
    return result


def _inspect_uses_resource_name(cls: type) -> bool:
    """AST inspection: does cls.check_online reference its third positional parameter?"""
    method = getattr(cls, "check_online", None)
    if method is None:
        return False
    try:
        source = inspect.getsource(method)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
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
            param_name = args[2].arg
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and child.id == param_name:
                    return True
            return False
    return False


def _check_online_uses_resource_name(rule: Rule) -> bool:
    """Thin wrapper: delegates to the lru_cache'd _class_uses_resource_name."""
    return _class_uses_resource_name(type(rule))


def _check_views_chunk(
    views_chunk: list[tuple[str, str]],
    rules_for_view: list[Rule],
) -> list[Violation]:
    """Run view-scoped rules against a chunk of (view_name, ddl) pairs. Pure Python, no cursor."""
    out: list[Violation] = []
    for view_name, ddl in views_chunk:
        for rule in rules_for_view:
            try:
                found = rule.check_static(ddl, view_name)
                if found:
                    out.extend(found)
            except Exception:
                pass
    return out


# (rule_id, error_message)
RuleError = tuple[str, str]


def _run_rules_chunk(
    gateway: Any,
    rules_chunk: list[tuple[int, Rule]],
    worker_id: int,
    profile: bool = False,
    scan_context: ScanContext | None = None,
) -> tuple[list[Violation], list[RuleTiming], list[RuleError]]:
    """Run a subset of rules on a dedicated connection. Used by parallel scan."""
    out: list[Violation] = []
    timings: list[RuleTiming] = []
    errors: list[RuleError] = []
    cursor = gateway.get_cursor_for_worker(worker_id)
    for _idx, rule in rules_chunk:
        t0 = time.perf_counter()
        try:
            found = rule.check_online(cursor, scan_context=scan_context)
            if found:
                out.extend(found)
        except Exception as e:
            errors.append((rule.id, str(e)))
        if profile:
            timings.append((rule.id, rule.name, time.perf_counter() - t0))
    return out, timings, errors


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
            # Try one extra connection; interactive auth (browser/TOTP) typically allows only one at a time.
            try:
                _ = self.gateway.get_cursor_for_worker(1)
            except Exception:
                self.telemetry.warning(
                    "Interactive authentication detected — parallel workers require separate connections. "
                    "Falling back to 1 worker. "
                    "For parallel scans, use keypair auth: run 'snowfort audit bootstrap --keypair'."
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

        violations, view_timings = self._execute_view_phase(violations, include_snowfort_db, profile, workers)
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
        workers: int = 1,
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
                violations, timings = self._run_view_phase_batch(
                    cur, violations, rules_for_view, ddl_map, profile, workers
                )
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
            # A2: fetch active databases first to skip views from dropped databases.
            cur.execute("SELECT DATABASE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE DELETED IS NULL")
            active_dbs_upper: frozenset[str] = frozenset(str(r[0]).upper() for r in cur.fetchall())

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
                if catalog not in active_dbs_upper:
                    continue  # A2: skip views from dropped databases
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
        workers: int = 1,
    ) -> tuple[list[Violation], list[RuleTiming]]:
        """Run view-scoped rules against pre-fetched DDLs (batch path).
        When workers > 1, partitions views across threads (check_static is pure Python, no cursor).
        """
        timings: list[RuleTiming] = []
        n_views = len(ddl_map)
        n_per_view = len(rules_for_view)
        if n_views == 0:
            self.telemetry.info("  No user views to check (system DBs excluded).")
            return violations, timings

        views_list = list(ddl_map.items())

        if workers > 1 and n_views > 1:
            self.telemetry.info(
                f"  Checking {n_views} views with {n_per_view} view-scoped rule(s) (batch DDL, {workers} workers)..."
            )
            t0_all = time.perf_counter()
            chunk_size = max(1, n_views // workers)
            chunks = [views_list[i : i + chunk_size] for i in range(0, n_views, chunk_size)]
            with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as pool:
                futures = [pool.submit(_check_views_chunk, chunk, rules_for_view) for chunk in chunks]
                for fut in as_completed(futures):
                    violations.extend(fut.result())
            if profile:
                timings.append(("VIEW_PHASE", "Batch DDL (parallel)", time.perf_counter() - t0_all))
        else:
            self.telemetry.info(f"  Checking {n_views} views with {n_per_view} view-scoped rule(s) (batch DDL)...")
            rule_elapsed: dict[str, float] = {}
            for view_name, ddl in views_list:
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
        # A2: fetch active databases to exclude views from dropped databases.
        try:
            cur.execute("SELECT DATABASE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE DELETED IS NULL")
            active_dbs_upper: frozenset[str] = frozenset(str(r[0]).upper() for r in cur.fetchall())
        except Exception:
            active_dbs_upper = frozenset()
        cur.execute("SHOW VIEWS IN ACCOUNT")
        all_rows = cur.fetchall()
        DB_NAME_IDX, SCHEMA_NAME_IDX, VIEW_NAME_IDX = 4, 5, 1
        views = [
            r
            for r in all_rows
            if len(r) > max(DB_NAME_IDX, SCHEMA_NAME_IDX, VIEW_NAME_IDX)
            and (r[DB_NAME_IDX] or "").upper() not in excluded_dbs
            and (r[DB_NAME_IDX] or "").upper() not in excluded_db_like
            and (not active_dbs_upper or (r[DB_NAME_IDX] or "").upper() in active_dbs_upper)
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

        # Build tag_refs_index for O(1) lookup by (DOMAIN, OBJECT_NAME).
        if ctx.tag_refs is not None:
            idx: dict[tuple[str, str], dict[str, str]] = {}
            for row in ctx.tag_refs:
                domain = str(row[0]).upper()
                obj = str(row[1]).upper()
                tag = str(row[2]).upper()
                val = str(row[3]) if row[3] is not None else ""
                key = (domain, obj)
                tags = idx.get(key)
                if tags is None:
                    tags = {}
                    idx[key] = tags
                tags[tag] = val
            object.__setattr__(ctx, "tag_refs_index", idx)
            self.telemetry.debug(f"  [ScanContext] Built tag_refs_index with {len(idx)} entries.")

        # Derive sso_enforced and zombie_user_logins from the prefetched user list.
        if ctx.users is not None and ctx.users_cols:
            sso_enforced, zombie_logins = _derive_sso_and_zombies(ctx.users, ctx.users_cols)
            object.__setattr__(ctx, "sso_enforced", sso_enforced)
            object.__setattr__(ctx, "zombie_user_logins", frozenset(zombie_logins))
            self.telemetry.debug(
                f"  [ScanContext] SSO detection: sso_enforced={sso_enforced}. Zombie logins: {len(zombie_logins)}."
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
                    out, chunk_timings, chunk_errors = fut.result()
                    violations.extend(out)
                    timings.extend(chunk_timings)
                    for rule_id, err_msg in chunk_errors:
                        self.telemetry.error(f"  Worker {worker_id}: {rule_id} failed: {err_msg}")
                except Exception as e:
                    self.telemetry.error(f"Rule execution failed: {e}")
                n_done += len(chunks[worker_id])
                self.telemetry.info(f"  Worker {worker_id + 1}/{workers}: {n_done}/{total} rules done.")
        return violations, timings
