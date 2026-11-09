"""Database engine, session factory and the declarative base for all models.

Transactions are owned by the service layer: a service calls ``session.commit()``
once at the end of a unit of work, and any exception rolls everything back.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Predictable constraint names, so migrations and error messages are stable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (MySQL DATETIME has no time zone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def connect_args() -> dict:
    """Driver options: verified TLS when DATABASE_SSL_CA is set (hosted MySQL)."""
    ca_path = get_settings().database_ssl_ca
    return {"ssl": {"ca": ca_path}} if ca_path else {}


engine = create_engine(
    get_settings().database_url,
    connect_args=connect_args(),
    pool_pre_ping=True,  # drop dead connections instead of failing a request
    pool_recycle=3600,
    isolation_level="REPEATABLE READ",  # InnoDB default, stated explicitly
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    """Run one unit of work atomically: commit if the block succeeds, roll back on any error.

    It first ends any earlier read-only transaction in this request (for example the
    one that loaded the logged-in user). With MySQL's REPEATABLE READ, a transaction's
    snapshot is taken at its first plain read. Starting fresh and locking rows first
    means that snapshot is taken *after* our locks are held, so data protected by
    those locks is current.
    """
    db.commit()
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()  # undo everything and release all row locks
        raise


def ping_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


# MySQL error codes raised when row locks collide.
MYSQL_LOCK_WAIT_TIMEOUT = 1205
MYSQL_DEADLOCK = 1213


def is_lock_conflict(exc: OperationalError) -> bool:
    code = exc.orig.args[0] if exc.orig is not None and exc.orig.args else None
    return code in (MYSQL_LOCK_WAIT_TIMEOUT, MYSQL_DEADLOCK)
