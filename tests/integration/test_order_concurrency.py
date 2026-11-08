"""Concurrent requests against the real MySQL database.

Each test releases several API requests at the same instant (threading.Barrier),
so they genuinely compete for the same rows. Row locks must serialise them so that
stock never goes negative and is never deducted or restored twice.
"""

import threading
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Product, StockMovement
from tests.conftest import login_client
from tests.factories import make_customer, make_product, see_latest

URL = "/api/orders"


def run_together(*calls):
    """Run the callables in parallel threads, released together. Returns their results."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(index, call):
        barrier.wait()
        results[index] = call()

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results


def ledger_total(db, product_id) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(
            StockMovement.product_id == product_id
        )
    )


def create_order(test_client, customer, items):
    response = test_client.post(
        URL,
        json={
            "customer_id": customer.id,
            "items": [{"product_id": p.id, "quantity": q} for p, q in items],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def two_sales_clients(app, sales_user, other_sales_user):
    return login_client(app, sales_user.email), login_client(app, other_sales_user.email)


def test_two_users_confirming_against_limited_stock_never_go_negative(
    db_session, two_sales_clients
):
    """Stock 5; two users each confirm an order for 3. Exactly one can succeed.

    Repeated several times with a fresh product, because a race may not show up
    on every single attempt.
    """
    first_client, second_client = two_sales_clients
    customer = make_customer(db_session)
    db_session.commit()

    for _ in range(5):
        product = make_product(db_session, stock_quantity=5, price=Decimal("10"))
        db_session.commit()
        order_a = create_order(first_client, customer, [(product, 3)])
        order_b = create_order(second_client, customer, [(product, 3)])

        responses = run_together(
            lambda a=order_a: first_client.post(f"{URL}/{a}/confirm"),
            lambda b=order_b: second_client.post(f"{URL}/{b}/confirm"),
        )

        assert sorted(r.status_code for r in responses) == [200, 409]
        loser = next(r for r in responses if r.status_code == 409)
        assert loser.json()["error"]["code"] == "insufficient_stock"
        assert loser.json()["error"]["details"][0]["available"] == 2

        see_latest(db_session)
        assert db_session.get(Product, product.id).stock_quantity == 2
        # The factory adds no opening movement, so the ledger holds only the winner's -3.
        assert ledger_total(db_session, product.id) == -3


def test_same_order_confirmed_twice_at_once_deducts_once(db_session, app, sales_user):
    customer = make_customer(db_session)
    product = make_product(db_session, stock_quantity=10)
    db_session.commit()
    clients = [login_client(app, sales_user.email) for _ in range(3)]
    order_id = create_order(clients[0], customer, [(product, 4)])

    responses = run_together(*[lambda c=c: c.post(f"{URL}/{order_id}/confirm") for c in clients])

    assert sorted(r.status_code for r in responses) == [200, 409, 409]
    see_latest(db_session)
    assert db_session.get(Product, product.id).stock_quantity == 6
    assert ledger_total(db_session, product.id) == -4


def test_confirm_and_cancel_racing_leave_consistent_stock(db_session, app, sales_user):
    """Whichever wins, the final stock must match the final status."""
    customer = make_customer(db_session)
    product = make_product(db_session, stock_quantity=10)
    db_session.commit()
    confirmer, canceller = login_client(app, sales_user.email), login_client(app, sales_user.email)
    order_id = create_order(confirmer, customer, [(product, 4)])

    run_together(
        lambda: confirmer.post(f"{URL}/{order_id}/confirm"),
        lambda: canceller.post(f"{URL}/{order_id}/cancel"),
    )

    final = confirmer.get(f"{URL}/{order_id}").json()["status"]
    assert final == "CANCELLED"  # cancel either ran first, or ran after confirm and restored
    see_latest(db_session)
    assert db_session.get(Product, product.id).stock_quantity == 10
    assert ledger_total(db_session, product.id) == 0


def test_orders_locking_the_same_products_in_different_order_do_not_deadlock(
    db_session, two_sales_clients
):
    """Order A lists (P1, P2) and order B lists (P2, P1). Locks are always taken in
    ascending product id, so the two confirmations never deadlock."""
    first_client, second_client = two_sales_clients
    customer = make_customer(db_session)
    p1 = make_product(db_session, stock_quantity=100)
    p2 = make_product(db_session, stock_quantity=100)
    db_session.commit()

    for _ in range(5):
        order_a = create_order(first_client, customer, [(p1, 1), (p2, 1)])
        order_b = create_order(second_client, customer, [(p2, 1), (p1, 1)])
        responses = run_together(
            lambda a=order_a: first_client.post(f"{URL}/{a}/confirm"),
            lambda b=order_b: second_client.post(f"{URL}/{b}/confirm"),
        )
        assert [r.status_code for r in responses] == [200, 200]

    see_latest(db_session)
    assert db_session.get(Product, p1.id).stock_quantity == 90
    assert db_session.get(Product, p2.id).stock_quantity == 90


def test_admin_adjustment_racing_a_confirmation_never_goes_negative(
    db_session, app, admin_user, sales_user
):
    """Stock 5: an admin removes 4 while a sales user confirms an order for 3."""
    customer = make_customer(db_session)
    product = make_product(db_session, stock_quantity=5)
    db_session.commit()
    admin, seller = login_client(app, admin_user.email), login_client(app, sales_user.email)
    order_id = create_order(seller, customer, [(product, 3)])

    responses = run_together(
        lambda: seller.post(f"{URL}/{order_id}/confirm"),
        lambda: admin.post(
            f"/api/products/{product.id}/adjust-stock",
            json={"adjustment_type": "DECREASE", "quantity": 4, "reason": "Damaged"},
        ),
    )

    assert sorted(r.status_code for r in responses) == [200, 409]
    see_latest(db_session)
    remaining = db_session.get(Product, product.id).stock_quantity
    assert remaining in (1, 2)  # 5-4 if the adjustment won, 5-3 if the order won
    assert remaining >= 0
