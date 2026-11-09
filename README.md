# Sales Order & Inventory Management

A web application for a small trading company to manage customers, products, multi-item sales
orders and stock. It replaces spreadsheets, which caused wrong order totals, stock mismatches
and unreliable sales figures. Built for the Savyant Systems Fresher / Trainee Software Developer
technical assignment.

Users maintain master data, create orders with several products, confirm or cancel them (stock is
deducted and restored safely, even under simultaneous requests), import products from CSV, and
review sales and stock reports.

## Documentation

| Document | Contents |
|---|---|
| This README | Setup, sample accounts, data model, design decisions, assumptions, known limitations |
| [docs/API.md](docs/API.md) | Every endpoint, with real example requests and responses |
| [docs/CONCURRENCY.md](docs/CONCURRENCY.md) | How conflicting stock updates are prevented, and how that is tested |
| [docs/TESTING.md](docs/TESTING.md) | How to run the tests, the Part 12 scenarios, coverage, exploratory testing |
| [docs/DEBUGGING_EXERCISE.md](docs/DEBUGGING_EXERCISE.md) | Part 11: cause, fix and tests for `calculate_total` |
| [sql/queries.sql](sql/queries.sql) | The five standalone SQL queries (Part 9) |
| [AI_USAGE.md](AI_USAGE.md) | Part 14: how AI tools were used and reviewed |

## Tech stack

| Area | Choice |
|---|---|
| Runtime | Python 3.12 |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | MySQL 8.4 (Docker Compose); any MySQL 8.x works |
| Frontend | Server-rendered HTML (Jinja2) + plain JavaScript (`fetch`) + CSS, no framework |
| Passwords | Argon2id via `pwdlib` |
| Tests | pytest, FastAPI TestClient, pytest-cov |
| Lint/format | ruff |

Exact dependency versions are pinned in [requirements.txt](requirements.txt) and
[requirements-dev.txt](requirements-dev.txt).

## Quick start

### Option A: everything in Docker (fastest)

Prerequisites: Docker with Compose v2.

```bash
cp .env.example .env     # then set SECRET_KEY and the sample passwords
docker compose up --build
```

Then open http://localhost:8000. The app container waits for MySQL, applies the migrations and
loads the sample data. Seeding is safe to repeat. Set `SEED_ON_START=false` in `.env` to skip it,
or `APP_PORT` to use another port.

### Option B: run the app locally (development)

Prerequisites: Python 3.12, Docker (or an existing MySQL 8.x server), Git.

```bash
# 1. Configuration
cp .env.example .env          # then set SECRET_KEY and the sample passwords

# 2. Database
docker compose up -d mysql    # starts MySQL 8.4 and creates sales_db + sales_test

# 3. Python environment
python3.12 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 4. Create the tables
alembic upgrade head

# 5. Load sample data (accounts use the SEED_* values from your .env)
python -m db.seed            # add --reset to empty all tables first

# 6. Run, then open http://localhost:8000
uvicorn app.main:app --reload --port 8000
```

Shortcuts are available in the [Makefile](Makefile): `make up`, `make install`, `make migrate`,
`make seed`, `make run`, `make test`, `make cov`, `make lint`, `make schema`.

Interactive API documentation is served at http://localhost:8000/docs while the app runs.

### Option C: public demo on Render (optional)

The app can be deployed to Render from the same `Dockerfile`, with a hosted MySQL (Render has no
MySQL of its own). See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and the Blueprint in
[render.yaml](render.yaml).

## Sample accounts and data

`python -m db.seed` creates three accounts. Their emails and passwords come from the `SEED_*`
variables in your `.env`.

| Role | Email (default) | Password (default in `.env.example`) |
|---|---|---|
| Admin | `admin@example.com` | `admin@123` (`SEED_ADMIN_PASSWORD`) |
| Sales User | `sales1@example.com` | `sales1@123` (`SEED_SALES1_PASSWORD`) |
| Sales User | `sales2@example.com` | `sales2@123` (`SEED_SALES2_PASSWORD`) |

