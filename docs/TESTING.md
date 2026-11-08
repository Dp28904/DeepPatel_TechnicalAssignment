# Testing

**516 automated tests** cover the application and the debugging exercise.

| Check | Result |
|---|---|
| Tests | all pass, 0 skipped |
| Line coverage (`app` + `debugging`) | 98% |
| Lint and format (ruff) | clean |
| Exploratory probe: 351 hostile requests | 0 server errors, run both in-process and over HTTP against the Docker image |

## How to run

The tests use a real MySQL database, `sales_test`, because row locks, CHECK constraints and transactions are part of what is being tested. The MySQL container creates this database on first start.

```bash
docker compose up -d mysql               # MySQL 8.4 with sales_db and sales_test
pytest                                   # everything (about a minute)
pytest --cov=app --cov=debugging         # with coverage
pytest debugging                         # only the debugging exercise (no database needed)
pytest tests/unit                        # only the pure unit tests (no database needed)
pytest -k required                       # only the 9 scenarios required by Part 12
```

Safety: the suite refuses to run unless the database name ends in `_test`. The schema is rebuilt from the Alembic migrations at the start of each run: a full downgrade, then an upgrade, which also tests the migration itself. Every table is emptied after each test.

## Required scenarios (Part 12)

| # | Scenario | Expected | Test |
|---|---|---|---|
| 1 | Order with multiple items and discount | Correct subtotal and grand total | `tests/unit/test_calculations.py::test_assignment_example_multi_item_order_with_discount`, `tests/integration/test_orders_api.py::test_required_1_multi_item_order_with_discount_has_correct_totals` |
| 2 | Zero or negative quantity | Rejected | `test_required_2_zero_or_negative_quantity_is_rejected` |
| 3 | Discount outside 0–20% | Rejected | `test_required_3_discount_outside_0_to_20_is_rejected` |
| 4 | Confirmation with sufficient stock | Confirmed, stock deducted | `test_required_4_confirm_with_sufficient_stock_deducts_stock` |
| 5 | One insufficient-stock item | No stock or status change | `test_required_5_confirm_with_one_insufficient_item_changes_nothing` (also checks that no movements were written) |
| 6 | Repeated confirmation | No additional deduction | `test_required_6_repeated_confirmation_does_not_deduct_again` |
| 7 | Cancel a confirmed order | Stock restored once | `test_required_7_cancelling_confirmed_order_restores_stock_once` |
| 8 | Sales User opens another user's order | Access denied (404) | `test_required_8_sales_user_cannot_access_another_users_order` |
| 9 | CSV with an invalid row | Nothing imported | `tests/integration/test_csv_import.py::test_required_9_csv_with_an_invalid_row_imports_nothing` |

## Test suites

| File | Tests | What it proves |
|---|---|---|
| `tests/integration/test_api_contract.py` | 98 | Rules for **every** endpoint: 401 / 403 / CSRF, malformed bodies, bad ids, paging and dates, exact response fields, no leaks, 500 and lock-conflict handling, regression tests |
| `tests/integration/test_e2e_flow.py` | 2 | Full business journeys across both roles, checking every step (see below) |
| `tests/integration/test_orders_api.py` | 50 | Draft create and edit, rate snapshot, confirm and cancel, ownership, list filters |
| `tests/integration/test_order_concurrency.py` | 5 | Simultaneous requests: limited stock, triple confirm, confirm vs cancel, deadlock-free locking, adjustment vs confirm |
| `tests/integration/test_products_api.py` | 38 | Product CRUD, unique codes, visibility, safe delete, stock adjustment, ledger consistency, concurrent decreases |
| `tests/integration/test_customers_api.py` | 28 | Customer CRUD, search and filter, role visibility, safe delete |
| `tests/integration/test_dashboard.py` | 9 | Dashboard: role scoping (all vs own orders), headline numbers, zero-filled monthly trend, category/product/customer/team rankings, low stock, date range |
| `tests/integration/test_reports.py` | 25 | All 4 reports and all 5 queries in `sql/queries.sql`, checked against a dataset with hand-calculated results |
| `tests/integration/test_csv_import.py` | 15 | All-or-nothing import, row errors, opening stock, the sample files, limits, permissions |
| `tests/integration/test_friendly_errors.py` | 18 | Every validation error is a plain sentence naming the field ("Name is required.", "Item 2 quantity must be 1 or more."), for bodies, query parameters, dates and invalid JSON |
| `tests/integration/test_user_management.py` | 29 | Admin adds Sales Users and Admins; edits Sales Users (name, login email, password); Admin edits self and changes own password with the current one; no editing other Admins; Sales Users cannot change passwords; a password change signs out other sessions; passwords are never trimmed |
| `tests/integration/test_auth.py` | 28 | Login and logout, sessions, inactive users, CSRF, role checks, page redirects |
| `tests/integration/test_schema.py` | 26 | Database constraints: CHECK, UNIQUE, FOREIGN KEY RESTRICT/CASCADE, DECIMAL storage |
| `tests/integration/test_users_cli_seed.py` | 7 | The account CLI and the seed script (idempotent, `--reset`) |
| `tests/integration/test_master_data_pages.py`, `test_order_pages.py` | 20 | HTML pages render for the right roles; login redirects |
| `tests/unit/test_calculations.py` | 20 | Order maths: worked example, half-up rounding, limits |
| `tests/unit/test_csv_validator.py` | 31 | CSV parsing: headers, BOM, quoting, every row rule, duplicates |
| `tests/unit/test_money.py`, `test_security.py`, `test_app_basics.py` | 29 | Rounding, password hashing, safe redirects, JSON 404/405, request ids |
| `debugging/test_calculate_total.py` | 36 | Part 11: the bug reproduced, the fix, and every edge case |

