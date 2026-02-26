-- STAT_001: Hardcoded environment suffix _DEV
-- Intended to trigger: "Hardcoded environment suffix detected"
SELECT *
FROM DEV_BRONZE_DEV.RAW.EVENTS
WHERE env = 'DEV';
