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

# 4. Run
uvicorn app.main:app --reload --port 8000
```

Shortcuts are available in the [Makefile](Makefile) (`make up`, `make install`, `make run`, `make test`, `make lint`).

## Running tests

```bash
pytest
```

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
