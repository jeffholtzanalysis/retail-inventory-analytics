-- Retail Inventory Analytics — analysis queries
-- Tested against SQLite (see sql/run_queries.py to execute all of these
-- against the CSVs in data/ and print results).

-- 1. Monthly revenue trend, chain-wide -------------------------------------
SELECT
    strftime('%Y-%m', t.date)                       AS month,
    SUM(t.units_sold)                                AS units_sold,
    ROUND(SUM(t.units_sold * p.unit_price), 2)       AS revenue
FROM inventory_transactions t
JOIN products p ON p.product_id = t.product_id
GROUP BY month
ORDER BY month;


-- 2. Top 10 products by revenue, with category ------------------------------
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(t.units_sold)                              AS units_sold,
    ROUND(SUM(t.units_sold * p.unit_price), 2)     AS revenue
FROM inventory_transactions t
JOIN products p ON p.product_id = t.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;


-- 3. Inventory turnover ratio per product (annualized) ----------------------
-- turnover = cost of goods sold / average inventory value
WITH cogs AS (
    SELECT
        t.product_id,
        SUM(t.units_sold * p.unit_cost) AS cogs
    FROM inventory_transactions t
    JOIN products p ON p.product_id = t.product_id
    GROUP BY t.product_id
),
avg_inv AS (
    SELECT
        t.product_id,
        AVG(t.units_in_stock_eod * p.unit_cost) AS avg_inventory_value
    FROM inventory_transactions t
    JOIN products p ON p.product_id = t.product_id
    GROUP BY t.product_id
)
SELECT
    p.product_id,
    p.product_name,
    p.category,
    ROUND(cogs.cogs, 2)                AS annual_cogs,
    ROUND(avg_inv.avg_inventory_value, 2) AS avg_inventory_value,
    ROUND(cogs.cogs / NULLIF(avg_inv.avg_inventory_value, 0), 2) AS turnover_ratio
FROM cogs
JOIN avg_inv ON avg_inv.product_id = cogs.product_id
JOIN products p ON p.product_id = cogs.product_id
ORDER BY turnover_ratio ASC;   -- slowest movers first (tie up cash)


-- 4. Stockout rate by store and category ------------------------------------
SELECT
    s.store_name,
    p.category,
    ROUND(100.0 * SUM(t.stockout_flag) / COUNT(*), 2) AS stockout_rate_pct,
    SUM(t.stockout_flag)                              AS stockout_days
FROM inventory_transactions t
JOIN stores s   ON s.store_id = t.store_id
JOIN products p ON p.product_id = t.product_id
GROUP BY s.store_name, p.category
ORDER BY stockout_rate_pct DESC
LIMIT 15;


-- 5. ABC analysis (Pareto): cumulative revenue share by product -------------
WITH product_revenue AS (
    SELECT
        p.product_id,
        p.product_name,
        SUM(t.units_sold * p.unit_price) AS revenue
    FROM inventory_transactions t
    JOIN products p ON p.product_id = t.product_id
    GROUP BY p.product_id, p.product_name
),
ranked AS (
    SELECT
        product_id,
        product_name,
        revenue,
        SUM(revenue) OVER (ORDER BY revenue DESC)
            / SUM(revenue) OVER () AS cum_revenue_share
    FROM product_revenue
)
SELECT
    product_id,
    product_name,
    ROUND(revenue, 2) AS revenue,
    ROUND(100 * cum_revenue_share, 1) AS cum_revenue_pct,
    CASE
        WHEN cum_revenue_share <= 0.80 THEN 'A'
        WHEN cum_revenue_share <= 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM ranked
ORDER BY revenue DESC;


-- 6. Store ranking by revenue per day open, with rank window function ------
SELECT
    s.store_name,
    s.region,
    ROUND(SUM(t.units_sold * p.unit_price), 2)               AS total_revenue,
    RANK() OVER (ORDER BY SUM(t.units_sold * p.unit_price) DESC) AS revenue_rank
FROM inventory_transactions t
JOIN stores s   ON s.store_id = t.store_id
JOIN products p ON p.product_id = t.product_id
GROUP BY s.store_name, s.region
ORDER BY revenue_rank;


-- 7. Products most frequently below reorder point (replenishment risk) ------
SELECT
    p.product_id,
    p.product_name,
    p.reorder_point,
    COUNT(*) FILTER (WHERE t.units_in_stock_eod <= p.reorder_point) AS days_at_or_below_reorder_point,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.units_in_stock_eod <= p.reorder_point) / COUNT(*), 1) AS pct_of_days
FROM inventory_transactions t
JOIN products p ON p.product_id = t.product_id
GROUP BY p.product_id, p.product_name, p.reorder_point
ORDER BY pct_of_days DESC
LIMIT 10;
