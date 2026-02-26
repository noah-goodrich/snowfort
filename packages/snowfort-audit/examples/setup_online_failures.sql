!set variable_substitution=true;

-- Setup Script: The "Bad Architect" Environment
-- This script intentionally creates resources that violate Snowarch WAF rules.
-- Run this in a SANDBOX account to test the snowarch-audit online scanner.

USE ROLE ACCOUNTADMIN;

-- 1. [SEC_003] Network Policy: The Open Door
CREATE NETWORK POLICY IF NOT EXISTS BAD_OPEN_POLICY
    ALLOWED_IP_LIST = ('0.0.0.0/0')
    COMMENTS = 'Violates SEC_003 (Allow All)';

-- 2. [COST_001] Warehouse: The Cash Furnace
CREATE WAREHOUSE IF NOT EXISTS BAD_COST_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 3600 -- 1 Hour (Violates COST_001)
    AUTO_RESUME = TRUE
    COMMENT = 'Violates COST_001 (High Auto Suspend)';

-- 3. [COST_005] Warehouse: Multi-Cluster standard scaling
CREATE WAREHOUSE IF NOT EXISTS BAD_MC_WH
    WITH WAREHOUSE_SIZE = 'SMALL'
    MAX_CLUSTER_COUNT = 2
    SCALING_POLICY = 'STANDARD' -- Should be ECONOMY (Violates COST_005)
    COMMENT = 'Violates COST_005 (Standard Scaling check)';

-- 4. [SEC_004] Public Grants: The Commons
GRANT USAGE ON WAREHOUSE BAD_COST_WH TO ROLE PUBLIC; -- Violates SEC_004

-- 5. [SEC_008] Zombie Roles: The Orphan
CREATE ROLE IF NOT EXISTS ORPHAN_ROLE; -- Violates SEC_008 (No grants)

-- 6. [REL_002/REL_003] Reliability: Dangerous Tables
CREATE DATABASE IF NOT EXISTS BAD_PRACTICE_DB;
CREATE SCHEMA IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC;

CREATE TABLE IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC.FRAGILE_TABLE (id int)
    DATA_RETENTION_TIME_IN_DAYS = 0 -- Violates REL_002
    ENABLE_SCHEMA_EVOLUTION = TRUE; -- Violates REL_003

-- 7. [OPS_001] Tags: The Mystery Box
-- Resources above (Warehouses, DB) created without Tags violate OPS_001.

-- 8. [SEC_002] Identity: The Unprotected Admin
CREATE USER IF NOT EXISTS BAD_ADMIN_USER
    PASSWORD = 'Password123!'
    MUST_CHANGE_PASSWORD = FALSE;
GRANT ROLE SYSADMIN TO USER BAD_ADMIN_USER; -- Violates SEC_002 (Admin w/o MFA)

-- 9. [SEC_006] Service User: Password Auth
CREATE USER IF NOT EXISTS BAD_SVC_USER
    PASSWORD = 'Password123!'
    DEFAULT_ROLE = PUBLIC
    COMMENT = 'Service User'; -- Heuristic for Service User checks
-- Violates SEC_006 (Should use Key Pair)

SELECT 'Environment configured with multiple WAF violations.' as status;
