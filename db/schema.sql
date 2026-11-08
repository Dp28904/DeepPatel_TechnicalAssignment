-- Generated from the Alembic migrations with: alembic upgrade head --sql
-- Do not edit by hand. Regenerate with: make schema
-- MySQL 8.4

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE customers (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(150) NOT NULL, 
    email VARCHAR(255), 
    mobile VARCHAR(20), 
    city VARCHAR(100), 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_customers PRIMARY KEY (id)
);

CREATE INDEX ix_customers_email ON customers (email);

CREATE INDEX ix_customers_is_active ON customers (is_active);

CREATE INDEX ix_customers_mobile ON customers (mobile);

CREATE INDEX ix_customers_name ON customers (name);

CREATE TABLE products (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    code VARCHAR(30) NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    category VARCHAR(80) NOT NULL, 
    price NUMERIC(12, 2) NOT NULL, 
    stock_quantity INTEGER NOT NULL, 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_products PRIMARY KEY (id), 
    CONSTRAINT ck_products_price_non_negative CHECK (price >= 0), 
    CONSTRAINT ck_products_stock_non_negative CHECK (stock_quantity >= 0), 
    CONSTRAINT uq_products_code UNIQUE (code)
);

CREATE INDEX ix_products_category ON products (category);

CREATE INDEX ix_products_is_active ON products (is_active);

CREATE INDEX ix_products_name ON products (name);

CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(150) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    `role` ENUM('ADMIN','SALES') NOT NULL, 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE sales_orders (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    order_number VARCHAR(40) NOT NULL, 
    customer_id INTEGER NOT NULL, 
    order_date DATE NOT NULL, 
    status ENUM('DRAFT','CONFIRMED','CANCELLED') NOT NULL, 
    discount_percent NUMERIC(5, 2) NOT NULL, 
    subtotal NUMERIC(12, 2) NOT NULL, 
    discount_amount NUMERIC(12, 2) NOT NULL, 
    grand_total NUMERIC(12, 2) NOT NULL, 
    created_by INTEGER NOT NULL, 
    confirmed_by INTEGER, 
    cancelled_by INTEGER, 
    confirmed_at DATETIME, 
    cancelled_at DATETIME, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_sales_orders PRIMARY KEY (id), 
    CONSTRAINT ck_sales_orders_discount_percent_range CHECK (discount_percent >= 0 AND discount_percent <= 20), 
    CONSTRAINT ck_sales_orders_amounts_non_negative CHECK (subtotal >= 0 AND discount_amount >= 0 AND grand_total >= 0), 
    CONSTRAINT fk_sales_orders_cancelled_by_users FOREIGN KEY(cancelled_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_sales_orders_confirmed_by_users FOREIGN KEY(confirmed_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_sales_orders_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_sales_orders_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_sales_orders_order_number UNIQUE (order_number)
);

CREATE INDEX ix_sales_orders_created_by ON sales_orders (created_by);

CREATE INDEX ix_sales_orders_customer_id ON sales_orders (customer_id);

CREATE INDEX ix_sales_orders_status_order_date ON sales_orders (status, order_date);

CREATE TABLE sales_order_items (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    order_id INTEGER NOT NULL, 
    product_id INTEGER NOT NULL, 
    quantity INTEGER NOT NULL, 
    rate NUMERIC(12, 2) NOT NULL, 
    amount NUMERIC(12, 2) NOT NULL, 
    CONSTRAINT pk_sales_order_items PRIMARY KEY (id), 
    CONSTRAINT ck_sales_order_items_quantity_positive CHECK (quantity > 0), 
    CONSTRAINT ck_sales_order_items_amounts_non_negative CHECK (rate >= 0 AND amount >= 0), 
    CONSTRAINT fk_sales_order_items_order_id_sales_orders FOREIGN KEY(order_id) REFERENCES sales_orders (id) ON DELETE CASCADE, 
    CONSTRAINT fk_sales_order_items_product_id_products FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_sales_order_items_order_product UNIQUE (order_id, product_id)
);

CREATE INDEX ix_sales_order_items_product_id ON sales_order_items (product_id);

CREATE TABLE stock_movements (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    product_id INTEGER NOT NULL, 
    movement_type ENUM('OPENING','ADJUSTMENT_IN','ADJUSTMENT_OUT','ORDER_CONFIRM','ORDER_CANCEL') NOT NULL, 
    quantity_change INTEGER NOT NULL, 
    order_id INTEGER, 
    reason VARCHAR(255), 
    created_by INTEGER NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_stock_movements PRIMARY KEY (id), 
    CONSTRAINT ck_stock_movements_quantity_change_non_zero CHECK (quantity_change <> 0), 
    CONSTRAINT fk_stock_movements_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_stock_movements_order_id_sales_orders FOREIGN KEY(order_id) REFERENCES sales_orders (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_stock_movements_product_id_products FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
);

CREATE INDEX ix_stock_movements_created_at ON stock_movements (created_at);

CREATE INDEX ix_stock_movements_movement_type ON stock_movements (movement_type);

CREATE INDEX ix_stock_movements_order_id ON stock_movements (order_id);

CREATE INDEX ix_stock_movements_product_id_created_at ON stock_movements (product_id, created_at);

INSERT INTO alembic_version (version_num) VALUES ('0001');

-- Running upgrade 0001 -> 0002

ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT '1';

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

