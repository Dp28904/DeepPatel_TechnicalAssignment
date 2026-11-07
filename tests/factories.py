"""Small helpers that insert test rows directly. Each returns the flushed model."""

from datetime import date
from decimal import Decimal
from itertools import count

from sqlalchemy.orm import Session

from app.core.enums import MovementType, OrderStatus, Role
from app.models import Customer, Product, SalesOrder, SalesOrderItem, StockMovement, User

_seq = count(1)


def make_user(db: Session, *, role: Role = Role.SALES, **overrides) -> User:
    n = next(_seq)
    user = User(
        name=overrides.pop("name", f"User {n}"),
        email=overrides.pop("email", f"user{n}@example.com"),
        password_hash=overrides.pop("password_hash", "not-a-real-hash"),
        role=role,
        **overrides,
    )
    db.add(user)
    db.flush()
    return user


def make_customer(db: Session, **overrides) -> Customer:
    n = next(_seq)
    customer = Customer(
        name=overrides.pop("name", f"Customer {n}"),
        email=overrides.pop("email", f"customer{n}@example.com"),
        mobile=overrides.pop("mobile", f"98765{n:05d}"),
        city=overrides.pop("city", "Ahmedabad"),
        **overrides,
    )
    db.add(customer)
    db.flush()
    return customer


def make_product(db: Session, **overrides) -> Product:
    n = next(_seq)
    product = Product(
        code=overrides.pop("code", f"PRD-{n:04d}"),
        name=overrides.pop("name", f"Product {n}"),
        category=overrides.pop("category", "Accessories"),
        price=overrides.pop("price", Decimal("100.00")),
        stock_quantity=overrides.pop("stock_quantity", 10),
        **overrides,
    )
    db.add(product)
    db.flush()
    return product


def make_order(
    db: Session,
    *,
    customer: Customer,
    created_by: User,
    items: list[tuple[Product, int]] = (),
    status: OrderStatus = OrderStatus.DRAFT,
    discount_percent: Decimal = Decimal("0"),
) -> SalesOrder:
    """Insert an order with raw values (no business rules). Totals are left at zero."""
    n = next(_seq)
    order = SalesOrder(
        order_number=f"TEST-{n:06d}",
        customer_id=customer.id,
        order_date=date.today(),
        status=status,
        discount_percent=discount_percent,
        created_by=created_by.id,
    )
    for product, quantity in items:
        order.items.append(
            SalesOrderItem(
                product_id=product.id,
                quantity=quantity,
                rate=product.price,
                amount=product.price * quantity,
            )
        )
    db.add(order)
    db.flush()
    return order


def make_movement(
    db: Session, *, product: Product, user: User, change: int, kind=MovementType.OPENING
) -> StockMovement:
    movement = StockMovement(
        product_id=product.id, movement_type=kind, quantity_change=change, created_by=user.id
    )
    db.add(movement)
    db.flush()
    return movement
