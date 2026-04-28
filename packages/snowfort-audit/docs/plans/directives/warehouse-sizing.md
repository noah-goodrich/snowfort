# Directive B: Warehouse Sizing & Cost Optimization

**Depends on:** Project A (Foundation) — requires `FindingCategory`, adjusted scoring,
enriched manifest, and reliable error handling.

**Priority:** Highest dollar impact. The single most valuable tool in the audit per
production experience. Warehouse spend is typically 60-80% of a Snowflake bill.

---

## Objective

Add warehouse utilization profiling, workload classification, consolidation analysis,
and storage cost optimization to snowfort-audit. Produce concrete dollar-denominated
savings projections grounded in actual `WAREHOUSE_METERING_HISTORY` credits and
Snowflake's published credit-per-size table — not vague percentage estimates.

## Scope

### Warehouse Utilization & Sizing

**New rules:**

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| PERF_020 | Three-Layer Utilization Profile | Compute P50 utilization across execution, queuing, and idle layers per warehouse using `WAREHOUSE_LOAD_HISTORY`. Flag underutilized (P50 exec < 10%) and overloaded (P50 queue > 20%). | MEDIUM |
| PERF_021 | Query Duration Anomaly | Flag warehouses where P95/P50 query duration ratio exceeds 10x — indicates mixed workloads or sizing mismatch. | LOW |
| PERF_022 | Workload Isolation | Detect warehouses serving both short interactive queries (<5s P50) and long batch queries (>60s P50) in the same 24h window. Recommend workload separation. | MEDIUM |
| COST_034 | Consolidation Candidates | Identify warehouse pairs with: complementary usage patterns (peak hours don't overlap), combined P50 utilization < 60%, and compatible workload types. Produce merge recommendation. | MEDIUM |
| COST_035 | Savings Projection | For each sizing/consolidation recommendation, compute annual credit savings using actual `WAREHOUSE_METERING_HISTORY` credits × credit-per-size delta. | INFORMATIONAL |
| PERF_023 | Auto-Suspend Optimization | Compute P75 inter-query gap per warehouse from `QUERY_HISTORY`. If P75 gap < current `auto_suspend`, recommend tighter setting. If P75 gap > 10× `auto_suspend`, flag as already aggressive. | LOW |
| COST_036 | Dormant Warehouse | Flag warehouses with zero queries in 30+ days that are not suspended. | HIGH |

**Workload classification engine:**

Classify each warehouse into one of: `INTERACTIVE`, `BATCH`, `ETL`, `MIXED`,
`DORMANT` based on query duration distribution, time-of-day patterns, and query
types from `QUERY_HISTORY`. Classification drives sizing recommendations:
- INTERACTIVE: optimize for concurrency (multi-cluster, smaller size)
- BATCH: optimize for throughput (single-cluster, larger size)
- ETL: optimize for scheduled windows (auto-suspend aggressive)
- MIXED: recommend splitting
- DORMANT: recommend removal

**Key ACCOUNT_USAGE views:**
- `WAREHOUSE_LOAD_HISTORY` (10-second granularity for utilization)
- `WAREHOUSE_METERING_HISTORY` (hourly credit consumption)
- `QUERY_HISTORY` (query duration, queue time, warehouse, user)

All warehouse queries route through `ScanContext.get_or_fetch()` for single-roundtrip
caching.

**Reference SQL (P50 utilization from memo section 14):**
```sql
WITH hourly AS (
    SELECT
        WAREHOUSE_NAME,
        DATE_TRUNC('HOUR', START_TIME) AS hr,
        AVG(AVG_RUNNING) AS avg_running,
        AVG(AVG_QUEUED_LOAD) AS avg_queued,
        MAX(AVG_RUNNING + AVG_QUEUED_LOAD + AVG_QUEUED_PROVISIONING + AVG_BLOCKED) AS peak_load
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
    WHERE START_TIME >= DATEADD('DAY', -30, CURRENT_TIMESTAMP())
    GROUP BY 1, 2
)
SELECT
    WAREHOUSE_NAME,
    APPROX_PERCENTILE(avg_running, 0.5) AS p50_running,
    APPROX_PERCENTILE(avg_queued, 0.5) AS p50_queued,
    APPROX_PERCENTILE(peak_load, 0.95) AS p95_peak
FROM hourly
GROUP BY 1;
```

### Storage Cost Optimization

**New rules:**

| Rule ID | Name | Description | Severity |
|---------|------|-------------|----------|
| COST_037 | Excessive Time Travel Retention | Flag tables >1TB with `DATA_RETENTION_TIME_IN_DAYS` > 7 where query frequency is < 1/day. High retention on rarely-queried large tables wastes storage. | MEDIUM |
| COST_038 | Clone Sprawl | Detect databases/schemas with >5 active clones or clones older than 90 days. Stale clones accumulate storage delta as source diverges. | LOW |
| COST_039 | Cold Storage / Iceberg Migration Candidates | Flag tables >100GB with <1 query/week and no clustering key. These are candidates for Iceberg table conversion (automatic tiered storage) or archival. | MEDIUM |
| COST_040 | Stale Table Storage Impact | Enhance existing COST_016 (stale table detection) with storage byte quantification. Rank by storage × staleness to prioritize cleanup. | LOW |

**Design constraint:** Use `TABLE_STORAGE_METRICS` and `QUERY_HISTORY` for storage
analysis. Do not require external metadata or manual tagging. Pattern detection via
configurable conventions, not hard-coded object name lists.

### Conventions

New convention block in `pyproject.toml`:
```toml
[tool.snowfort.thresholds.warehouse_sizing]
utilization_underused_p50 = 0.10      # P50 exec < 10% = underutilized
utilization_overloaded_p50_queue = 0.20  # P50 queue > 20% = overloaded
workload_split_short_p50_seconds = 5
workload_split_long_p50_seconds = 60
dormant_days = 30
lookback_days = 30

[tool.snowfort.thresholds.storage]
cold_table_min_bytes = 107374182400   # 100 GB
cold_table_max_queries_per_week = 1
clone_stale_days = 90
clone_max_per_schema = 5
excessive_retention_min_bytes = 1099511627776  # 1 TB
excessive_retention_min_days = 7
```

## Key Design Decisions

1. **Credits, not percentages.** Savings projections use actual metering credits
   and Snowflake's published credit-per-size table (XS=1, S=2, M=4, L=8, XL=16,
   2XL=32, 3XL=64, 4XL=128, 5XL=256, 6XL=512). No estimation.

