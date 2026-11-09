"""Sales order business rules: Draft create/edit, confirm, cancel, ownership.

Status flow
    DRAFT -> CONFIRMED   deduct stock
    DRAFT -> CANCELLED   no stock change
    CONFIRMED -> CANCELLED   restore stock
    CANCELLED is final. Only DRAFT orders can be edited.

Concurrency (see docs/CONCURRENCY.md)
    Every state change runs in one transaction that:
    1. locks the order row (SELECT ... FOR UPDATE). Concurrent edits, confirms and
       cancels of the same order queue up here, and the status re-check after the lock
       makes repeated confirm/cancel requests harmless (409, nothing changes);
    2. locks the product rows in ascending id order (a fixed order prevents deadlocks);
    3. checks every item, then changes stock and writes stock movements;
    4. commits, or rolls back everything if anything fails.
    The CHECK (stock_quantity >= 0) constraint is a final safety net.

Ownership
    Sales Users can only see and act on orders they created. Someone else's order
    is reported as 404 Not Found, so its existence is not revealed.
"""

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.constants import ORDER_NUMBER_PREFIX
from app.core.database import transaction, utc_now
from app.core.dates import validate_date_range
from app.core.enums import MovementType, OrderStatus
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, paginate
from app.modules.customers import service as customer_service
from app.modules.inventory import service as inventory_service
from app.modules.orders import repository
from app.modules.orders.calculations import calculate_order_totals
from app.modules.orders.models import SalesOrder, SalesOrderItem
from app.modules.orders.schemas import OrderIn, OrderSummaryOut
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.users.models import User


# --- Access ---------------------------------------------------------------
def _can_access(user: User, order: SalesOrder) -> bool:
    return user.is_admin or order.created_by == user.id


def _not_found(order_id: int) -> NotFound:
    return NotFound(f"Order {order_id} was not found.")


def _require_status(order: SalesOrder, allowed: OrderStatus, action: str) -> None:
    if order.status != allowed:
        raise Conflict(
            f"Order {order.order_number} is {order.status.value.lower()}; "
            f"only {allowed.value.lower()} orders can be {action}.",
            code="invalid_order_status",
            details={"status": order.status.value},
        )


def _lock_accessible_order(db: Session, user: User, order_id: int) -> SalesOrder:
    order = repository.get_for_update(db, order_id)
    if order is None or not _can_access(user, order):
        raise _not_found(order_id)
    return order


