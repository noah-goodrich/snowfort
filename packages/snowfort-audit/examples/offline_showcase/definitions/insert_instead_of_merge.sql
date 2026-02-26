-- STAT_004: INSERT INTO ... SELECT (consider idempotent MERGE)
-- Intended to trigger: "MERGE Pattern Recommendation"
INSERT INTO silver.daily_summary
SELECT
    date_trunc('day', created_at) AS day,
    COUNT(*),
    SUM(amount)
FROM bronze.orders
WHERE created_at >= CURRENT_DATE() - 1
GROUP BY 1;
