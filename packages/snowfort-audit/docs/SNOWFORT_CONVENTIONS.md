# Snowfort Conventions

Opinionated defaults for Snowfort audit and downstream IaC tools. Override any value via `[tool.snowfort.conventions]` in your project's `pyproject.toml`.

## Admin (default names)

| Convention       | Default       | Rationale |
|------------------|---------------|-----------|
| admin_database   | SNOWFORT      | Default admin database for account bootstrap and management objects. |
| admin_role       | SNOWFORT      | Role used for platform administration (replaces legacy HOID/THAIDAKAR in new setups). |
| admin_user       | SVC_SNOWFORT  | Service account for automation; prefix `SVC_` indicates non-human. |

## Warehouse

| Convention                   | Default | Rationale |
|-----------------------------|---------|-----------|
| auto_suspend_seconds        | 1       | Minimize credit waste; set higher only when you have a documented performance benefit (e.g. warm cache for dashboards). |
| max_statement_timeout_seconds | 3600  | Cap runaway queries at 1 hour; adjust per warehouse type (e.g. 900 for BI, 28800 for ETL). |
| scaling_policy_mcw          | ECONOMY | For multi-cluster warehouses, ECONOMY reduces premature spin-up vs STANDARD. |

## Naming

| Convention           | Default | Rationale |
|----------------------|---------|-----------|
| env_prefix_pattern   | `^(DEV\|STG\|PRD)_` | Environment prefix first (e.g. DEV_BRONZE) for consistent grouping and grants. |
| warehouse_pattern    | `^(DEV\|STG\|PRD)_\w+_(XSMALL\|...\|XXXLARGE)$` | `{ENV}_{FUNCTION}_{SIZE}`; explicit size prevents accidental resizing. |
| service_account_prefix | SVC_  | Distinguish service accounts from human users. |
| db_owner_role_suffix | _OWNER | Account-level owner role per database (e.g. DEV_BRONZE_OWNER). |

## Security

| Convention              | Default | Rationale |
|-------------------------|---------|-----------|
| require_mfa_all_users   | true    | Account-level REQUIRE_MFA_FOR_ALL_USERS reduces credential theft risk. |
| require_network_policy  | true    | Restrict client IPs where possible; MFA can compensate when IP restriction is not feasible. |
| max_account_admins     | 3       | Cap ACCOUNTADMIN count to limit blast radius. |
| min_account_admins     | 2       | At least two for redundancy and break-glass. |

## Tags

| Convention    | Default | Rationale |
|---------------|---------|-----------|
| required_tags | COST_CENTER, OWNER, ENVIRONMENT | Minimum set for cost attribution and ownership. |
| iac_tags      | MANAGED_BY | Tag for drift detection and IaC ownership (e.g. MANAGED_BY = 'terraform'). |

## Overriding in pyproject.toml

```toml
[tool.snowfort.conventions.warehouse]
auto_suspend_seconds = 60

[tool.snowfort.conventions.tags]
required_tags = ["COST_CENTER", "OWNER", "ENVIRONMENT", "TEAM"]
```

Values are merged over the defaults; only override what you need.
