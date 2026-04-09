!set variable_substitution=true;

-- Setup Script: The "Bad Architect" Environment (v0.3.0)
-- This script intentionally creates resources that violate Snowfort WAF rules.
-- Run this in a SANDBOX account to test the snowfort-audit online scanner.
--
-- All objects are prefixed SNOWFORT_TEST_ for easy identification/cleanup.
-- All warehouses are X-SMALL (minimal credit cost).
--
-- Triggers: SEC_002, SEC_003, SEC_004, SEC_006, SEC_008, SEC_011,
--   COST_001, COST_005, COST_008, COST_009, REL_002, REL_003, REL_006,
--   GOV_004, OPS_001, OPS_009, PERF_011.

USE ROLE ACCOUNTADMIN;

-- ============================================================
-- SECURITY pillar
-- ============================================================

-- [SEC_003] Network Policy: The Open Door
CREATE NETWORK POLICY IF NOT EXISTS BAD_OPEN_POLICY
    ALLOWED_IP_LIST = ('0.0.0.0/0')
    COMMENT = 'Violates SEC_003 (Allow All)';

-- [SEC_008] Zombie Role: No grants (Orphan + Empty)
CREATE ROLE IF NOT EXISTS ORPHAN_ROLE;

-- [SEC_002] Admin user without MFA
CREATE USER IF NOT EXISTS BAD_ADMIN_USER
    PASSWORD = 'Password123!'
    MUST_CHANGE_PASSWORD = FALSE;
GRANT ROLE SYSADMIN TO USER BAD_ADMIN_USER;

-- [SEC_006] Service user with password auth
CREATE USER IF NOT EXISTS BAD_SVC_USER
    PASSWORD = 'Password123!'
    DEFAULT_ROLE = PUBLIC
    COMMENT = 'Service User';

-- [SEC_011] Password-only user (no MFA, no SSO, no key-pair)
CREATE USER IF NOT EXISTS SNOWFORT_TEST_PWD_USER
    PASSWORD = 'TestPassword456!'
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Violates SEC_011 (password-only auth)';

-- [SEC_004] Public grants
CREATE WAREHOUSE IF NOT EXISTS SNOWFORT_TEST_PUBLIC_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;
GRANT USAGE ON WAREHOUSE SNOWFORT_TEST_PUBLIC_WH TO ROLE PUBLIC;

-- ============================================================
-- COST pillar
-- ============================================================

-- [COST_001] Warehouse with very high auto-suspend
CREATE WAREHOUSE IF NOT EXISTS BAD_COST_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 3600
    AUTO_RESUME = TRUE
    COMMENT = 'Violates COST_001 (1hr auto-suspend)';

-- [COST_005] Multi-cluster standard scaling
CREATE WAREHOUSE IF NOT EXISTS BAD_MC_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    MAX_CLUSTER_COUNT = 2
    SCALING_POLICY = 'STANDARD'
    COMMENT = 'Violates COST_005 (Standard scaling)';

-- [COST_008] Staging-named permanent table (should be transient)
CREATE DATABASE IF NOT EXISTS BAD_PRACTICE_DB;
CREATE SCHEMA IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC;
CREATE TABLE IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC.STG_ORDERS (
    id INT, data VARIANT
) COMMENT = 'Violates COST_008 (staging-named permanent table)';

-- ============================================================
-- RELIABILITY pillar
-- ============================================================

-- [REL_002] Table with zero retention + [REL_003] schema evolution
CREATE TABLE IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC.FRAGILE_TABLE (id INT)
    DATA_RETENTION_TIME_IN_DAYS = 0
    ENABLE_SCHEMA_EVOLUTION = TRUE;

-- [REL_006] Production-like table with 1-day retention
CREATE DATABASE IF NOT EXISTS PRD_BAD_DB;
CREATE SCHEMA IF NOT EXISTS PRD_BAD_DB.PUBLIC;
CREATE TABLE IF NOT EXISTS PRD_BAD_DB.PUBLIC.CRITICAL_TABLE (
    id INT, data VARIANT
) DATA_RETENTION_TIME_IN_DAYS = 1
  COMMENT = 'Violates REL_006 (1-day retention on prod table)';

-- ============================================================
-- PERFORMANCE pillar
-- ============================================================

-- [PERF_011] Bad clustering key: too many expressions + MOD anti-pattern
CREATE TABLE IF NOT EXISTS BAD_PRACTICE_DB.PUBLIC.BAD_CLUSTER_TABLE (
    id INT, region VARCHAR, category VARCHAR,
    created_date DATE, status INT, priority INT
) CLUSTER BY (id, region, category, created_date, MOD(status, 10));

-- ============================================================
-- GOVERNANCE pillar
-- ============================================================

-- [GOV_004] Database and tables without comments/documentation
CREATE DATABASE IF NOT EXISTS SNOWFORT_TEST_UNDOCUMENTED_DB;
CREATE SCHEMA IF NOT EXISTS SNOWFORT_TEST_UNDOCUMENTED_DB.PUBLIC;
CREATE TABLE IF NOT EXISTS SNOWFORT_TEST_UNDOCUMENTED_DB.PUBLIC.NO_DOCS_TABLE (
    id INT, mystery_col VARIANT
);

-- ============================================================
-- OPERATIONS pillar
-- ============================================================

-- [OPS_001] All warehouses/databases above are created WITHOUT tags.
-- [OPS_009] Warehouses above have no resource monitor assigned.

SELECT 'Snowfort WAF test environment configured with violations across all 6 pillars.' AS status;
