-- SQL_001: SELECT * (AM04 / star)
-- Intended to trigger: "No SELECT *" rule when SQLFluff validates
SELECT *
FROM silver.orders
WHERE created_at > CURRENT_DATE() - 7;
