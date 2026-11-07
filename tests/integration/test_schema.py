"""The database itself enforces the critical rules (CHECK, UNIQUE, FOREIGN KEY).

The service layer validates first and returns friendly messages; these constraints
are the backstop that keeps data correct even if a code path forgets a check.
"""

from decimal import Decimal

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.database import engine
from app.core.enums import MovementType, OrderStatus, Role
from app.models import Product, SalesOrder, SalesOrderItem
from tests.factories import (
    make_customer,
    make_movement,
    make_order,
    make_product,
    make_user,
)

# MySQL reports CHECK violations as error 3819; PyMySQL may raise it as either class.
ConstraintViolation = (IntegrityError, OperationalError)


def test_health_reports_database_ok(client, migrated_database):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_migration_creates_all_six_tables(migrated_database):
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "customers",
        "products",
        "sales_orders",
        "sales_order_items",
        "stock_movements",
    } <= tables


def test_money_is_stored_as_exact_decimal(db_session):
    product = make_product(db_session, price=Decimal("1500.50"))
    db_session.commit()
    db_session.expire_all()
    stored = db_session.scalar(select(Product.price).where(Product.id == product.id))
    assert stored == Decimal("1500.50")
    assert isinstance(stored, Decimal)


def test_enums_are_stored_as_readable_text(db_session):
    admin = make_user(db_session, role=Role.ADMIN)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(type(admin), admin.id).role is Role.ADMIN


def test_user_email_is_unique(db_session):
    make_user(db_session, email="dup@example.com")
    with pytest.raises(IntegrityError):
        make_user(db_session, email="dup@example.com")


def test_product_code_is_unique(db_session):
    make_product(db_session, code="PRD-001")
    with pytest.raises(IntegrityError):
        make_product(db_session, code="PRD-001")


def test_product_stock_cannot_be_negative(db_session):
    with pytest.raises(ConstraintViolation):
        make_product(db_session, stock_quantity=-1)


def test_product_price_cannot_be_negative(db_session):
    with pytest.raises(ConstraintViolation):
        make_product(db_session, price=Decimal("-0.01"))


def test_stock_update_below_zero_is_rejected_by_database(db_session):
    product = make_product(db_session, stock_quantity=2)
    db_session.commit()
    product.stock_quantity = product.stock_quantity - 3
    with pytest.raises(ConstraintViolation):
        db_session.flush()


@pytest.mark.parametrize("discount", ["-1", "20.01", "21"])
def test_discount_outside_0_to_20_is_rejected_by_database(db_session, discount):
    customer, user = make_customer(db_session), make_user(db_session)
    with pytest.raises(ConstraintViolation):
        make_order(
            db_session, customer=customer, created_by=user, discount_percent=Decimal(discount)
        )


@pytest.mark.parametrize("discount", ["0", "12.5", "20"])
def test_discount_within_range_is_accepted(db_session, discount):
    customer, user = make_customer(db_session), make_user(db_session)
    order = make_order(
        db_session, customer=customer, created_by=user, discount_percent=Decimal(discount)
    )
    assert order.id


@pytest.mark.parametrize("quantity", [0, -5])
def test_order_item_quantity_must_be_positive(db_session, quantity):
    customer, user, product = (
        make_customer(db_session),
        make_user(db_session),
        make_product(db_session),
    )
    with pytest.raises(ConstraintViolation):
        make_order(db_session, customer=customer, created_by=user, items=[(product, quantity)])


def test_same_product_cannot_appear_twice_in_an_order(db_session):
    customer, user, product = (
        make_customer(db_session),
        make_user(db_session),
        make_product(db_session),
    )
    with pytest.raises(IntegrityError):
        make_order(
            db_session, customer=customer, created_by=user, items=[(product, 1), (product, 2)]
        )


def test_order_number_is_unique(db_session):
    customer, user = make_customer(db_session), make_user(db_session)
    first = make_order(db_session, customer=customer, created_by=user)
    second = make_order(db_session, customer=customer, created_by=user)
    second.order_number = first.order_number
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_customer_referenced_by_order_cannot_be_deleted(db_session):
    customer, user = make_customer(db_session), make_user(db_session)
    make_order(db_session, customer=customer, created_by=user)
    db_session.commit()
    db_session.delete(customer)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_referenced_by_order_item_cannot_be_deleted(db_session):
    customer, user, product = (
        make_customer(db_session),
        make_user(db_session),
        make_product(db_session),
    )
    make_order(db_session, customer=customer, created_by=user, items=[(product, 1)])
    db_session.commit()
    db_session.delete(product)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_referenced_by_stock_movement_cannot_be_deleted(db_session):
    product, user = make_product(db_session), make_user(db_session)
    make_movement(db_session, product=product, user=user, change=10)
    db_session.commit()
    db_session.delete(product)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unreferenced_customer_and_product_can_be_deleted(db_session):
    customer, product = make_customer(db_session), make_product(db_session)
    db_session.commit()
    db_session.delete(customer)
    db_session.delete(product)
    db_session.commit()


def test_stock_movement_change_cannot_be_zero(db_session):
    product, user = make_product(db_session), make_user(db_session)
    with pytest.raises(ConstraintViolation):
        make_movement(db_session, product=product, user=user, change=0, kind=MovementType.OPENING)


def test_order_items_are_deleted_with_their_order(db_session):
    customer, user, product = (
        make_customer(db_session),
        make_user(db_session),
        make_product(db_session),
    )
    order = make_order(db_session, customer=customer, created_by=user, items=[(product, 2)])
    db_session.commit()
    db_session.delete(order)
    db_session.commit()
    assert (
        db_session.scalar(select(SalesOrderItem).where(SalesOrderItem.order_id == order.id)) is None
    )


def test_new_order_defaults_to_draft_with_zero_totals(db_session):
    customer, user = make_customer(db_session), make_user(db_session)
    order = make_order(db_session, customer=customer, created_by=user)
    db_session.commit()
    db_session.expire_all()
    stored = db_session.get(SalesOrder, order.id)
    assert stored.status is OrderStatus.DRAFT
    assert stored.grand_total == Decimal("0.00")
