-- STAT_005: Dynamic table with >5 JOINs (WAF: keep JOIN count minimal)
-- Intended to trigger: "Dynamic Table Complexity"
CREATE OR REPLACE DYNAMIC TABLE gold.customer_360
    TARGET_LAG = '1 hour'
    WAREHOUSE = WH_TRANSFORM
AS
SELECT
    c.id,
    c.name,
    o.order_id,
    o.amount,
    p.product_name,
    r.region_name,
    s.score,
    t.tier
FROM bronze.customers c
JOIN bronze.orders o ON o.customer_id = c.id
JOIN bronze.order_lines ol ON ol.order_id = o.order_id
JOIN bronze.products p ON p.id = ol.product_id
JOIN bronze.regions r ON r.id = c.region_id
JOIN bronze.scores s ON s.customer_id = c.id
JOIN bronze.tiers t ON t.id = c.tier_id;
