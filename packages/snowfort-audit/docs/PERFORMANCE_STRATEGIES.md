# Performance Engineering: Sub-60-Minute Scan Target

*Date: 2026-04-08 | Status: Draft for review*

## Current State

A single-worker scan against a production Snowflake instance takes **multiple hours**.
The scan executes 83 rules, each running 1-5 SQL queries independently. With
`--workers 4-8`, account-level rules parallelize, but several structural bottlenecks
remain.

### Bottleneck Inventory

| Bottleneck | Rules Affected | Impact | Root Cause |
|:---|:---|:---|:---|
| N+1 SHOW PARAMETERS per warehouse | COST_009 | O(N) where N=warehouses | Loop: `SHOW PARAMETERS IN WAREHOUSE {name}` |
| N+1 CLUSTERING_DEPTH per table | PERF_001 | O(N) where N=large tables | Loop: `SYSTEM$CLUSTERING_DEPTH('{table}')` |
| N+1 SHOW GRANTS per role | SEC_008 | O(N) where N=roles | Loop: `SHOW GRANTS OF/TO ROLE {name}` |
| Correlated subquery + FLATTEN | COST_007, COST_013 | Minutes each | `NOT EXISTS (... LATERAL FLATTEN(ACCESS_HISTORY))` |
| Sequential view-phase loop | SQL_001 | O(V) where V=views | `GET_DDL('VIEW', name)` per view, no parallelism |
| Redundant SHOW WAREHOUSES | 5+ rules | 5x same query | No shared result cache |
| Redundant SHOW USERS | 4+ rules | 4x same query | No shared result cache |
| Redundant TAG_REFERENCES query | 3+ rules | 3x same query | No shared result cache |
| Heavy QUERY_HISTORY aggregations | PERF_003/004/013, OPS_005 | 10-60s each | 7-day window, PERCENTILE_CONT |

---

## Strategy 1: Shared Query Cache (Prefetch Layer)

**Concept:** Many rules query the same underlying views. Instead of each rule running
its own `SHOW WAREHOUSES` or `SELECT ... FROM ACCOUNT_USAGE.TABLES`, run each shared
query ONCE at scan start and inject results into rules.

### What to Cache

| Query | Rules Using It | Calls Saved |
|:---|:---|:---|
| `SHOW WAREHOUSES` | COST_001, COST_002, COST_009, OPS_002, OPS_001, PERF_012 | 5+ |
| `SHOW USERS` | SEC_002, SEC_006, SEC_007, SEC_011, SEC_015 | 4+ |
| `SHOW ROLES` | SEC_008 | 1 (but expensive with N+1) |
| `SHOW DATABASES` | REL_001, OPS_004, OPS_001, OPS_008, OPS_009 | 4+ |
| `TAG_REFERENCES` | COST_001, OPS_001, OPS_009, SEC_009, SEC_010 | 4+ |
| `ACCOUNT_USAGE.TABLES` | PERF_001, REL_002, REL_003, COST_007, COST_008 | 4+ |
| `QUERY_HISTORY (7d)` | PERF_002-004, PERF_013, OPS_005, COST_011 | 5+ |

### Implementation

```
ScanContext:
  warehouses: list[Row]      # SHOW WAREHOUSES (once)
  users: list[Row]           # SHOW USERS (once)
  databases: list[Row]       # SHOW DATABASES (once)
  roles: list[Row]           # SHOW ROLES (once)
  tables: list[Row]          # ACCOUNT_USAGE.TABLES (once)
  tag_refs: list[Row]        # TAG_REFERENCES (once)
  query_history_7d: list[Row]  # QUERY_HISTORY 7-day (once, heavy)
```

Each rule receives `ScanContext` via constructor or method arg. Rules that need
the data pull from the cache. Rules that need rule-specific queries still run
their own.

### Expected Impact

- **Eliminates ~20-30 redundant SQL calls** across the scan
- **SHOW WAREHOUSES** alone runs 5+ times currently
- **QUERY_HISTORY prefetch** is the biggest win: one 30-60s query replaces 5+
  separate 10-30s queries, each scanning the same 7-day window
- **Estimated time savings: 2-5 minutes** depending on account size

### Risks

- QUERY_HISTORY prefetch pulls a large result set into memory. May need
  column subsetting or warehouse-level partitioning.
- Cache invalidation: not an issue for a single scan (data is point-in-time).

### Peer Review

