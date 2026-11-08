"""Customer business rules: visibility by role, create/update, safe delete."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access import can_see, visible_status
from app.core.enums import StatusFilter
from app.core.exceptions import Conflict, NotFound
from app.core.pagination import PageParams, paginate
from app.modules.customers import repository
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerIn, CustomerOut
from app.modules.orders import usage as order_usage
from app.modules.users.models import User


def list_customers(
    db: Session, user: User, search: str | None, status: StatusFilter, params: PageParams
) -> dict:
    statement = repository.search_statement(search, visible_status(user, status))
    return paginate(db, statement, params, CustomerOut.model_validate)


def get_customer(db: Session, user: User, customer_id: int) -> Customer:
    """Return a customer the user may see. Inactive customers are hidden from Sales Users."""
    customer = repository.get(db, customer_id)
    if customer is None or not can_see(user, customer.is_active):
        raise NotFound(f"Customer {customer_id} was not found.")
    return customer


def create_customer(db: Session, data: CustomerIn) -> Customer:
    customer = repository.add(db, Customer(**data.model_dump()))
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, user: User, customer_id: int, data: CustomerIn) -> Customer:
    customer = get_customer(db, user, customer_id)
    for field, value in data.model_dump().items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)  # return exactly what was stored
    return customer


def _in_use_error(customer: Customer, order_count: int | None = None) -> Conflict:
    used_by = f"used by {order_count} order(s)" if order_count else "used by an order"
    return Conflict(
        f"'{customer.name}' is {used_by} and cannot be deleted. Deactivate the customer instead.",
        code="customer_in_use",
    )


def delete_customer(db: Session, user: User, customer_id: int) -> None:
    customer = get_customer(db, user, customer_id)
    order_count = order_usage.count_orders_for_customer(db, customer.id)
    if order_count:
        raise _in_use_error(customer, order_count)
    try:
        repository.delete(db, customer)
        db.commit()
    except IntegrityError as exc:
        # An order was created for this customer between our check and the delete;
        # the foreign key (ON DELETE RESTRICT) stopped it.
        db.rollback()
        raise _in_use_error(customer) from exc


# --- Used by the orders module ----------------------------------------------
def find_customer(db: Session, customer_id: int, *, lock_for_share: bool = False):
    """Return the customer (active or not) or None. ``lock_for_share`` takes a shared
    lock, so the customer cannot be changed or deleted until our transaction ends."""
    if lock_for_share:
        return repository.get_for_share(db, customer_id)
    return repository.get(db, customer_id)
