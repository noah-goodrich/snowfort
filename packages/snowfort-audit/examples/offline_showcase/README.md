# Offline audit showcase

This folder is a **deliberately non-compliant** sample project so you can see the offline scanner in action.

## Run

From the `packages/snowfort-audit` directory (or pass the full path to this folder):

```bash
snowfort-audit scan --offline --path examples/offline_showcase
```

With remediation details and JSON manifest:

```bash
snowfort-audit scan --offline --path examples/offline_showcase -v --manifest
```

## Intended violations

| Source | Rule | What’s wrong |
|--------|------|--------------|
| `manifest.yml` | COST_001 | `DEV_SLOW_WH`: auto_suspend 3600s (max 60s for DEV) |
| `manifest.yml` | COST_005 | `DEV_MC_WH`: multi-cluster with STANDARD scaling |
| `manifest.yml` | REL_003 | `fragile_events`: table with enable_schema_evolution |
| `hardcoded_env.sql` | STAT_001 | Hardcoded `_DEV` suffix |
| `destructive.sql` | STAT_002 | DROP TABLE / DROP SCHEMA |
| `secret_exposure.sql` | STAT_003 | Hardcoded `PASSWORD = '...'` |
| `select_star.sql` | SQL_001 | `SELECT *` |
| `insert_instead_of_merge.sql` | STAT_004 | INSERT INTO ... SELECT; consider idempotent MERGE |
| `complex_dynamic_table.sql` | STAT_005 | Dynamic table with >5 JOINs |
| `antipattern_sql.sql` | STAT_006 | ORDER BY without LIMIT; OR in JOIN; UNION vs UNION ALL |