**Snowflake Architect:** *"This is the single most impactful change. ACCOUNT_USAGE
views have a 45-minute latency SLA and are backed by internal metadata tables.
Querying them once vs five times is a 5x reduction in metadata scan cost. The
QUERY_HISTORY prefetch is critical — that view is the most expensive to query
because it stores every executed statement. One aggregation pass over 7 days
beats five. Watch for the 10K-row default result limit on SHOW commands — use
`SHOW WAREHOUSES IN ACCOUNT` with LIMIT if needed."*

**Python Architect:** *"Implement as a frozen dataclass passed to `check_online()`.
Don't use a mutable global cache — that breaks thread safety for parallel workers.
Each worker gets its own reference to the same immutable prefetch data. Consider
`__slots__` for memory efficiency on large result sets."*

---

## Strategy 2: Eliminate N+1 Query Patterns

**Concept:** Three rules have O(N) query loops that dominate scan time in large
accounts.

### COST_009: Per-Warehouse Statement Timeout

**Current:** `SHOW WAREHOUSES` + `SHOW PARAMETERS IN WAREHOUSE {name}` × N
**Fix:** Query `SNOWFLAKE.ACCOUNT_USAGE.PARAMETERS` directly (if accessible) or
batch: run a single query that joins warehouse metadata with parameter settings.

```sql
-- Replace N+1 with single query
SELECT w."name" AS warehouse_name,
       p."value" AS timeout_value
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) w  -- after SHOW WAREHOUSES
LEFT JOIN (
    SELECT OBJECT_NAME, PARAMETER_VALUE
    FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_PARAMETERS
    WHERE PARAMETER_NAME = 'STATEMENT_TIMEOUT_IN_SECONDS'
      AND OBJECT_TYPE = 'WAREHOUSE'
) p ON w."name" = p.OBJECT_NAME
```

If OBJECT_PARAMETERS is not available, an alternative: use a Snowpark stored
procedure that loops server-side (no round-trip per warehouse).

### PERF_001: Cluster Key Validation

**Current:** `SELECT ... FROM TABLES WHERE BYTES > 1TB` + `SYSTEM$CLUSTERING_DEPTH()`
per table.
**Fix:** SYSTEM$CLUSTERING_DEPTH must be called per-table (no batch function). But:
1. Limit to top 20 tables by size (not all >1TB tables)
2. Parallelize the calls across workers
3. Use `SYSTEM$CLUSTERING_INFORMATION()` instead — returns depth + overlap in one call

### SEC_008: Zombie Roles

**Current:** `SHOW ROLES` + (`SHOW GRANTS OF ROLE {name}` + `SHOW GRANTS TO ROLE
{name}`) × N roles.
**Fix:** Replace with ACCOUNT_USAGE views:

```sql
-- All role grants in one query (replaces N × SHOW GRANTS OF ROLE)
SELECT GRANTEE_NAME, ROLE, PRIVILEGE, GRANTED_ON
FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
WHERE DELETED_ON IS NULL
```

This returns ALL grants across ALL roles in a single query. Parse in Python
instead of running N SHOW commands.

### Expected Impact

- **COST_009:** From O(N) to O(1). 50 warehouses: 50 queries → 1 query.
  Saves 1-3 minutes.
- **PERF_001:** From O(N) to O(20). Cap at 20 tables. Saves 30s-2min.
- **SEC_008:** From O(N) to O(1). 200 roles: 400 queries → 1 query.
  Saves 2-5 minutes.
- **Combined: 3-10 minutes saved.**

### Peer Review

**Snowflake Architect:** *"GRANTS_TO_ROLES in ACCOUNT_USAGE is the correct
replacement for SHOW GRANTS loops. It has up to 2-hour latency for newly created
grants, but for an audit tool checking drift, that's acceptable. For COST_009,
check if SHOW PARAMETERS IN ACCOUNT returns warehouse-level overrides — it may
not. The OBJECT_PARAMETERS approach requires Enterprise+ in some cases. Fall back
to the N+1 pattern with a concurrency limit (5 parallel SHOW PARAMETERS) if
the batch query isn't available."*

**Staff Snowpark Engineer:** *"For PERF_001, SYSTEM$CLUSTERING_DEPTH cannot be
batched in SQL. But you CAN batch it in Snowpark Python: submit all calls as
async tasks using `session.call('SYSTEM$CLUSTERING_DEPTH', table)` in a
ThreadPoolExecutor. Each call is <100ms; 20 calls in parallel completes in
<500ms vs 2-4 seconds sequentially."*

