-- STAT_006: Anti-pattern SQL (ORDER BY without LIMIT, OR in JOIN, UNION vs UNION ALL)
-- Intended to trigger: "Anti-Pattern SQL Detection"

-- ORDER BY without LIMIT
SELECT user_id, SUM(amount) AS total
FROM orders
GROUP BY user_id
ORDER BY total DESC;

-- OR in JOIN predicate (can prevent efficient pruning)
SELECT a.id, b.name
FROM table_a a
JOIN table_b b ON (b.ref_id = a.id OR b.alt_id = a.id);

-- UNION where UNION ALL might suffice (deduplication cost)
SELECT id, name FROM legacy.users
UNION
SELECT id, name FROM staging.users;