## End-to-end journey

`test_complete_sales_and_inventory_journey` drives the API the way the UI does, checking status codes and bodies at every step:

1. **Admin** creates a customer, whose email and mobile are normalised. Admin creates a product with opening stock 20 (code upper-cased, price `"1500.00"`) and imports a CSV (2 products, 1 opening movement).
2. Admin decreases stock by 2 with a reason. The response shows stock 18 and an `ADJUSTMENT_OUT -2` movement.
3. **Sales User** lists products and sees only active ones, even when asking for `status=all`. They fetch a product's price and stock, then create a Draft. The totals are 4500.00 / 450.00 / 4050.00, and stock is unchanged.
4. The keyboard price rises to 1800. The Sales User edits the Draft: changes the quantity, removes a row and changes the discount. The existing line **keeps rate 1500.00**, and the totals are 6000.00 / 300.00 / 5700.00.
5. **Confirm**: status CONFIRMED and stock 18 → 14. Confirming again gives 409. Editing gives 409, because the order is read-only. Stock stays 14.
6. **Reports**: customer sales shows 1 order for 5700.00. Product sales shows quantity 4 and gross 6000.00. Movement history lists `ORDER_CONFIRM -4`, `ADJUSTMENT_OUT -2` and `OPENING +20`. Low stock with a threshold of 15 lists the keyboard. Another Sales User gets **404** for the order and sees 0 orders.
7. **Cancel**: stock goes back to 18. Cancelling again gives 409, and stock stays 18. The sale disappears from the report, and the movement ledger sums to 18.
8. **Safe delete**: the customer and keyboard cannot be deleted (409). The unused inactive product can be (204). **Logout**, then any call gives 401, and logging in again works.

`test_insufficient_stock_journey_explains_exactly_what_is_missing`: a confirmation is refused with `{product_code, requested: 5, available: 3}` and nothing changes. The admin restocks, and the same Draft then confirms.

## Endpoint coverage

| Endpoint | Success | 401 | 403 role | 403 CSRF | 404 | 409 | 422 |
|---|---|---|---|---|---|---|---|
| `POST /api/auth/login` | ✓ | ✓ wrong credentials | – | ✓ | – | – | ✓ |
| `POST /api/auth/logout`, `GET /api/auth/me` | ✓ | ✓ | – | ✓ | – | – | – |
| `GET/POST /api/customers` | ✓ | ✓ | ✓ | ✓ | – | – | ✓ |
| `GET/PUT/DELETE /api/customers/{id}` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ in use | ✓ |
| `GET/POST /api/products`, `GET /api/products/categories` | ✓ | ✓ | ✓ | ✓ | – | ✓ duplicate code | ✓ |
| `GET/PUT/DELETE /api/products/{id}` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ in use | ✓ |
| `POST /api/products/{id}/adjust-stock` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ negative / limit | ✓ |
| `GET/POST /api/orders` | ✓ | ✓ | – | ✓ | – | – | ✓ |
| `GET/PUT /api/orders/{id}` | ✓ | ✓ | – | ✓ | ✓ not owned | ✓ not Draft | ✓ |
| `POST /api/orders/{id}/confirm` and `/cancel` | ✓ | ✓ | – | ✓ | ✓ not owned | ✓ status / stock / lock | – |
| `POST /api/imports/products` | ✓ | ✓ | ✓ | ✓ | – | ✓ race | ✓ (413 too large) |
| `GET /api/reports/*` (4 reports) | ✓ | ✓ | ✓ | – | – | – | ✓ |
| `GET /api/dashboard` | ✓ | ✓ | – (scoped by role) | – | – | – | ✓ |
| `POST /api/auth/password` (own password, Admins) | ✓ | ✓ | ✓ Sales User | ✓ | – | – | ✓ wrong current / too short |
| `GET/PUT /api/users/{id}`, `GET /api/users` | ✓ | ✓ | ✓ (other Admin) | ✓ | ✓ | ✓ email taken | ✓ |
| `POST /api/users/{id}/password` | ✓ | ✓ | ✓ (self / Admin) | ✓ | ✓ | – | ✓ |
| `GET/HEAD /api/health` | ✓ | – | – | – | – | – | – (503 when the database is down) |