---

## Strategy 3: Parallelize the View-Phase Loop

**Concept:** The view-phase loop (SQL_001 checking every view via GET_DDL) is
completely sequential. For accounts with 1000+ views, this is the single largest
wall-clock bottleneck.

### Current Behavior

```
For each of V views:
    GET_DDL('VIEW', view_name)    # ~50-200ms per call
    Parse DDL for SELECT *
Total: V × 150ms average = 150 seconds for 1000 views
```

### Fix: Parallel View Scanning

1. **Partition views across workers** (same as account-level rules).
2. Each worker gets its own cursor and processes V/N views.
3. With 4 workers and 1000 views: 250 views per worker, ~37s total.

```python
# Sketch
with ThreadPoolExecutor(max_workers=workers) as executor:
    chunks = partition_views(views, workers)
    futures = {
        executor.submit(_scan_views_chunk, gateway, chunk, view_rules, i)
        for i, chunk in enumerate(chunks)
    }
    for f in as_completed(futures):
        violations.extend(f.result())
```

### Alternative: Batch GET_DDL

Instead of one GET_DDL per view, query `INFORMATION_SCHEMA.VIEWS` which
contains `VIEW_DEFINITION` for all views in a database:

```sql
SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, VIEW_DEFINITION
FROM SNOWFLAKE.ACCOUNT_USAGE.VIEWS
WHERE DELETED IS NULL
  AND VIEW_DEFINITION IS NOT NULL
```

This returns ALL view DDLs in ONE query. Parse in Python. Eliminates the
per-view loop entirely.

### Expected Impact

- **Parallel approach:** V/N speedup. 1000 views with 4 workers: 4x faster.
- **Batch DDL approach:** Entire view phase in ONE query (~5-15 seconds
  regardless of view count). This is the nuclear option.
- **Estimated savings: 2-15 minutes** depending on view count.

### Risks

- ACCOUNT_USAGE.VIEWS has up to 2-hour latency for new views.
- VIEW_DEFINITION may be truncated for very large view definitions.
- Some views may not be accessible if the role lacks privileges.

### Peer Review

**Snowflake Architect:** *"ACCOUNT_USAGE.VIEWS is the right approach. It stores
the DDL for every view in the account with no per-object query. The latency
is 120 minutes for newly created views, but existing views are always present.
VIEW_DEFINITION is NOT truncated — it stores the full DDL. This eliminates the
view loop entirely and is the highest-ROI change for accounts with many views."*

**Python Architect:** *"If you go with the parallel approach instead of batch,
ensure each worker's cursor is independently created — don't share cursors across
threads. The Snowflake connector is thread-safe per-connection but NOT per-cursor.
The batch approach is strictly better if ACCOUNT_USAGE.VIEWS is accessible."*

---

## Strategy 4: Query Optimization (SQL Rewrites)

**Concept:** Several rules use expensive SQL patterns that can be rewritten for
10-100x performance improvement.

### COST_007: Stale Table Detection

**Current:**
```sql
SELECT ... FROM TABLE_STORAGE_METRICS m
WHERE NOT EXISTS (
    SELECT 1 FROM ACCESS_HISTORY h,
    LATERAL FLATTEN(h.direct_objects_accessed) f
    WHERE f.value:objectName::string = m.TABLE_NAME
      AND h.QUERY_START_TIME > DATEADD('day', -90, CURRENT_TIMESTAMP())
)
```

**Rewrite:** Use a pre-aggregated CTE:
```sql
WITH accessed AS (
    SELECT DISTINCT f.value:objectName::string AS table_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY h,
    LATERAL FLATTEN(h.direct_objects_accessed) f
    WHERE h.QUERY_START_TIME > DATEADD('day', -90, CURRENT_TIMESTAMP())
)
SELECT m.TABLE_CATALOG, m.TABLE_SCHEMA, m.TABLE_NAME, m.ACTIVE_BYTES
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS m
LEFT JOIN accessed a ON m.TABLE_NAME = a.table_name
WHERE a.table_name IS NULL
  AND m.ACTIVE_BYTES > 1073741824
LIMIT 50
```

**Why faster:** The FLATTEN happens once in the CTE, not once per outer row.
Snowflake's optimizer handles LEFT JOIN + IS NULL more efficiently than
correlated NOT EXISTS with FLATTEN.

