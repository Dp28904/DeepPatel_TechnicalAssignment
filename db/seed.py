"""Load sample data for local development and the demo.

    python -m db.seed           # add sample data; existing rows are left alone
    python -m db.seed --reset   # empty every table first, then load sample data

Sample account emails and passwords come from .env (SEED_* variables), so no
credentials are stored in the repository.
"""

import argparse
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.enums import Role
from app.models import Base, Customer, SalesOrder
from app.modules.customers import service as customer_service
from app.modules.customers.schemas import CustomerIn
from app.modules.orders import service as order_service
from app.modules.orders.schemas import OrderIn
from app.modules.products import repository as product_repository
from app.modules.products import service as product_service
from app.modules.products.schemas import ProductCreate
from app.modules.users import repository as user_repository
from app.modules.users import service as user_service
from app.modules.users.schemas import UserCreate


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str
    seed_sales1_email: str = "sales1@example.com"
    seed_sales1_password: str
    seed_sales2_email: str = "sales2@example.com"
    seed_sales2_password: str


def reset_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    print("All tables emptied.")


def seed_users(db: Session, settings: SeedSettings) -> None:
    accounts = [
        ("Asha Admin", settings.seed_admin_email, settings.seed_admin_password, Role.ADMIN),
        ("Ravi Sales", settings.seed_sales1_email, settings.seed_sales1_password, Role.SALES),
        ("Meera Sales", settings.seed_sales2_email, settings.seed_sales2_password, Role.SALES),
    ]
    for name, email, password, role in accounts:
        if user_repository.get_by_email(db, email):
            print(f"  user exists, skipped: {email}")
            continue
        user_service.create_user(
            db, UserCreate(name=name, email=email, password=password, role=role)
        )
        print(f"  created {role.value:<5} {email}")


# name, email, mobile, city, active
SAMPLE_CUSTOMERS = [
    ("Shree Ganesh Traders", "accounts@shreeganesh.example.com", "9824012345", "Ahmedabad", True),
    ("Patel Electronics", "purchase@patelelec.example.com", "9898123456", "Surat", True),
    ("Mehta & Sons", "mehta.sons@example.com", "9426098765", "Vadodara", True),
    ("Sunrise Office Supplies", "orders@sunrise.example.com", "9712233445", "Rajkot", True),
    ("Kumar IT Solutions", "it@kumar.example.com", "9909887766", "Mumbai", True),
    ("Green Leaf Stationers", "hello@greenleaf.example.com", "9033445566", "Pune", True),
    ("Never Ordered Pvt Ltd", "info@neverordered.example.com", "9000011111", "Jaipur", True),
    ("Old Partner Co", "old@partner.example.com", "9000022222", "Indore", False),
]

# code, name, category, price, opening stock, active
SAMPLE_PRODUCTS = [
    ("PRD-001", "Keyboard", "Accessories", "1500.00", 20, True),
    ("PRD-002", "Mouse", "Accessories", "500.00", 50, True),
    ("PRD-003", "USB-C Hub", "Accessories", "2200.00", 8, True),
    ("PRD-004", "Webcam HD", "Accessories", "3200.00", 3, True),
    ("PRD-101", "24-inch Monitor", "Displays", "11500.00", 12, True),
    ("PRD-102", "27-inch Monitor", "Displays", "18999.00", 4, True),
    ("PRD-201", "Laptop Stand", "Furniture", "1800.00", 25, True),
    ("PRD-202", "Office Chair", "Furniture", "7499.00", 6, True),
    ("PRD-301", "HDMI Cable 2m", "Cables", "349.00", 120, True),
    ("PRD-302", "Ethernet Cable 5m", "Cables", "299.00", 2, True),
    ("PRD-401", "A4 Paper Ream", "Stationery", "325.50", 200, True),
    ("PRD-999", "VGA Cable (discontinued)", "Cables", "199.00", 0, False),
]


def seed_customers(db: Session) -> None:
    for name, email, mobile, city, active in SAMPLE_CUSTOMERS:
        if db.scalar(select(Customer).where(Customer.name == name)):
            print(f"  customer exists, skipped: {name}")
            continue
        customer_service.create_customer(
            db, CustomerIn(name=name, email=email, mobile=mobile, city=city, is_active=active)
        )
        print(f"  created customer {name}")


