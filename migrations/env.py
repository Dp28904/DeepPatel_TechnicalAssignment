"""Alembic environment.

The database URL comes from, in order:
1. ``-x db_url=...`` on the command line (used by the test suite for sales_test)
2. ``sqlalchemy.url`` set programmatically on the Alembic config
3. ``DATABASE_URL`` from the environment / .env file
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import connect_args
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    return (
        x_args.get("db_url")
        or config.get_main_option("sqlalchemy.url")
        or (get_settings().database_url)
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args(),  # TLS for hosted MySQL, same as the app
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
