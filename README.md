# Sales Order & Inventory Management

A web application for a small trading company to manage customers, products, multi-item sales
orders and stock. Built for the Savyant Systems Fresher / Trainee Software Developer technical
assignment.

> **Status:** work in progress. This README grows as each feature lands; the final version
> lists every assumption and known limitation.

## Tech stack

| Area | Choice |
|---|---|
| Runtime | Python 3.12 |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | MySQL 8.4 (Docker Compose) |
| Frontend | Server-rendered HTML (Jinja2) + plain JavaScript (`fetch`) + CSS |
| Tests | pytest, httpx TestClient |
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

## Sample accounts

`python -m db.seed` creates three accounts. Their emails and passwords come from the `SEED_*`
variables in your `.env`; `.env.example` holds placeholders only, so no real credentials are
committed.

| Role | Email (default) | Password |
|---|---|---|
| Admin | `admin@example.com` | value of `SEED_ADMIN_PASSWORD` |
| Sales User | `sales1@example.com` | value of `SEED_SALES1_PASSWORD` |
| Sales User | `sales2@example.com` | value of `SEED_SALES2_PASSWORD` |

An Admin can change a Sales User's name, login email and password on the **Users** page, and their own
name, email and password (current password required) on **My account**. Sales Users cannot change
passwords; they ask an Admin. A password change signs that user out of every other session.

To create more accounts (the password is prompted for and never stored in shell history):

```bash
python -m app.cli create-user --name "Asha Admin" --email asha@example.com --role ADMIN
python -m app.cli create-user --name "Ravi Sales" --email ravi@example.com --role SALES
```

The full DDL is also available as [db/schema.sql](db/schema.sql) (generated from the migrations
with `make schema`).

Shortcuts are available in the [Makefile](Makefile) (`make up`, `make install`, `make run`, `make test`, `make lint`).

## Running tests

```bash
pytest                                   # all tests
pytest --cov=app --cov-report=term       # with coverage
```

Tests run against a separate `sales_test` database, created automatically by the MySQL container.
The schema is built from the real Alembic migrations at the start of each run, and every table is
emptied after each test. As a safety guard, the suite refuses to run unless the database name ends
in `_test`.

## Project structure

```
app/
  core/        shared infrastructure: config, database, errors, logging, security
  modules/     one package per business area (auth, customers, products, orders, ...)
  templates/   Jinja2 page shells
  static/      CSS and JavaScript
migrations/    Alembic migrations
db/            schema.sql export and seed script
sql/           standalone report queries
samples/       sample CSV files for product import
debugging/     debugging exercise (fixed function + tests)
tests/         unit and integration tests
docs/          design and process documentation
```
