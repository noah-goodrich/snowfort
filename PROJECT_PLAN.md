# Project Plan: Streamlit Dashboard for WAF Audit Findings
*Established: 2026-05-11*

## Objective
Build a multi-page Streamlit-in-Snowflake (SiS) dashboard for interactive exploration of snowfort-audit findings,
with drill-down remediation details and historical score trending. Persisted via `--persist` flag on the CLI scan
command, stored in `SNOWFORT.AUDIT` schema, deployed via Snow CLI.

## Acceptance Criteria
- [ ] Existing `native_app/`, `streamlit_app.py`, and `SnowparkAuditRepository` removed
  - Verify: `ls packages/snowfort-audit/native_app` returns "No such file"
- [ ] `SNOWFORT.AUDIT.SCAN_METADATA` and `SNOWFORT.AUDIT.SCAN_VIOLATIONS` DDL exists
  - Verify: `sql/dashboard_schema.sql` contains both CREATE TABLE statements
- [ ] `snowfort audit scan --persist` writes scan results to Snowflake tables
  - Verify: Run scan with `--persist`, then `SELECT COUNT(*) FROM SNOWFORT.AUDIT.SCAN_METADATA` returns 1+
- [ ] Multi-page Streamlit app with 3 pages (Dashboard, Explorer, Trends)
  - Verify: `ls packages/snowfort-audit/streamlit/pages/` shows 3 page files
- [ ] Explorer page shows drill-down (rationale, remediation, quick-win badge) per violation
  - Verify: Manual test in Snowsight after deploy
- [ ] Trends page shows score-over-time line chart and scan comparison
  - Verify: Manual test after 2+ persisted scans
- [ ] `snowflake.yml` Snow CLI project config enables `snow streamlit deploy`
  - Verify: File exists and is valid YAML
- [ ] `snowfort audit deploy-dashboard` CLI command deploys the app
  - Verify: Command runs without error, prints dashboard URL
- [ ] Schema auto-creates if SNOWFORT DB doesn't exist (CREATE IF NOT EXISTS)
  - Verify: Unit test for PersistScanUseCase with mock cursor verifying DDL execution
- [ ] Full CI gate passes
  - Verify: `drone exec snowfort -- make check`

## Scope Boundaries
- NOT building: Native App packaging or Marketplace distribution
- NOT building: Scheduled Task for automatic scans (future directive)
- NOT building: Role-based access control within the dashboard (relies on Snowflake grants)
- NOT building: Real-time scan (dashboard reads persisted results, does not run scans)
- If done early: Ship, don't expand.

## Ship Definition
PR opened → CI passes (`drone exec snowfort -- make check`) → manual deploy test in Snowsight → merged to main.

## Risks
- Snow CLI may not be available in the devcontainer — mitigate by adding to dev deps and Dockerfile
- `CREATE DATABASE IF NOT EXISTS` requires ACCOUNTADMIN or CREATE DATABASE privilege — mitigate by documenting in
  bootstrap and handling insufficient privilege errors gracefully
- SiS multi-page apps require all pages in a `pages/` subdirectory relative to main_file — verify with Snow CLI docs
- Plotly/pandas must be in `environment.yml` for SiS (not pip-installed) — verify Anaconda channel availability

## Architecture

```
CLI (snowfort audit scan --persist)
    │
    ▼
PersistScanUseCase
    │
    ▼
SNOWFORT.AUDIT.SCAN_METADATA  ←──┐
SNOWFORT.AUDIT.SCAN_VIOLATIONS ←──┤
                                   │
Streamlit-in-Snowflake (SiS)  ────┘
├── Page 1: Dashboard (KPIs, charts)
├── Page 2: Explorer (drill-down, remediation)
└── Page 3: Trends (score history, regression, comparison)
```