def seed_products(db: Session, admin) -> None:
    for code, name, category, price, stock, active in SAMPLE_PRODUCTS:
        if product_repository.get_by_code(db, code):
            print(f"  product exists, skipped: {code}")
            continue
        # Goes through the service, so opening stock is recorded as a stock movement.
        product_service.create_product(
            db,
            admin,
            ProductCreate(
                code=code,
                name=name,
                category=category,
                price=price,
                stock_quantity=stock,
                is_active=active,
            ),
        )
        print(f"  created product {code} (stock {stock})")


# customer, created by (admin/sales1/sales2), order date, discount %, items, what to do
SAMPLE_ORDERS = [
    (
        "Shree Ganesh Traders",
        "sales1",
        "2026-08-05",
        "10",
        [("PRD-001", 2), ("PRD-002", 3)],
        "confirm",
    ),
    ("Patel Electronics", "sales1", "2026-08-18", "5", [("PRD-101", 2), ("PRD-301", 4)], "confirm"),
    ("Mehta & Sons", "sales2", "2026-09-02", "0", [("PRD-201", 3), ("PRD-401", 10)], "confirm"),
    (
        "Kumar IT Solutions",
        "sales2",
        "2026-09-21",
        "15",
        [("PRD-102", 1), ("PRD-003", 2)],
        "confirm",
    ),
    (
        "Shree Ganesh Traders",
        "admin",
        "2026-10-03",
        "20",
        [("PRD-202", 2), ("PRD-201", 2)],
        "confirm",
    ),
    (
        "Sunrise Office Supplies",
        "sales1",
        "2026-10-14",
        "0",
        [("PRD-401", 25), ("PRD-301", 10)],
        "confirm",
    ),
    ("Patel Electronics", "sales2", "2026-10-28", "10", [("PRD-002", 5)], "confirm+cancel"),
    ("Green Leaf Stationers", "sales1", "2026-11-02", "0", [("PRD-401", 15)], "confirm"),
    ("Kumar IT Solutions", "sales1", "2026-11-05", "5", [("PRD-101", 1), ("PRD-002", 2)], "draft"),
    # Webcam stock is 3, so confirming this draft fails: handy for the demo.
    ("Mehta & Sons", "sales2", "2026-11-06", "0", [("PRD-004", 5)], "draft"),
    ("Sunrise Office Supplies", "sales2", "2026-11-07", "0", [("PRD-003", 1)], "cancel"),
]


def seed_orders(db: Session, users: dict) -> None:
    if db.scalar(select(SalesOrder.id).limit(1)):
        print("  orders exist, skipped")
        return
    customers = {c.name: c for c in db.scalars(select(Customer))}
    for customer_name, owner, order_date, discount, items, action in SAMPLE_ORDERS:
        user = users[owner]
        data = OrderIn(
            customer_id=customers[customer_name].id,
            order_date=order_date,
            discount_percent=discount,
            items=[
                {"product_id": product_repository.get_by_code(db, code).id, "quantity": qty}
                for code, qty in items
            ],
        )
        # Through the real services, so totals, stock and movements are all consistent.
        order = order_service.create_order(db, user, data)
        if "confirm" in action:
            order_service.confirm_order(db, user, order.id)
        if "cancel" in action:
            order_service.cancel_order(db, user, order.id)
        print(f"  {order.order_number} {customer_name:<24} {action}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m db.seed")
    parser.add_argument("--reset", action="store_true", help="empty all tables before seeding")
    args = parser.parse_args(argv)

    settings = SeedSettings()
    if args.reset:
        reset_database()

    with SessionLocal() as db:
        print("Seeding users...")
        seed_users(db, settings)
        admin = user_repository.get_by_email(db, settings.seed_admin_email)
        print("Seeding customers...")
        seed_customers(db)
        print("Seeding products...")
        seed_products(db, admin)
        print("Seeding orders...")
        users = {
            "admin": admin,
            "sales1": user_repository.get_by_email(db, settings.seed_sales1_email),
            "sales2": user_repository.get_by_email(db, settings.seed_sales2_email),
        }
        seed_orders(db, users)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
