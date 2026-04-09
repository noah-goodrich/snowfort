# Warehouse Sizing Guide

Use this matrix to choose the right warehouse size for each workload type.
Oversizing wastes credits; undersizing forces spilling and query queuing.

## Workload → Recommended Size

| Workload Type | Recommended Size | Rationale |
|---|---|---|
| Interactive queries / BI dashboards | XS – S | Low concurrency, small result sets; query caching covers repeat access |
| ELT loads (dbt, Fivetran) — row counts < 1B/day | S – M | Moderate parallelism; scale up only when query queuing appears |
| ELT loads — row counts ≥ 1B/day | M – L | High I/O; L unlocks faster scan threads per node |
| Large-table aggregations / window functions | L – XL | Memory-bound; spilling to disk degrades XS/S dramatically |
| ML feature engineering / COPY INTO | M – XL | Burst workload; use multi-cluster + auto-resume |
| Snowpark (Python UDFs, ML inference) | L – 2XL | JVM + Python heap per node; under-sizing causes OOM |
| SPCS (Snowpark Container Services) | Dedicated compute pool | Containers run on compute pools, not virtual warehouses |
| Cortex LLM functions (COMPLETE, etc.) | XS – S | Serverless billing; warehouse size does not affect Cortex credit consumption |
| Search Optimization Service | Managed by Snowflake | Not billed against virtual warehouses |
| Admin tasks (GRANT, ALTER, SHOW) | XS | Metadata operations; no benefit from larger sizes |

## Auto-Suspend Recommendation

| Scenario | `AUTO_SUSPEND` Setting |
|---|---|
| Interactive / ad-hoc (default) | 30s — eliminates idle waste; cold-start is fast on XS/S |
| Batch pipelines with known schedule | Equal to pipeline cadence (e.g., 3600s for hourly jobs) |
| Always-on BI tools (Tableau Live, Sigma) | 120–300s — avoids disrupting active sessions |

Snowfort Audit flags warehouses with `AUTO_SUSPEND > 3600s` (COST_001 hard cap) and `AUTO_SUSPEND > 30s` (COST_001 standard).

## Multi-Cluster Settings

Use **multi-cluster** (AUTO_MIN=1, AUTO_MAX=N) for:
- Dashboards with concurrent users (>5 simultaneous queries)
- Pipelines that run dbt models in parallel

Use **single-cluster** for:
- Sequential ELT jobs
- Snowfort Audit itself (single-pass, not concurrency-bound)

## Resource Monitor Recommendation

Attach a **Resource Monitor** to every production warehouse with a monthly credit quota:

```sql
CREATE RESOURCE MONITOR prod_wh_monitor
  WITH CREDIT_QUOTA = 500
  TRIGGERS
    ON 80 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE my_prod_wh SET RESOURCE_MONITOR = prod_wh_monitor;
```

Snowfort Audit flags warehouses without a Resource Monitor (OP_001).

## Key-Pair Auth for Parallel Scans

Snowfort Audit uses `--workers N` to parallelize rules across N warehouse connections.
Interactive authentication (browser SSO, MFA) supports only one active connection;
parallel workers fall back to 1 worker automatically.

To use parallel scanning, configure key-pair auth:

```bash
# Generate a keypair and get the ALTER USER SQL:
snowfort audit bootstrap --keypair

# Then set the environment variables:
export SNOWFLAKE_AUTHENTICATOR=snowflake_jwt
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/snowfort_rsa_key.p8
```

Run `snowfort audit scan --workers 4` to benefit from parallel execution.
