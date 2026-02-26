-- STAT_002: Naked DROP statement
-- Intended to trigger: "Destructive DROP statement detected"
DROP TABLE IF EXISTS DEV_BRONZE.RAW.STAGING;
DROP SCHEMA IF EXISTS DEV_BRONZE.LEGACY;
