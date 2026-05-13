# Project Plan: Streamlit Dashboard for WAF Audit Findings
*Established: 2026-05-11*
*Shipped: 2026-05-11 — PR #20 merged to main*

## Objective
Build a multi-page Streamlit-in-Snowflake (SiS) dashboard for interactive exploration of snowfort-audit findings,
with drill-down remediation details and historical score trending. Persisted via `--persist` flag on the CLI scan
command, stored in `SNOWFORT.AUDIT` schema, deployed via Snow CLI.

## Acceptance Criteria
- [x] Existing `native_app/`, `streamlit_app.py`, and `SnowparkAuditRepository` removed
- [x] `SNOWFORT.AUDIT.SCAN_METADATA` and `SNOWFORT.AUDIT.SCAN_VIOLATIONS` DDL exists
- [x] `snowfort audit scan --persist` writes scan results to Snowflake tables
- [x] Multi-page Streamlit app with 3 pages (Dashboard, Explorer, Trends)
- [x] Explorer page shows drill-down (rationale, remediation, quick-win badge) per violation
- [x] Trends page shows score-over-time line chart and scan comparison
- [x] `snowflake.yml` Snow CLI project config enables `snow streamlit deploy`
- [x] `snowfort audit deploy-dashboard` CLI command deploys the app
- [x] Schema auto-creates if SNOWFORT DB doesn't exist (CREATE IF NOT EXISTS)
- [x] Full CI gate passes

## Scope Boundaries
- NOT building: Native App packaging or Marketplace distribution
- NOT building: Scheduled Task for automatic scans (future directive)
- NOT building: Role-based access control within the dashboard (relies on Snowflake grants)
- NOT building: Real-time scan (dashboard reads persisted results, does not run scans)