> **These are demo-only sample passwords**, published so the reviewer can log in straight away.
> They are not real credentials and are not used anywhere else. Change them in your `.env` (and
> re-run the seed with `--reset`) before running the application anywhere other than your own
> machine. The real `.env` file is gitignored and never committed.

The seed also loads 8 customers (one inactive, one that has never ordered), 12 products in five
categories (some low-stock, one at zero, one inactive) and 11 orders owned by different users in
every state: confirmed, cancelled after confirming, Draft, cancelled Draft, and a Draft that
cannot be confirmed because of low stock. Orders are created through the real services, so
totals, stock and stock movements are consistent.

To create more accounts (the password is prompted for and never stored in shell history):

```bash
python -m app.cli create-user --name "Asha Admin" --email asha@example.com --role ADMIN
python -m app.cli create-user --name "Ravi Sales" --email ravi@example.com --role SALES
```

An Admin can also add users, and change a Sales User's name, login email and password, on the
**Users** page. Admins change their own details on **My account** (their current password is
required to change it). Sales Users cannot change passwords; they ask an Admin. A password change
signs that user out of every other session.

## Roles and permissions

All permissions are enforced on the server. The UI also hides links a user cannot use, but that
is only a convenience.

| Action | Admin | Sales User |
|---|---|---|
| View customers and products | All, with an active / inactive / all filter | **Active only**; an inactive record returns 404 |
| Create, edit, delete customers and products; adjust stock | Yes | No (403) |
| Create, view, edit, confirm, cancel orders | All orders | **Only orders they created**; anyone else's order returns 404, so changing the id in the URL reveals nothing |
| Reports, CSV import, user management | Yes | No (403) |
| Dashboard | All orders | Own orders |

## Data model

Six tables, created by Alembic migrations ([migrations/versions](migrations/versions)). The full
DDL is also exported to [db/schema.sql](db/schema.sql) (`make schema`).

```
users ─────────────┐ created_by / confirmed_by / cancelled_by
                   ▼
customers ──1:N── sales_orders ──1:N── sales_order_items ──N:1── products
                   │                                              │
                   └──── 0:N ──── stock_movements ──── N:1 ───────┘
                                  (created_by → users)
```

| Table | Key columns | Constraints and indexes |
|---|---|---|
| `users` | name, email, password_hash, role (`ADMIN`/`SALES`), is_active, session_version | `email` UNIQUE |
| `customers` | name, email, mobile, city, is_active | Indexes on name, email, mobile and is_active (the list is searched by those) |
| `products` | code, name, category, price `DECIMAL(12,2)`, stock_quantity `INT`, is_active | `code` UNIQUE; `CHECK (price >= 0)`; `CHECK (stock_quantity >= 0)`; indexes on name, category, is_active |
| `sales_orders` | order_number, customer_id, order_date, status, discount_percent `DECIMAL(5,2)`, subtotal, discount_amount, grand_total `DECIMAL(12,2)`, created_by, confirmed_by/at, cancelled_by/at | `order_number` UNIQUE; `CHECK` discount 0–20; `CHECK` amounts ≥ 0; index on (status, order_date) for reports |
| `sales_order_items` | order_id, product_id, quantity, rate, amount | UNIQUE (order_id, product_id), so a product appears once per order; `CHECK (quantity > 0)`; `CHECK` rate and amount ≥ 0 |
| `stock_movements` | product_id, movement_type, quantity_change, order_id (nullable), reason, created_by, created_at | `CHECK (quantity_change <> 0)`; index on (product_id, created_at) for the history report |

**Foreign keys.** Orders, items and movements reference customers, products and users with
`ON DELETE RESTRICT`, so the database itself refuses to delete referenced master data. Order
items belong to their order (`ON DELETE CASCADE`); orders themselves are never deleted, only
cancelled, and a line removed from a Draft is deleted by the application.