2. **P50 over averages.** Averages hide bimodal distributions. P50 (median) reflects
   typical behavior; P95 captures peak. Both reported.

3. **No hard-coded warehouse names.** All detection is pattern-based using utilization
   metrics, query profiles, and configurable thresholds.

4. **Workload classification is a building block.** The classification engine produces
   structured metadata consumed by sizing rules, consolidation analysis, and the
   Cortex synthesizer prompt. It's not a standalone rule.

5. **Storage rules use the same `FindingCategory` system from Project A.** Cold
   storage candidates are INFORMATIONAL (recommendation, not violation). Excessive
   retention is ACTIONABLE.

## TDD Requirements

Every rule listed above requires:
1. Unit test with mock `ACCOUNT_USAGE` data asserting correct violation generation
2. Unit test asserting severity and category assignment
3. Unit test asserting conventions override behavior
4. Integration test: workload classifier produces correct classification for known
   query distribution shapes (unimodal short, unimodal long, bimodal)

## Ship Definition

1. PR with all new rules registered in `rule_registry.py`
2. `make check` passes
3. `rules_snapshot.yaml` updated with new rule IDs
4. Manual: `snowfort audit scan --manifest` includes warehouse sizing findings
   with credit-denominated savings projections

## Risks

| Risk | Mitigation |
|------|------------|
| `WAREHOUSE_LOAD_HISTORY` has 14-day retention in some editions | Detect available history range, degrade gracefully to `METERING_HISTORY` only |
| P50 utilization requires sufficient data points | Skip warehouse if < 7 days of history, note in finding |
| Credit-per-size table may change | Store as a convention-level constant, not magic numbers |
| `QUERY_HISTORY` can be very large (billions of rows) | Aggregate server-side with date filter; never fetch raw rows |
