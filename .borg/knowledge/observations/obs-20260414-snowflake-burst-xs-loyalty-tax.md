---
id: obs-20260414-snowflake-burst-xs-loyalty-tax
session_date: '2026-06-16'
project: snowfort
tool: claude-code
tags:
- snowflake
- cost
- warehouses
- burst-xs
- waypoint
category: domain_knowledge
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-16 10:27:07.900902+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260414-snowflake-burst-xs-loyalty-tax

## content

BURST_XS warehouse (Snowflake's smallest on-demand size) is cost-defensible for the waypoint project's workload at Stage 1, but incurs approximately $10/month in idle-minimum spend that has no performance return — termed a 'loyalty tax' for staying on Snowflake before query volume justifies it over a Postgres-equivalent.

## resolution

Accept the loyalty tax if Snowflake's ecosystem features (sharing, native apps, future data product path) are part of the strategic bet. Reject Snowflake (as wallpaper-kit correctly did) when the workload is pure relational CRUD with no data product ambitions.
