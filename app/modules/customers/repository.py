"""Database queries for customers. No business rules here."""

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.enums import StatusFilter
from app.modules.customers.models import Customer


def get(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def search_statement(search: str | None, status: StatusFilter) -> Select:
    statement = select(Customer)
    if search:
        term = search.strip()
        statement = statement.where(
            or_(
                Customer.name.contains(term, autoescape=True),
                Customer.email.contains(term, autoescape=True),
                Customer.mobile.contains(term, autoescape=True),
            )
        )
    if status == StatusFilter.ACTIVE:
        statement = statement.where(Customer.is_active.is_(True))
    elif status == StatusFilter.INACTIVE:
        statement = statement.where(Customer.is_active.is_(False))
    return statement.order_by(Customer.name, Customer.id)


def add(db: Session, customer: Customer) -> Customer:
    db.add(customer)
    db.flush()
    return customer


def delete(db: Session, customer: Customer) -> None:
    db.delete(customer)
    db.flush()