## Exploratory testing

A probe script sent **351 hostile or edge-case requests** to all 27 API operations (the dashboard endpoint, added later, is covered by the contract tests). It ran first in-process, then over real HTTP against the Docker image. The inputs covered:

- invalid JSON, arrays, strings, empty bodies, `text/plain` and form-encoded bodies
- ids of `0`, `-1`, `10^20`, `abc` and `1.5`
- page numbers up to `10^20`
- dates such as `2026-13-01`, `2026-02-30` and `9999-12-31`
- SQL-injection and `<script>` strings, NUL bytes, emoji and 10,000-character strings
- money written as `1e2`, `1_000`, `Infinity`, `NaN` or `0x10`
- binary, unterminated, semicolon-separated and oversized CSV files
- forged session cookies, missing or wrong CSRF headers, and unsupported methods

Every probe was checked for: no 5xx, JSON replies from `/api`, the standard error shape, and no tracebacks or SQL in responses.

### Bugs found and fixed

Each one now has a regression test in `test_api_contract.py`.

| # | Input | Before | Cause | Fix |
|---|---|---|---|---|
| 1 | `?page=100000000000000000000` on any list | **500** | The SQL OFFSET overflowed | Page number capped at 100,000, giving 422 |
| 2 | `stock-movements?to=9999-12-31` | **500** | Adding one day to the last possible date overflowed | The range now ends at 23:59:59 of `to`, with no date arithmetic |
| 3 | Stock increases past about 2.1 billion | **500** | MySQL INT overflow | Stock is capped at 1,000,000,000, giving 409 `stock_limit_exceeded` |
| 4 | Order of 1,000,000 × 9,999,999.99 | **500** | The total did not fit `DECIMAL(12,2)` | Line amounts and subtotal are checked against the column maximum, giving 422 |
| 5 | Any unexpected error | 500 body showed `"request_id": "-"` | The 500 handler runs after the request-id middleware has finished | The id is kept on the request, returned in the body and the `X-Request-ID` header, and logged with the traceback |
| 6 | Name containing `\x00`, tab or newline (API or CSV) | Accepted | No control-character check | All request text fields reject control characters, giving 422 |
| 7 | Price `"1_000"`, `"1e2"` | Accepted as 1000 and 100 | Python's `Decimal` parses these forms | Money and discount text must be a plain number such as `1500.50` |
| 8 | Order date `0001-01-01` | Accepted | No lower bound | Order date must be on or after 2000-01-01 |
| 9 | `HEAD /api/health` | 405 | Only GET was routed | Health answers GET and HEAD |

Bugs found earlier, during development, are listed in `AI_USAGE.md`.

### Accepted by design

- Whitespace around values (`" 100 "`) is trimmed everywhere.
- `-0` is stored as `0.00`.
- A trailing slash in a URL redirects to the canonical path.
- `OPTIONS` returns 405 because cross-origin use is not supported.
- Injection and HTML strings are stored as plain text. Queries are parameterised, and the UI renders all data with `textContent`, never `innerHTML`.

## Concurrency proof

The concurrency tests send real simultaneous requests using `threading.Barrier`. To confirm they really guard the code, the product row lock was **removed temporarily**. The tests then failed every time (stock went negative, or stock was deducted twice), and passed again once the lock was restored. See `docs/CONCURRENCY.md` for the locking design.