## Key design decisions

**Layered modules.** Each business area is a package in [app/modules](app/modules) with the same
layers:

| File | Responsibility |
|---|---|
| `router.py` | JSON API endpoints: HTTP in and out, no business rules |
| `pages.py` | HTML pages: page access checks only |
| `schemas.py` | Pydantic request and response shapes: input validation |
| `service.py` | Business rules and transactions |
| `repository.py` | SQL queries: no business rules |
| `models.py` | SQLAlchemy tables |

Modules call each other only through `service.py`. Shared infrastructure (configuration, the
database session, error handling, logging, security, money, pagination, constants) lives in
[app/core](app/core).

**The server owns every financial value.** The browser sends only the customer, order date,
discount percentage and `(product, quantity)` pairs. The rate comes from the product's price in
the database; amounts, totals, status and owner are always set by the server. Request bodies
reject unknown fields, so a client that sends `rate`, `grand_total` or `status` gets a 422.

**One calculation, one rounding rule.** All order money is computed in one place,
[app/modules/orders/calculations.py](app/modules/orders/calculations.py), with `Decimal` (never
`float`) and rounded to two decimals with `ROUND_HALF_UP`. Each line amount is rounded first and
the subtotal is their sum, so the printed lines always add up to the printed subtotal. The
order form's live preview uses whole paise in JavaScript with the same rule, but the saved and
displayed figures are always the server's.

**The rate is stored on the order line.** When a product is added to an order, its current
price is copied into `sales_order_items.rate`. Later price changes do not alter existing orders.
When a Draft is edited, lines that remain keep their stored rate; newly added lines take the
current price.

**Every stock change is recorded.** Stock changes in only four places: opening stock (create or
import), Admin adjustment, order confirmation and order cancellation. Each writes one
`stock_movements` row in the same transaction, so the ledger always adds up to the current stock.
Product edits cannot change stock directly.

**Concurrency-safe stock updates.** Confirming, cancelling and adjusting stock lock the affected
rows (`SELECT ... FOR UPDATE`, products in ascending id order to avoid deadlocks), re-check the
order status after the lock, check every line before changing anything, and commit everything in
one transaction. See [docs/CONCURRENCY.md](docs/CONCURRENCY.md).

**Deactivate rather than delete.** Customers and products used by orders (or, for products, by
stock movements) cannot be deleted; the API returns 409 and suggests deactivating instead.
Inactive records stay in history and reports but cannot be added to new orders.

**Clear, consistent errors.** Every API error has the shape
`{"error": {"code", "message", "details"}}` with the right status code (401, 403, 404, 409, 413,
422). Validation errors are plain sentences per field ("Item 2 quantity must be 1 or more.").
Tracebacks only go to the server log; a 500 response carries a request id that matches the log
line.

**Session-based authentication.** A signed, httpOnly, SameSite=Lax cookie holds the user id and a
`session_version`. Every state-changing API call must also send the header
`X-Requested-With: fetch`, which another website cannot add, so cross-site request forgery is
blocked. Changing a password increments `session_version`, which signs out the user's other
sessions.

**Business limits in one place.** Discount range, quantity limits, maximum price, CSV limits and
field lengths are defined once in [app/core/constants.py](app/core/constants.py) and used by
schemas, services and the database constraints.

## Assumptions

- One currency and one stock location. Amounts are shown without a currency symbol.
- Quantities are whole numbers. Order quantities are 1–1,000,000; stock is 0–1,000,000,000.
- Prices are 0–9,999,999.99 with at most two decimals. A price of zero is allowed (for free
  items).
- The discount is a single percentage (0–20, up to two decimals) applied to the order subtotal,
  not to individual lines.
- "Sales" means **Confirmed** orders only. Drafts are not sales yet and Cancelled orders were
  reversed, so reports and the dashboard's sales figures exclude both.