# --- Reading --------------------------------------------------------------
def list_orders(
    db: Session,
    user: User,
    params: PageParams,
    *,
    status: OrderStatus | None = None,
    customer_id: int | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    validate_date_range(date_from, date_to)
    statement = repository.search_statement(
        created_by=None if user.is_admin else user.id,
        status=status,
        customer_id=customer_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
    return paginate(db, statement, params, OrderSummaryOut.from_model)


def get_order(db: Session, user: User, order_id: int) -> SalesOrder:
    order = repository.get(db, order_id)
    if order is None or not _can_access(user, order):
        raise _not_found(order_id)
    return order


# --- Draft validation -------------------------------------------------------
def _require_active_customer(db: Session, customer_id: int) -> None:
    customer = customer_service.find_customer(db, customer_id)
    if customer is None or not customer.is_active:
        message = "Select an active customer."
        raise ValidationFailed(message, details=[{"field": "customer_id", "message": message}])


def _require_active_products(db: Session, data: OrderIn) -> dict[int, Product]:
    products = product_service.get_products_by_ids(db, [item.product_id for item in data.items])
    errors = []
    for index, item in enumerate(data.items):
        product = products.get(item.product_id)
        if product is None:
            message = f"Product {item.product_id} does not exist."
        elif not product.is_active:
            message = f"'{product.code}' is inactive and cannot be ordered."
        else:
            continue
        errors.append({"field": f"items.{index}.product_id", "message": message})
    if errors:
        raise ValidationFailed("Some products cannot be ordered.", details=errors)
    return products


def _apply_draft(order: SalesOrder, data: OrderIn, products: dict[int, Product]) -> None:
    """Set customer, date, discount and items, then recalculate every amount.

    A line that already exists keeps its stored rate, so a later price change does
    not alter it. A new line takes the product's current price from the database
    (never a price sent by the browser).
    """
    existing = {item.product_id: item for item in order.items}
    wanted = {item.product_id for item in data.items}

    for item in list(order.items):
        if item.product_id not in wanted:
            order.items.remove(item)  # removed row; deleted on flush (delete-orphan)

    lines: list[SalesOrderItem] = []
    for item_in in data.items:
        line = existing.get(item_in.product_id)
        if line is None:
            line = SalesOrderItem(
                product_id=item_in.product_id, rate=products[item_in.product_id].price
            )
            order.items.append(line)
        line.quantity = item_in.quantity
        lines.append(line)

    totals = calculate_order_totals(
        [(line.quantity, line.rate) for line in lines], data.discount_percent
    )
    for line, amount in zip(lines, totals.line_amounts, strict=True):
        line.amount = amount

    order.customer_id = data.customer_id
    order.order_date = data.order_date or date.today()
    order.discount_percent = totals.discount_percent
    order.subtotal = totals.subtotal
    order.discount_amount = totals.discount_amount
    order.grand_total = totals.grand_total


# --- Draft create / edit ----------------------------------------------------
def create_order(db: Session, user: User, data: OrderIn) -> SalesOrder:
    with transaction(db):
        _require_active_customer(db, data.customer_id)
        products = _require_active_products(db, data)

        order = SalesOrder(
            order_number=f"TMP-{uuid4().hex}",  # replaced below once the id is known
            status=OrderStatus.DRAFT,
            created_by=user.id,  # owner always comes from the session
        )
        _apply_draft(order, data, products)
        repository.add(db, order)
        # The id is unique, so the number is too. Business dates (order date, order
        # number) use the local calendar date; audit timestamps are stored in UTC.
        order.order_number = f"{ORDER_NUMBER_PREFIX}-{date.today():%Y%m%d}-{order.id:06d}"
    return repository.get(db, order.id)


def update_order(db: Session, user: User, order_id: int, data: OrderIn) -> SalesOrder:
    with transaction(db):
        order = _lock_accessible_order(db, user, order_id)
        _require_status(order, OrderStatus.DRAFT, "edited")
        _require_active_customer(db, data.customer_id)
        products = _require_active_products(db, data)
        _apply_draft(order, data, products)
    return repository.get(db, order.id)


# --- Confirm / cancel -------------------------------------------------------
def confirm_order(db: Session, user: User, order_id: int) -> SalesOrder:
    with transaction(db):
        # 1. Lock the order. A second confirm request waits here, then sees CONFIRMED.
        order = _lock_accessible_order(db, user, order_id)
        _require_status(order, OrderStatus.DRAFT, "confirmed")

        # 2. Lock the customer (shared) and every product (exclusive, ascending id).
        customer = customer_service.find_customer(db, order.customer_id, lock_for_share=True)
        products = product_service.lock_products(db, [item.product_id for item in order.items])

        # 3. Check everything before changing anything.
        if not customer.is_active:
            raise Conflict(
                f"Customer '{customer.name}' is inactive. Reactivate the customer or cancel "
                "this order.",
                code="inactive_customer",
            )
        inactive = [
            products[item.product_id].code
            for item in order.items
            if not products[item.product_id].is_active
        ]
        if inactive:
            raise Conflict(
                f"These products are inactive: {', '.join(inactive)}. "
                "Remove them from the order or reactivate them.",
                code="inactive_products",
                details=[{"product_code": code} for code in inactive],
            )
        shortfalls = [
            {
                "product_id": item.product_id,
                "product_code": products[item.product_id].code,
                "product_name": products[item.product_id].name,
                "requested": item.quantity,
                "available": products[item.product_id].stock_quantity,
            }
            for item in order.items
            if products[item.product_id].stock_quantity < item.quantity
        ]
        if shortfalls:
            # Raising rolls back the transaction: no stock and no status changes at all.
            raise Conflict(
                "Not enough stock to confirm this order. Nothing was changed.",
                code="insufficient_stock",
                details=shortfalls,
            )

        # 4. Deduct stock and record one movement per item, in the same transaction.
        for item in order.items:
            products[item.product_id].stock_quantity -= item.quantity
            inventory_service.record_movement(
                db,
                product_id=item.product_id,
                movement_type=MovementType.ORDER_CONFIRM,
                quantity_change=-item.quantity,
                user_id=user.id,
                order_id=order.id,
                reason=f"Order {order.order_number} confirmed",
            )
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = utc_now()
        order.confirmed_by = user.id
    return repository.get(db, order.id)


def cancel_order(db: Session, user: User, order_id: int) -> SalesOrder:
    with transaction(db):
        order = _lock_accessible_order(db, user, order_id)
        if order.status == OrderStatus.CANCELLED:
            # A repeated cancel must not restore stock a second time.
            raise Conflict(
                f"Order {order.order_number} is already cancelled.",
                code="invalid_order_status",
                details={"status": order.status.value},
            )

        if order.status == OrderStatus.CONFIRMED:
            # Put back exactly what the confirmation deducted.
            products = product_service.lock_products(db, [i.product_id for i in order.items])
            for item in order.items:
                products[item.product_id].stock_quantity += item.quantity
                inventory_service.record_movement(
                    db,
                    product_id=item.product_id,
                    movement_type=MovementType.ORDER_CANCEL,
                    quantity_change=item.quantity,
                    user_id=user.id,
                    order_id=order.id,
                    reason=f"Order {order.order_number} cancelled",
                )

        order.status = OrderStatus.CANCELLED
        order.cancelled_at = utc_now()
        order.cancelled_by = user.id
    return repository.get(db, order.id)
