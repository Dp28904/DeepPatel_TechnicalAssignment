"""initial schema

Creates the six tables: users, customers, products, sales_orders,
sales_order_items and stock_movements.

Key decisions (see docs/DATABASE.md):
- Money columns are DECIMAL(12,2); discount_percent is DECIMAL(5,2).
- CHECK constraints are the last line of defence: stock and prices can never be
  negative, quantities are positive, discount stays within 0-20.
- Foreign keys to customers/products/users use RESTRICT, so referenced master
  data cannot be deleted (it can be deactivated instead).
- Order items cascade with their order; one product appears once per order.

Revision ID: 0001
Revises:
Create Date: 2026-11-08 00:25:26.434848
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("mobile", sa.String(length=20), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)
    op.create_index(op.f("ix_customers_is_active"), "customers", ["is_active"], unique=False)
    op.create_index(op.f("ix_customers_mobile"), "customers", ["mobile"], unique=False)
    op.create_index(op.f("ix_customers_name"), "customers", ["name"], unique=False)
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("price >= 0", name=op.f("ck_products_price_non_negative")),
        sa.CheckConstraint("stock_quantity >= 0", name=op.f("ck_products_stock_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("code", name=op.f("uq_products_code")),
    )
    op.create_index(op.f("ix_products_category"), "products", ["category"], unique=False)
    op.create_index(op.f("ix_products_is_active"), "products", ["is_active"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "SALES", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "sales_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "CONFIRMED", "CANCELLED", name="order_status"),
            nullable=False,
        ),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 20",
            name=op.f("ck_sales_orders_discount_percent_range"),
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount_amount >= 0 AND grand_total >= 0",
            name=op.f("ck_sales_orders_amounts_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by"],
            ["users.id"],
            name=op.f("fk_sales_orders_cancelled_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name=op.f("fk_sales_orders_confirmed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_sales_orders_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_sales_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_orders")),
        sa.UniqueConstraint("order_number", name=op.f("uq_sales_orders_order_number")),
    )
    op.create_index(
        op.f("ix_sales_orders_created_by"), "sales_orders", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_sales_orders_customer_id"), "sales_orders", ["customer_id"], unique=False
    )
    op.create_index(
        "ix_sales_orders_status_order_date", "sales_orders", ["status", "order_date"], unique=False
    )
    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_sales_order_items_quantity_positive")),
        sa.CheckConstraint(
            "rate >= 0 AND amount >= 0", name=op.f("ck_sales_order_items_amounts_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["sales_orders.id"],
            name=op.f("fk_sales_order_items_order_id_sales_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_sales_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_order_items")),
        sa.UniqueConstraint("order_id", "product_id", name="uq_sales_order_items_order_product"),
    )
    op.create_index(
        op.f("ix_sales_order_items_product_id"), "sales_order_items", ["product_id"], unique=False
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "movement_type",
            sa.Enum(
                "OPENING",
                "ADJUSTMENT_IN",
                "ADJUSTMENT_OUT",
                "ORDER_CONFIRM",
                "ORDER_CANCEL",
                name="movement_type",
            ),
            nullable=False,
        ),
        sa.Column("quantity_change", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "quantity_change <> 0", name=op.f("ck_stock_movements_quantity_change_non_zero")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_stock_movements_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["sales_orders.id"],
            name=op.f("fk_stock_movements_order_id_sales_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_movements_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(
        op.f("ix_stock_movements_created_at"), "stock_movements", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_stock_movements_movement_type"), "stock_movements", ["movement_type"], unique=False
    )
    op.create_index(
        op.f("ix_stock_movements_order_id"), "stock_movements", ["order_id"], unique=False
    )
    op.create_index(
        "ix_stock_movements_product_id_created_at",
        "stock_movements",
        ["product_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop tables child-first. Dropping a table also drops its indexes; MySQL refuses
    # to drop an index on its own while a foreign key still depends on it.
    for table in (
        "stock_movements",
        "sales_order_items",
        "sales_orders",
        "users",
        "products",
        "customers",
    ):
        op.drop_table(table)
