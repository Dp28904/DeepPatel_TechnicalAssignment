"""End-to-end business journey through the API only, the way the UI uses it.

One continuous story across both roles. Each step checks the status code and the
response body, and stock and reports are checked as they change:

 1. Admin sets up master data: customer, product with opening stock, CSV import.
 2. Admin adjusts stock (with a reason) and deactivates an obsolete product.
 3. A Sales User sees only active data and builds a Draft order.
 4. The Sales User edits the Draft (change quantity, remove a row, add a row).
 5. Confirmation deducts stock and writes movements; the order becomes read-only.
 6. Reports show the sale; another Sales User cannot see the order.
 7. Cancelling restores stock once; reports no longer count the sale.
 8. Referenced master data cannot be deleted; logout ends the session.
"""

from decimal import Decimal

from tests.conftest import TEST_PASSWORD, login_client

CSV = (
    "product_code,product_name,category,price,stock_quantity,status\n"
    "MS-100,Wireless Mouse,Accessories,500,40,Active\n"
    "OLD-1,Serial Cable,Cables,99,0,Inactive\n"
)


def test_complete_sales_and_inventory_journey(app, admin_user, sales_user, other_sales_user):
    admin = login_client(app, admin_user.email)
    sales = login_client(app, sales_user.email)
    other = login_client(app, other_sales_user.email)

    # ---- 1. Master data -------------------------------------------------------------
    r = admin.post(
        "/api/customers",
        json={
            "name": "Acme Traders",
            "email": "Buyer@Acme.com",
            "mobile": "98250 12345",
            "city": "Surat",
        },
    )
    assert r.status_code == 201
    customer = r.json()
    assert (customer["email"], customer["mobile"], customer["is_active"]) == (
        "buyer@acme.com",
        "9825012345",
        True,
    )

    r = admin.post(
        "/api/products",
        json={
            "code": "kb-100",
            "name": "Keyboard",
            "category": "Accessories",
            "price": "1500",
            "stock_quantity": 20,
        },
    )
    assert r.status_code == 201
    keyboard = r.json()
    assert (keyboard["code"], keyboard["price"], keyboard["stock_quantity"]) == (
        "KB-100",
        "1500.00",
        20,
    )

    r = admin.post(
        "/api/imports/products", files={"file": ("products.csv", CSV.encode(), "text/csv")}
    )
    assert r.status_code == 201
    assert (r.json()["imported_count"], r.json()["opening_stock_movements"]) == (2, 1)
    mouse = next(p for p in r.json()["products"] if p["code"] == "MS-100")

    # ---- 2. Stock adjustment and deactivation -----------------------------------------
    r = admin.post(
        f"/api/products/{keyboard['id']}/adjust-stock",
        json={
            "adjustment_type": "DECREASE",
            "quantity": 2,
            "reason": "Two units damaged in storage",
        },
    )
    assert r.status_code == 200
    assert r.json()["product"]["stock_quantity"] == 18
    assert (r.json()["movement"]["movement_type"], r.json()["movement"]["quantity_change"]) == (
        "ADJUSTMENT_OUT",
        -2,
    )

    # ---- 3. Sales User sees active data only and drafts an order --------------------
    r = sales.get("/api/products?status=all&page_size=100")
    codes = {p["code"] for p in r.json()["items"]}
    assert codes == {"KB-100", "MS-100"}  # OLD-1 is inactive: hidden even with status=all

    r = sales.get(f"/api/products/{mouse['id']}")  # what the order form fetches on select
    assert (r.json()["price"], r.json()["stock_quantity"]) == ("500.00", 40)

    r = sales.post(
        "/api/orders",
        json={
            "customer_id": customer["id"],
            "discount_percent": "10",
            "items": [
                {"product_id": keyboard["id"], "quantity": 2},
                {"product_id": mouse["id"], "quantity": 3},
            ],
        },
    )
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "DRAFT"
    assert (order["subtotal"], order["discount_amount"], order["grand_total"]) == (
        "4500.00",
        "450.00",
        "4050.00",
    )
    assert (order["can_edit"], order["can_confirm"], order["can_cancel"]) == (True, True, True)
    assert (
        sales.get(f"/api/products/{keyboard['id']}").json()["stock_quantity"] == 18
    )  # Draft reserves nothing

    # ---- 4. Edit the Draft --------------------------------------------------------------
    # The keyboard's price rises; the line already on the order must keep 1500.
    admin.put(
        f"/api/products/{keyboard['id']}",
        json={"code": "KB-100", "name": "Keyboard", "category": "Accessories", "price": "1800"},
    )
    r = sales.put(
        f"/api/orders/{order['id']}",
        json={
            "customer_id": customer["id"],
            "discount_percent": "5",
            "items": [{"product_id": keyboard["id"], "quantity": 4}],  # mouse row removed
        },
    )
    assert r.status_code == 200
    order = r.json()
    assert [(i["product_code"], i["quantity"], i["rate"], i["amount"]) for i in order["items"]] == [
        ("KB-100", 4, "1500.00", "6000.00")
    ]
    assert (order["subtotal"], order["discount_amount"], order["grand_total"]) == (
        "6000.00",
        "300.00",
        "5700.00",
    )

    # ---- 5. Confirm -----------------------------------------------------------------------
    r = sales.post(f"/api/orders/{order['id']}/confirm")
    assert r.status_code == 200
    order = r.json()
    assert order["status"] == "CONFIRMED" and order["confirmed_at"]
    assert (order["can_edit"], order["can_confirm"], order["can_cancel"]) == (False, False, True)
    assert sales.get(f"/api/products/{keyboard['id']}").json()["stock_quantity"] == 14

    r = sales.post(f"/api/orders/{order['id']}/confirm")  # double click / retry
    assert r.status_code == 409
    r = sales.put(
        f"/api/orders/{order['id']}",
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": keyboard["id"], "quantity": 1}],
        },
    )
    assert r.status_code == 409  # read-only once confirmed
    assert sales.get(f"/api/products/{keyboard['id']}").json()["stock_quantity"] == 14

    # ---- 6. Reports and ownership -------------------------------------------------------
    r = admin.get("/api/reports/customer-sales")
    acme = next(row for row in r.json()["rows"] if row["customer_id"] == customer["id"])
    assert (acme["confirmed_orders"], acme["total_sales"]) == (1, "5700.00")

    r = admin.get("/api/reports/product-sales")
    kb_row = next(row for row in r.json()["rows"] if row["code"] == "KB-100")
    assert (kb_row["quantity_sold"], kb_row["gross_value"]) == (4, "6000.00")

    r = admin.get(f"/api/reports/stock-movements?product_id={keyboard['id']}")
    assert [(m["movement_type"], m["quantity_change"]) for m in r.json()["items"]] == [
        ("ORDER_CONFIRM", -4),
        ("ADJUSTMENT_OUT", -2),
        ("OPENING", 20),
    ]

    r = admin.get("/api/reports/low-stock?threshold=15")
    assert [row["code"] for row in r.json()["rows"]] == ["KB-100"]

    assert other.get(f"/api/orders/{order['id']}").status_code == 404
    assert other.post(f"/api/orders/{order['id']}/cancel").status_code == 404
    assert other.get("/api/orders").json()["total"] == 0

    # ---- 7. Cancel restores stock exactly once -----------------------------------------
    r = sales.post(f"/api/orders/{order['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED" and r.json()["cancelled_at"]
    assert sales.get(f"/api/products/{keyboard['id']}").json()["stock_quantity"] == 18
    assert sales.post(f"/api/orders/{order['id']}/cancel").status_code == 409
    assert sales.get(f"/api/products/{keyboard['id']}").json()["stock_quantity"] == 18

    r = admin.get("/api/reports/customer-sales")
    acme = next(row for row in r.json()["rows"] if row["customer_id"] == customer["id"])
    assert (acme["confirmed_orders"], acme["total_sales"]) == (0, "0.00")
    ledger = admin.get(f"/api/reports/stock-movements?product_id={keyboard['id']}").json()["items"]
    assert sum(m["quantity_change"] for m in ledger) == 18  # ledger always explains stock

    # ---- 8. Safe delete and logout ----------------------------------------------------
    assert admin.delete(f"/api/customers/{customer['id']}").status_code == 409
    assert admin.delete(f"/api/products/{keyboard['id']}").status_code == 409
    # OLD-1 was imported with zero stock and never ordered, so nothing references it.
    old = next(
        p
        for p in admin.get("/api/products?status=inactive").json()["items"]
        if p["code"] == "OLD-1"
    )
    assert admin.delete(f"/api/products/{old['id']}").status_code == 204

    assert sales.post("/api/auth/logout").status_code == 204
    assert sales.get("/api/orders").status_code == 401
    relogin = sales.post(
        "/api/auth/login", json={"email": sales_user.email, "password": TEST_PASSWORD}
    )
    assert relogin.status_code == 200


def test_insufficient_stock_journey_explains_exactly_what_is_missing(
    app, admin_user, sales_user, db_session
):
    admin = login_client(app, admin_user.email)
    sales = login_client(app, sales_user.email)
    customer = admin.post("/api/customers", json={"name": "Shortage Ltd"}).json()
    webcam = admin.post(
        "/api/products",
        json={
            "code": "CAM",
            "name": "Webcam",
            "category": "AV",
            "price": "3200",
            "stock_quantity": 3,
        },
    ).json()
    hub = admin.post(
        "/api/products",
        json={
            "code": "HUB",
            "name": "USB Hub",
            "category": "AV",
            "price": "800",
            "stock_quantity": 10,
        },
    ).json()

    order = sales.post(
        "/api/orders",
        json={
            "customer_id": customer["id"],
            "items": [
                {"product_id": hub["id"], "quantity": 2},
                {"product_id": webcam["id"], "quantity": 5},
            ],
        },
    ).json()
    assert order["items"][1]["available_stock"] == 3  # UI can warn before confirming

    r = sales.post(f"/api/orders/{order['id']}/confirm")
    assert r.status_code == 409
    assert r.json()["error"]["details"] == [
        {
            "product_id": webcam["id"],
            "product_code": "CAM",
            "product_name": "Webcam",
            "requested": 5,
            "available": 3,
        }
    ]
    assert sales.get(f"/api/products/{hub['id']}").json()["stock_quantity"] == 10  # untouched

    # Admin restocks; the same Draft now confirms.
    admin.post(
        f"/api/products/{webcam['id']}/adjust-stock",
        json={"adjustment_type": "INCREASE", "quantity": 2, "reason": "Supplier delivery"},
    )
    r = sales.post(f"/api/orders/{order['id']}/confirm")
    assert r.status_code == 200
    assert sales.get(f"/api/products/{webcam['id']}").json()["stock_quantity"] == 0
    assert Decimal(r.json()["grand_total"]) == Decimal("17600.00")  # 2*800 + 5*3200
