-- =============================================================================
-- Standalone report queries (MySQL 8.x)
--
-- Run against the sample data:
--   docker compose exec -T mysql mysql -usales_app -psales_app_pw sales_db < sql/queries.sql
--
-- "Sales" means CONFIRMED orders only. Draft orders are not sales yet and
-- Cancelled orders were reversed, so both are excluded everywhere below.
-- Each query starts with a "-- name:" marker so the test suite can run it.
-- =============================================================================


-- name: top_customers
-- 1. Top three customers by Confirmed order grand total.
--    Grand total is already after the order discount. sales_order_items is not
--    joined, so an order with several lines is still counted once.
SELECT c.id,
       c.name,
       COUNT(o.id)        AS confirmed_orders,
       SUM(o.grand_total) AS total_sales
FROM customers c
JOIN sales_orders o
  ON o.customer_id = c.id
 AND o.status = 'CONFIRMED'
GROUP BY c.id, c.name
ORDER BY total_sales DESC, c.name
LIMIT 3;

-- Tie-aware variant: if two customers share third place, both are returned.
-- SELECT * FROM (
--     SELECT c.id, c.name, SUM(o.grand_total) AS total_sales,
--            DENSE_RANK() OVER (ORDER BY SUM(o.grand_total) DESC) AS sales_rank
--     FROM customers c
--     JOIN sales_orders o ON o.customer_id = c.id AND o.status = 'CONFIRMED'
--     GROUP BY c.id, c.name
-- ) ranked
-- WHERE sales_rank <= 3;


-- name: top_products
-- 2. Top three products by quantity sold in Confirmed orders.
SELECT p.id,
       p.code,
       p.name,
       SUM(i.quantity)      AS quantity_sold,
       COUNT(DISTINCT o.id) AS order_count
FROM sales_order_items i
JOIN sales_orders o
  ON o.id = i.order_id
 AND o.status = 'CONFIRMED'
JOIN products p
  ON p.id = i.product_id
GROUP BY p.id, p.code, p.name
ORDER BY quantity_sold DESC, p.code
LIMIT 3;


-- name: customers_without_orders
-- 3. Customers who have never placed any order (of any status: a Draft or a
--    Cancelled order still counts as "placed").
--    NOT EXISTS stops at the first matching order and, unlike NOT IN, is not
--    affected by NULLs.
SELECT c.id,
       c.name,
       c.email,
       c.city,
       c.is_active
FROM customers c
WHERE NOT EXISTS (
    SELECT 1
    FROM sales_orders o
    WHERE o.customer_id = c.id
)
ORDER BY c.name;


-- name: monthly_sales
-- 4. Month-wise Confirmed sales totals, grouped by year and month.
--    gross = before discount, net = after discount (what the customer pays).
SELECT YEAR(o.order_date)    AS sales_year,
       MONTH(o.order_date)   AS sales_month,
       COUNT(*)              AS confirmed_orders,
       SUM(o.subtotal)       AS gross_sales,
       SUM(o.discount_amount) AS total_discount,
       SUM(o.grand_total)    AS net_sales
FROM sales_orders o
WHERE o.status = 'CONFIRMED'
GROUP BY YEAR(o.order_date), MONTH(o.order_date)
ORDER BY sales_year, sales_month;


-- name: set_threshold
-- 5. Products below a supplied stock threshold. Change the value here.
SET @threshold = 10;

-- name: low_stock
SELECT p.id,
       p.code,
       p.name,
       p.category,
       p.stock_quantity,
       @threshold - p.stock_quantity AS below_threshold_by,
       p.is_active
FROM products p
WHERE p.stock_quantity < @threshold
ORDER BY p.stock_quantity, p.code;
