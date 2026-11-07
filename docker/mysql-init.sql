-- Runs once, when the MySQL data volume is first created.
-- Creates the separate database used by the automated test suite
-- and grants the application user access to it.
CREATE DATABASE IF NOT EXISTS sales_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON sales_test.* TO 'sales_app'@'%';
FLUSH PRIVILEGES;
