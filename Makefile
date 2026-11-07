# Convenience shortcuts. Every target has a plain-command equivalent in README.md.
PY ?= .venv/bin/python

.PHONY: install up down migrate seed run test cov lint format schema

install:            ## Create the Python 3.12 virtualenv and install dependencies
	python3.12 -m venv .venv || uv venv --python 3.12 .venv
	$(PY) -m pip install --upgrade pip || true
	$(PY) -m pip install -r requirements-dev.txt || uv pip install --python $(PY) -r requirements-dev.txt

up:                 ## Start MySQL in Docker
	docker compose up -d mysql

down:               ## Stop containers (data volume is kept)
	docker compose down

migrate:            ## Apply database migrations
	$(PY) -m alembic upgrade head

seed:               ## Load sample users, customers, products and orders
	$(PY) -m db.seed

run:                ## Start the dev server on http://localhost:8000
	$(PY) -m uvicorn app.main:app --reload --port 8000

test:               ## Run the full test suite
	$(PY) -m pytest

cov:                ## Run tests with a coverage report
	$(PY) -m pytest --cov=app --cov=debugging --cov-report=term-missing

lint:               ## Lint and check formatting
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:             ## Auto-format and fix lint issues
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

schema:             ## Regenerate db/schema.sql from the Alembic migrations
	$(PY) -m alembic upgrade head --sql > db/schema.sql