### COST_013: Unused Materialized View

Same pattern — correlated NOT EXISTS with FLATTEN. Same rewrite: CTE + LEFT JOIN.

### PERF_013: Query Latency SLO

**Current:** PERCENTILE_CONT over 7-day QUERY_HISTORY.
**Optimization:** Add `WAREHOUSE_NAME IS NOT NULL` filter and
`EXECUTION_STATUS = 'SUCCESS'` to exclude system queries and failures. This
can reduce the scan set by 30-50%.

### Heavy QUERY_HISTORY Rules (PERF_003/004, OPS_005, COST_011)

These all scan 7-day QUERY_HISTORY independently. With the prefetch cache
(Strategy 1), they share one scan. But the individual queries can also be
optimized:

- Add `QUERY_TYPE IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE')`
  to exclude DDL, SHOW, DESCRIBE which don't spill or queue.
- Add `EXECUTION_STATUS = 'SUCCESS'` to exclude cancelled/failed queries.
- Reduce time window from 7 days to 3 days for rules where recency matters
  more than coverage (PERF_003 spillage detection).

### Expected Impact

- **COST_007/013 rewrites:** From minutes to seconds. The CTE approach is
  typically 10-50x faster than correlated subquery with FLATTEN.
- **QUERY_HISTORY filters:** 30-50% scan reduction per query.
- **Combined: 3-10 minutes saved.**

### Peer Review

**Snowflake Architect:** *"The CTE + LEFT JOIN rewrite for ACCESS_HISTORY
FLATTEN is a known best practice. The Snowflake optimizer cannot push predicates
into LATERAL FLATTEN inside NOT EXISTS — it materializes the full FLATTEN for
every outer row. The CTE materializes once. This is the single biggest SQL-level
optimization you can make. For QUERY_HISTORY, always filter on QUERY_TYPE and
EXECUTION_STATUS — the view is partitioned on QUERY_START_TIME but not on type,
so filtering early reduces I/O."*

**Staff Snowpark Engineer:** *"If you're already prefetching QUERY_HISTORY into
Python (Strategy 1), consider doing the spillage/queuing/latency analysis in
pandas rather than SQL. Pull the raw data once with minimal columns
(WAREHOUSE_NAME, BYTES_SPILLED_TO_LOCAL, BYTES_SPILLED_TO_REMOTE,
QUEUED_PROVISIONING_TIME, TOTAL_ELAPSED_TIME, QUERY_TYPE) and compute
percentiles in numpy. This eliminates multiple heavy SQL aggregations."*

---

## Implementation Priority

| Strategy | Effort | Time Saved | Priority |
|:---|:---|:---|:---|
| 1. Shared Query Cache | Medium (1-2 sessions) | 2-5 min | **P1** |
| 2. Eliminate N+1 Patterns | Medium (1 session) | 3-10 min | **P1** |
| 3. Batch View DDL | Low (1 session) | 2-15 min | **P1** |
| 4. SQL Rewrites | Low-Medium (1 session) | 3-10 min | **P2** |

**Strategy 3 (batch view DDL)** is the highest ROI: one ACCOUNT_USAGE.VIEWS
query replaces the entire view-phase loop. Do it first.

**Strategies 1 + 2** together eliminate the majority of redundant and N+1
queries. Do them second.

**Strategy 4** is pure SQL optimization with no architecture changes. Can be
done incrementally, one rule at a time.

### Combined Target

| Scenario | Current (est.) | After All 4 Strategies |
|:---|:---|:---|
| 50 warehouses, 500 views, 7d history | ~45-90 min | ~8-15 min |
| 200 warehouses, 5000 views, 7d history | ~3-5 hours | ~20-40 min |
| 20 warehouses, 100 views, 7d history | ~15-30 min | ~3-5 min |

---

## Fifth Reviewer: DevOps/SRE (Operational Concerns)

*"Before optimizing SQL, measure. Add timing instrumentation to every rule
so you know WHERE the time goes. The --workers flag already exists but the
default is 1 — change the default to 4. Add a `--profile` flag that prints
per-rule execution time sorted by duration. You may find that 3-4 rules
account for 80% of scan time, and fixing just those rules gets you under
60 minutes without the architecture changes."*

**Recommended first step:** Add per-rule timing, run a production scan with
`--workers 4`, and identify the actual top-5 slowest rules before implementing
any of the above strategies.
