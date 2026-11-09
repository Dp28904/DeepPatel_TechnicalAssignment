# REST API

Every endpoint is under `/api`, takes and returns JSON (the CSV import takes a file upload), and
uses the same validation and permission rules as the web pages, because the pages call this API.

The request and response bodies below were **captured from the running application** against
the test database, using the sample accounts. Timestamps and ids will differ on your machine.

> Interactive documentation, generated from the code, is also available while the app runs:
> **http://localhost:8000/docs** (Swagger UI) and **/openapi.json**.

## Contents

- [Conventions](#conventions)
- [Trying it with curl](#trying-it-with-curl)
- [Auth](#auth)
- [Products](#products)
- [Customers](#customers)
- [Orders](#orders) (the five endpoints required by Part 8 are marked ★)
- [Reports](#reports)
- [CSV import](#csv-import)
- [Users](#users)
- [Dashboard and health](#dashboard-and-health)
- [Endpoint summary](#endpoint-summary)

## Conventions

**Authentication.** Log in with `POST /api/auth/login`. The response sets a signed, httpOnly
session cookie (`sales_session`, 8 hours) that must be sent with every later request.

**CSRF header.** Every `POST`, `PUT`, `PATCH` and `DELETE` must include
`X-Requested-With: fetch`. Without it the request is refused with `403 csrf_check_failed`.
Another website cannot add this header to a cross-site request, which blocks request forgery.

**Money** is always a string with exactly two decimals, such as `"1500.00"`. Send it as a string
or a JSON number written plainly (`1500`, `"1500.50"`); forms such as `1e3`, `1_000` and
`Infinity` are rejected.

**Pagination.** List endpoints accept `page` (from 1, at most 100,000) and `page_size`
(1–100, default 20) and return:

```json
{ "items": [ ... ], "total": 42, "page": 1, "page_size": 20, "pages": 3 }
```

**Errors** always have the same shape, and never include tracebacks, SQL or password hashes:

```json
{ "error": { "code": "machine_readable_code", "message": "A plain sentence.", "details": ... } }
```

| Status | Meaning | Example `code` |
|---|---|---|
| 401 | Not logged in, or wrong credentials | `unauthenticated`, `invalid_credentials` |
| 403 | Logged in, but the role is not allowed; or the CSRF header is missing | `forbidden`, `csrf_check_failed` |
| 404 | Record does not exist, **or belongs to another Sales User** | `not_found` |
| 409 | The request conflicts with the current state | `insufficient_stock`, `invalid_order_status`, `duplicate_product_code`, `customer_in_use`, `lock_conflict` |
| 413 | Uploaded file too large | `payload_too_large` |
| 422 | Invalid input; `details` lists `{field, message}` per problem | `validation_error`, `csv_invalid` |
| 500 | Unexpected error; `details.request_id` matches the server log | `internal_error` |

## Trying it with curl

```bash
# Log in and keep the session cookie in cookies.txt
curl -c cookies.txt -H 'Content-Type: application/json' -H 'X-Requested-With: fetch' \
     -d '{"email":"admin@example.com","password":"<SEED_ADMIN_PASSWORD>"}' \
     http://localhost:8000/api/auth/login

# Read (no CSRF header needed for GET)
curl -b cookies.txt 'http://localhost:8000/api/products?search=key'

# Write (CSRF header required)
curl -b cookies.txt -H 'Content-Type: application/json' -H 'X-Requested-With: fetch' \
     -d '{"customer_id":1,"discount_percent":"10","items":[{"product_id":1,"quantity":2}]}' \
     http://localhost:8000/api/orders
```

---

## Auth

### `POST /api/auth/login` — anyone

```json
{ "email": "admin@example.com", "password": "********" }
```

`200 OK` (and the session cookie is set)

```json
{ "id": 1, "name": "Asha Admin", "email": "admin@example.com", "role": "ADMIN", "is_active": true }
```

Wrong password, unknown email and inactive account all give the same answer, so the response
does not reveal which emails exist. `401`:

```json
{ "error": { "code": "invalid_credentials", "message": "Invalid email or password.", "details": null } }
```

### `POST /api/auth/logout` — logged in

`204 No Content`. The session is cleared.

### `GET /api/auth/me` — logged in

`200 OK`

```json
{ "id": 2, "name": "Ravi Sales", "email": "sales1@example.com", "role": "SALES", "is_active": true }
```

Without a session, this and every other protected endpoint returns `401`:

```json
{ "error": { "code": "unauthenticated", "message": "Please log in to continue.", "details": null } }
```

### `POST /api/auth/password` — Admin changing their own password

```json
{ "current_password": "old-password", "new_password": "a-new-password" }
```

`204 No Content`. Every other session of this user is signed out; the current one stays signed
in. A Sales User gets `403 ask_an_admin`; a wrong current password gives `422`.

---

## Products

### ★ `GET /api/products` — logged in

Lists **active** products by default, with search and pagination.

| Query | Meaning |
|---|---|
| `search` | Matches product code or name |
| `category` | Exact category |
| `status` | `active` (default), `inactive` or `all`. **Sales Users always get active products only**, whatever they send |
| `page`, `page_size` | Pagination |

`GET /api/products?search=key&page=1&page_size=20` → `200 OK`

```json
{
  "items": [
    {
      "id": 1, "code": "PRD-001", "name": "Keyboard", "category": "Accessories",
      "price": "1500.00", "stock_quantity": 20, "is_active": true,
      "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46"
    }
  ],
  "total": 1, "page": 1, "page_size": 20, "pages": 1
}
```

### `GET /api/products/categories` — logged in

`200 OK` → a sorted list of category names, for example `["Accessories", "Cables", "Displays"]`

### `GET /api/products/{id}` — logged in

`200 OK` with one product. An inactive product is `404` for a Sales User.

### `POST /api/products` — Admin

```json
{ "code": "prd-001", "name": "Keyboard", "category": "Accessories", "price": "1500", "stock_quantity": 20 }
```

`201 Created`. The code is stored upper-case, the price with two decimals, and the opening
stock is recorded as an `OPENING` stock movement.

```json
{
  "id": 1, "code": "PRD-001", "name": "Keyboard", "category": "Accessories",
  "price": "1500.00", "stock_quantity": 20, "is_active": true,
  "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46"
}
```

Rules: code 1–30 letters, digits or dashes and unique; price 0–9,999,999.99 with at most two
decimals; stock a whole number 0–1,000,000,000; `is_active` defaults to `true`.

Duplicate code → `409`:

```json
{
  "error": {
    "code": "duplicate_product_code",
    "message": "Product code 'PRD-001' already exists.",
    "details": [ { "field": "code", "message": "Product code 'PRD-001' already exists." } ]
  }
}
```

A Sales User calling any write endpoint gets `403`:

```json
{ "error": { "code": "forbidden", "message": "Only Admin users can perform this action.", "details": null } }
```

### `PUT /api/products/{id}` — Admin

Same body as create, **without** `stock_quantity`. Sending it gives `422` ("Stock cannot be
edited directly. Use 'Adjust stock' instead."), so every stock change goes through the ledger.

### `DELETE /api/products/{id}` — Admin

`204 No Content`, or `409 product_in_use` if any order item or stock movement references the
product. Deactivate it instead (`PUT` with `"is_active": false`).

### `POST /api/products/{id}/adjust-stock` — Admin

```json
{ "adjustment_type": "INCREASE", "quantity": 5, "reason": "Supplier delivery" }
```

`200 OK` — the updated product and the movement that was recorded:

```json
{
  "product": {
    "id": 2, "code": "PRD-002", "name": "Mouse", "category": "Accessories",
    "price": "500.00", "stock_quantity": 7, "is_active": true,
    "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46"
  },
  "movement": {
    "id": 3, "product_id": 2, "product_code": "PRD-002", "product_name": "Mouse",
    "movement_type": "ADJUSTMENT_IN", "quantity_change": 5,
    "order_id": null, "order_number": null, "reason": "Supplier delivery",
    "created_by": 1, "created_by_name": "Asha Admin", "created_at": "2026-11-09T08:00:46"
  }
}
```

`adjustment_type` is `INCREASE` or `DECREASE`; `quantity` is a whole number ≥ 1; `reason` is
required (3–255 characters). A decrease below zero → `409`:

```json
{
  "error": {
    "code": "insufficient_stock",
    "message": "Cannot remove 100 unit(s) of 'PRD-002': only 7 in stock. Stock cannot go below zero.",
    "details": [ { "field": "quantity", "message": "At most 7." } ]
  }
}
```

---

## Customers

### `GET /api/customers` — logged in

| Query | Meaning |
|---|---|
| `search` | Matches name, email or mobile |
| `status` | `active` (default), `inactive` or `all`. Sales Users always get active customers only |
| `page`, `page_size` | Pagination |

### `GET /api/customers/{id}` — logged in

An inactive customer is `404` for a Sales User.

### `POST /api/customers` — Admin

```json
{ "name": "Shree Ganesh Traders", "email": "Accounts@ShreeGanesh.example.com",
  "mobile": "+91 98240-12345", "city": "Ahmedabad" }
```

`201 Created`. The email is lower-cased; spaces, dashes and brackets are removed from the mobile
number, which must then be 10–15 digits with an optional leading `+`. Email, mobile and city
are optional; an empty string counts as "not provided".

```json
{
  "id": 1, "name": "Shree Ganesh Traders", "email": "accounts@shreeganesh.example.com",
  "mobile": "+919824012345", "city": "Ahmedabad", "is_active": true,
  "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46"
}
```

### `PUT /api/customers/{id}` — Admin

Same body as create.

### `DELETE /api/customers/{id}` — Admin

`204 No Content`, or `409` when any order references the customer:

```json
{
  "error": {
    "code": "customer_in_use",
    "message": "'Shree Ganesh Traders' is used by 2 order(s) and cannot be deleted. Deactivate the customer instead.",
    "details": null
  }
}
```

---

## Orders

Status flow: `DRAFT → CONFIRMED → CANCELLED`, or `DRAFT → CANCELLED`. Only Drafts can be
edited. Confirming deducts stock; cancelling a Confirmed order restores it.

**Ownership.** Admins see and act on every order. A Sales User sees and acts on **only the
orders they created**; anyone else's order returns `404`, so changing the id in the URL reveals
nothing.

**What the client may send.** Only the customer, order date, discount percentage and
`(product_id, quantity)` pairs. Rates, amounts, totals, status and owner are set by the server;
sending them is rejected (see below).

### ★ `POST /api/orders` — logged in (creates a Draft)

```json
{
  "customer_id": 1,
  "discount_percent": "10",
  "items": [ { "product_id": 1, "quantity": 2 }, { "product_id": 2, "quantity": 3 } ]
}
```

`order_date` is optional (`YYYY-MM-DD`, defaults to today, not in the future, not before
2000-01-01). `discount_percent` is optional (0–20, at most two decimals, default 0).

`201 Created` — the assignment's worked example, calculated by the server:

```json
{
  "id": 1,
  "order_number": "SO-20261109-000001",
  "customer": { "id": 1, "name": "Shree Ganesh Traders" },
  "order_date": "2026-11-09",
  "status": "DRAFT",
  "discount_percent": "10.00",
  "subtotal": "4500.00",
  "discount_amount": "450.00",
  "grand_total": "4050.00",
  "items": [
    { "id": 1, "product_id": 1, "product_code": "PRD-001", "product_name": "Keyboard",
      "quantity": 2, "rate": "1500.00", "amount": "3000.00", "available_stock": 20 },
    { "id": 2, "product_id": 2, "product_code": "PRD-002", "product_name": "Mouse",
      "quantity": 3, "rate": "500.00", "amount": "1500.00", "available_stock": 7 }
  ],
  "created_by": { "id": 2, "name": "Ravi Sales" },
  "created_at": "2026-11-09T08:00:46",
  "updated_at": "2026-11-09T08:00:46",
  "confirmed_at": null,
  "cancelled_at": null,
  "can_edit": true,
  "can_confirm": true,
  "can_cancel": true
}
```

`can_edit`, `can_confirm` and `can_cancel` tell the UI which buttons to show; the server checks
again on every request.

Invalid input → `422`, one plain message per problem:

```json
{
  "customer_id": 1, "discount_percent": "25",
  "items": [ { "product_id": 1, "quantity": 0 } ]
}
```

```json
{
  "error": {
    "code": "validation_error",
    "message": "2 things need fixing: Discount % must be 20 or less. Item 1 quantity must be 1 or more.",
    "details": [
      { "field": "discount_percent", "message": "Discount % must be 20 or less." },
      { "field": "items.0.quantity", "message": "Item 1 quantity must be 1 or more." }
    ]
  }
}
```

Trying to supply a rate or total → `422`, the values are never used:

```json
{
  "customer_id": 1, "discount_percent": "10",
  "items": [ { "product_id": 1, "quantity": 2, "rate": "1" } ],
  "grand_total": "1.00"
}
```

```json
{
  "error": {
    "code": "validation_error",
    "message": "2 things need fixing: Item 1 rate cannot be sent here; it is not an accepted field (the system sets it itself). Grand total cannot be sent here; it is not an accepted field (the system sets it itself).",
    "details": [
      { "field": "items.0.rate", "message": "Item 1 rate cannot be sent here; it is not an accepted field (the system sets it itself)." },
      { "field": "grand_total", "message": "Grand total cannot be sent here; it is not an accepted field (the system sets it itself)." }
    ]
  }
}
```

Other `422` cases: no items, the same product twice, an inactive or missing customer or
product, a quantity that is not a whole number from 1 to 1,000,000.

### ★ `GET /api/orders/{id}` — logged in

`200 OK` with the same body as above. Another Sales User asking for the same order → `404`:

```json
{ "error": { "code": "not_found", "message": "Order 1 was not found.", "details": null } }
```

### `GET /api/orders` — logged in

| Query | Meaning |
|---|---|
| `status` | `DRAFT`, `CONFIRMED` or `CANCELLED` |
| `customer_id` | One customer |
| `search` | Order number or customer name |
| `from`, `to` | Order date range, inclusive (`from` must not be after `to`) |
| `page`, `page_size` | Pagination |

`GET /api/orders?status=DRAFT` → `200 OK`

```json
{
  "items": [
    { "id": 1, "order_number": "SO-20261109-000001", "customer_name": "Shree Ganesh Traders",
      "order_date": "2026-11-09", "status": "DRAFT", "item_count": 2,
      "grand_total": "4050.00", "created_by_name": "Ravi Sales" }
  ],
  "total": 1, "page": 1, "page_size": 20, "pages": 1
}
```

### `PUT /api/orders/{id}` — owner or Admin, Draft only

Same body as create; it replaces the customer, date, discount and items. Lines that stay keep
their stored rate; new lines take the product's current price. Editing a Confirmed or Cancelled
order → `409`:

```json
{
  "error": {
    "code": "invalid_order_status",
    "message": "Order SO-20261109-000001 is confirmed; only draft orders can be edited.",
    "details": { "status": "CONFIRMED" }
  }
}
```

### ★ `POST /api/orders/{id}/confirm` — owner or Admin

No body. `200 OK` — status `CONFIRMED`, stock deducted (keyboard 20 → 18, mouse 7 → 4):

```json
{
  "id": 1, "order_number": "SO-20261109-000001", "status": "CONFIRMED",
  "subtotal": "4500.00", "discount_amount": "450.00", "grand_total": "4050.00",
  "items": [
    { "product_code": "PRD-001", "quantity": 2, "rate": "1500.00", "amount": "3000.00", "available_stock": 18 },
    { "product_code": "PRD-002", "quantity": 3, "rate": "500.00", "amount": "1500.00", "available_stock": 4 }
  ],
  "confirmed_at": "2026-11-09T08:00:46",
  "can_edit": false, "can_confirm": false, "can_cancel": true
}
```

(Response shortened; the full body has the same fields as `GET /api/orders/{id}`.)

Not enough stock for **any** item → `409`, and **nothing** changes (no stock, no status, no
movements). Every short item is listed:

```json
{
  "error": {
    "code": "insufficient_stock",
    "message": "Not enough stock to confirm this order. Nothing was changed.",
    "details": [
      { "product_id": 2, "product_code": "PRD-002", "product_name": "Mouse", "requested": 50, "available": 7 }
    ]
  }
}
```

Confirming again → `409`, and stock is not deducted a second time:

```json
{
  "error": {
    "code": "invalid_order_status",
    "message": "Order SO-20261109-000001 is confirmed; only draft orders can be confirmed.",
    "details": { "status": "CONFIRMED" }
  }
}
```

Other `409` cases: `inactive_customer`, `inactive_products`, and `lock_conflict` (the database
reported a deadlock or lock timeout; nothing was saved and the request is safe to retry).

### ★ `POST /api/orders/{id}/cancel` — owner or Admin

No body. A Draft is cancelled with no stock change. A Confirmed order is cancelled and its stock
is restored (keyboard 18 → 20, mouse 4 → 7), with an `ORDER_CANCEL` movement per item.
`200 OK`:

```json
{
  "id": 1, "order_number": "SO-20261109-000001", "status": "CANCELLED",
  "items": [
    { "product_code": "PRD-001", "quantity": 2, "available_stock": 20 },
    { "product_code": "PRD-002", "quantity": 3, "available_stock": 7 }
  ],
  "confirmed_at": "2026-11-09T08:00:46", "cancelled_at": "2026-11-09T08:00:46",
  "can_edit": false, "can_confirm": false, "can_cancel": false
}
```

(Response shortened.) Cancelling again → `409`, and stock is not restored a second time:

```json
{
  "error": {
    "code": "invalid_order_status",
    "message": "Order SO-20261109-000001 is already cancelled.",
    "details": { "status": "CANCELLED" }
  }
}
```

---

## Reports

Admin only (a Sales User gets `403`). Sales figures count **Confirmed orders only**. `from` and
`to` are optional, inclusive order dates.

### `GET /api/reports/customer-sales?from=&to=`

Every customer is listed, including those with no Confirmed orders in the range (zero totals).
`total_sales` is after the order discount, and each order is counted once however many items it
has.

`GET /api/reports/customer-sales?from=2026-01-01&to=2026-12-31` → `200 OK`

```json
{
  "filters": { "date_from": "2026-01-01", "date_to": "2026-12-31" },
  "rows": [
    { "customer_id": 1, "customer_name": "Shree Ganesh Traders", "city": "Ahmedabad",
      "is_active": true, "confirmed_orders": 1, "total_sales": "4050.00" }
  ],
  "totals": { "customers": 1, "customers_with_sales": 1, "confirmed_orders": 1, "total_sales": "4050.00" }
}
```

### `GET /api/reports/product-sales?from=&to=`

`gross_value` is the sum of item amounts, before the order discount.

```json
{
  "filters": { "date_from": null, "date_to": null },
  "rows": [
    { "product_id": 2, "code": "PRD-002", "name": "Mouse", "category": "Accessories",
      "is_active": true, "quantity_sold": 3, "order_count": 1, "gross_value": "1500.00" },
    { "product_id": 1, "code": "PRD-001", "name": "Keyboard", "category": "Accessories",
      "is_active": true, "quantity_sold": 2, "order_count": 1, "gross_value": "3000.00" }
  ],
  "totals": { "quantity_sold": 5, "gross_value": "4500.00" }
}
```

### `GET /api/reports/low-stock?threshold=10&include_inactive=false`

Products with stock **strictly below** the threshold (required, ≥ 0).

```json
{
  "threshold": 10,
  "include_inactive": false,
  "rows": [
    { "product_id": 2, "code": "PRD-002", "name": "Mouse", "category": "Accessories",
      "price": "500.00", "stock_quantity": 4, "is_active": true, "below_threshold_by": 6 }
  ]
}
```

### `GET /api/reports/stock-movements`

Query: `product_id`, `movement_type` (`OPENING`, `ADJUSTMENT_IN`, `ADJUSTMENT_OUT`,
`ORDER_CONFIRM`, `ORDER_CANCEL`), `from`, `to`, `page`, `page_size`. Newest first.

`GET /api/reports/stock-movements?product_id=1&page_size=5` → `200 OK`

```json
{
  "items": [
    { "id": 4, "product_id": 1, "product_code": "PRD-001", "product_name": "Keyboard",
      "movement_type": "ORDER_CONFIRM", "quantity_change": -2,
      "order_id": 1, "order_number": "SO-20261109-000001",
      "reason": "Order SO-20261109-000001 confirmed",
      "created_by": 2, "created_by_name": "Ravi Sales", "created_at": "2026-11-09T08:00:46" },
    { "id": 1, "product_id": 1, "product_code": "PRD-001", "product_name": "Keyboard",
      "movement_type": "OPENING", "quantity_change": 20,
      "order_id": null, "order_number": null, "reason": "Opening stock",
      "created_by": 1, "created_by_name": "Asha Admin", "created_at": "2026-11-09T08:00:46" }
  ],
  "total": 2, "page": 1, "page_size": 5, "pages": 1
}
```

---

## CSV import

### `POST /api/imports/products` — Admin

`multipart/form-data` with one field, `file` (a `.csv` file, at most 1 MB and 5,000 rows):

```bash
curl -b cookies.txt -H 'X-Requested-With: fetch' \
     -F 'file=@samples/products_valid.csv' http://localhost:8000/api/imports/products
```

```csv
product_code,product_name,category,price,stock_quantity,status
PRD-101,Monitor,Displays,11500,12,Active
PRD-102,HDMI Cable,Cables,349,0,Active
```

`201 Created`

```json
{
  "imported_count": 2,
  "opening_stock_movements": 1,
  "products": [
    { "id": 3, "code": "PRD-101", "name": "Monitor", "category": "Displays", "price": "11500.00",
      "stock_quantity": 12, "is_active": true, "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46" },
    { "id": 4, "code": "PRD-102", "name": "HDMI Cable", "category": "Cables", "price": "349.00",
      "stock_quantity": 0, "is_active": true, "created_at": "2026-11-09T08:00:46", "updated_at": "2026-11-09T08:00:46" }
  ]
}
```

If **any** row is invalid, **nothing** is imported. `422` lists every problem with its file row
number (the header is row 1):

```csv
product_code,product_name,category,price,stock_quantity,status
PRD-201,Good Row,Cables,100,1,Active
PRD-202,,Cables,-5,2.5,Pending
PRD-001,Existing Code,Cables,100,1,Active
```

```json
{
  "error": {
    "code": "csv_invalid",
    "message": "Nothing was imported: we found 5 problem(s) in the file. Fix the rows listed below and upload the file again.",
    "details": [
      { "row": 3, "field": "product_name", "message": "Product name is required." },
      { "row": 3, "field": "price", "message": "Price cannot be negative." },
      { "row": 3, "field": "stock_quantity", "message": "Stock quantity must be a whole number, got '2.5'." },
      { "row": 3, "field": "status", "message": "Status must be 'Active' or 'Inactive', got 'Pending'." },
      { "row": 4, "field": "product_code", "message": "Product code 'PRD-001' already exists." }
    ]
  }
}
```

Other cases: not a `.csv` file → `422`; larger than 1 MB → `413`; another request creates one
of the codes during the import → `409 duplicate_product_code`, with nothing saved.

---

## Users

Admin only.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/users` | – | Every account, with `can_edit_profile` and `can_reset_password` flags |
| POST | `/api/users` | `{"name", "email", "password", "role": "ADMIN" \| "SALES"}` | `201`; password at least 8 characters; `409 email_taken` |
| GET | `/api/users/{id}` | – | |
| PUT | `/api/users/{id}` | `{"name", "email"}` | A Sales User or yourself; another Admin → `403` |
| POST | `/api/users/{id}/password` | `{"new_password"}` | Sales Users only; `204`; signs that user out everywhere |

## Dashboard and health

`GET /api/dashboard?from=&to=` (logged in): headline numbers, monthly trend, orders by status,
top customers, products and categories, low stock and recent orders. Admins see every order,
Sales Users only their own (`"scope": "own"`).

`GET /api/health` (anyone): `200 {"status": "ok", "database": "ok"}`, or `503` when the database
cannot be reached. `HEAD` is also supported.

## Endpoint summary

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/login` | Anyone |
| POST | `/api/auth/logout` | Logged in |
| GET | `/api/auth/me` | Logged in |
| POST | `/api/auth/password` | Admin (own password) |
| GET | `/api/products` ★ | Logged in |
| GET | `/api/products/categories` | Logged in |
| GET | `/api/products/{id}` | Logged in |
| POST | `/api/products` | Admin |
| PUT / DELETE | `/api/products/{id}` | Admin |
| POST | `/api/products/{id}/adjust-stock` | Admin |
| GET | `/api/customers`, `/api/customers/{id}` | Logged in |
| POST | `/api/customers` | Admin |
| PUT / DELETE | `/api/customers/{id}` | Admin |
| GET | `/api/orders` | Logged in (own orders for Sales Users) |
| POST | `/api/orders` ★ | Logged in |
| GET | `/api/orders/{id}` ★ | Owner or Admin |
| PUT | `/api/orders/{id}` | Owner or Admin |
| POST | `/api/orders/{id}/confirm` ★ | Owner or Admin |
| POST | `/api/orders/{id}/cancel` ★ | Owner or Admin |
| GET | `/api/reports/customer-sales`, `/product-sales`, `/low-stock`, `/stock-movements` | Admin |
| POST | `/api/imports/products` | Admin |
| GET / POST | `/api/users` | Admin |
| GET / PUT | `/api/users/{id}` | Admin |
| POST | `/api/users/{id}/password` | Admin |
| GET | `/api/dashboard` | Logged in |
| GET / HEAD | `/api/health` | Anyone |