- The low-stock report lists products whose stock is **strictly below** the threshold entered.
- "Customers who have never placed any order" (SQL query 3) means no order in any status, since
  a Draft or Cancelled order was still placed.
- A Draft does not reserve stock. It can be saved for more units than are in stock (the form
  warns); confirmation is refused until stock is available.
- Product codes are case-insensitive and stored upper-case, so `prd-001` and `PRD-001` are the
  same code.
- Customer emails do not have to be unique (one email may serve several branches of a business),
  and email, mobile and city are optional. User login emails are unique.
- The order date defaults to today and cannot be in the future or before 2000-01-01. Business
  dates use the server's local calendar; audit timestamps are stored in UTC.
- A Sales User may cancel their own Confirmed order (the assignment allows Sales Users to manage
  their own orders), which restores the stock.
- CSV files are UTF-8 (an Excel byte-order mark is accepted), at most 1 MB and 5,000 rows.

## Known limitations

- No login rate limiting or account lockout; a production deployment should add it, for example
  at the reverse proxy.
- No self-service "forgot password" flow; an Admin sets a new password for a Sales User.
- Users cannot be deactivated or deleted from the UI or API (the database column exists, and an
  inactive user cannot log in).
- Sessions live in the signed cookie, so logging out clears the cookie in that browser only.
  Other sessions end when the password changes, or when they expire after 8 hours.
- Reports are shown on screen and through the API only; there is no CSV or PDF export.
- The dashboard's low-stock threshold is fixed at 10; the Low Stock report lets you enter any
  threshold.
- The user list is not paginated, which is fine for a small team.
- The order number uses the server's date and the database id (`SO-YYYYMMDD-000123`); numbers
  are unique but can have gaps when a transaction is rolled back.
- The concurrency design relies on InnoDB row locks, so the application requires MySQL (the
  tests run against a real MySQL database, not SQLite).
- The interface is deliberately simple and has not been audited for full accessibility
  compliance.

## Running tests

```bash
docker compose up -d mysql               # the tests need the sales_test database
pytest                                   # all 519 tests (about a minute)
pytest --cov=app --cov=debugging         # with coverage (98%)
pytest -k required                       # only the 9 scenarios required by Part 12
pytest debugging                         # only the debugging exercise (no database needed)
```

Tests run against a separate `sales_test` database, created automatically by the MySQL container.
The schema is built from the real Alembic migrations at the start of each run, and every table is
emptied after each test. As a safety guard, the suite refuses to run unless the database name
ends in `_test`. See [docs/TESTING.md](docs/TESTING.md) for the full list.

## Sample CSV files

| File | Purpose |
|---|---|
| [samples/products_valid.csv](samples/products_valid.csv) | Imports successfully |
| [samples/products_invalid.csv](samples/products_invalid.csv) | Every row problem the importer detects; nothing is imported |
| [samples/test_uploads/](samples/test_uploads/) | 15 extra files for manual testing, numbered `NN_valid_…` or `NN_invalid_…`: flexible header order, edge values (price 0, maximum price, quotes, spaces), a 50-product bulk file, bad headers, row errors, limits, duplicate and existing codes (any letter case), an empty file, a header-only file, a semicolon-separated file and a non-CSV file |

## Project structure

```
app/
  core/        shared infrastructure: config, database, errors, logging, security, money
  modules/     one package per business area:
               auth, users, customers, products, inventory, orders, imports, reports, dashboard
  templates/   Jinja2 pages
  static/      CSS and JavaScript (ES modules)
migrations/    Alembic migrations
db/            schema.sql export and seed script
sql/           standalone report queries
samples/       sample CSV files for product import
debugging/     debugging exercise (original, fix and tests)
docker/        container start-up script
tests/         unit and integration tests
docs/          API, concurrency, testing and debugging documentation
```
