"""Database engine, session factory and the declarative base for all models.

Transactions are owned by the service layer: a service calls ``session.commit()``
once at the end of a unit of work, and any exception rolls everything back.
"""

import tempfile
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


def _ca_file_from_text(pem: str) -> str:
    """Write a certificate given as text (DATABASE_SSL_CA_PEM) to a private temp file."""
    text = pem.replace("\\n", "\n").strip() + "\n"  # accept literal "\n" from one-line pastes
    with tempfile.NamedTemporaryFile("w", suffix=".pem", prefix="db-ca-", delete=False) as handle:
        handle.write(text)
    return handle.name


def connect_args() -> dict:
    """Driver options for TLS to a hosted MySQL.

    - CA certificate given: encrypted AND the server's identity is verified (best).
    - Only ssl-mode REQUIRED/PREFERRED: encrypted, identity not verified (like the
      MySQL client's REQUIRED mode).
    - Otherwise: plain connection (local development).
    """
    settings = get_settings()
    if settings.database_ssl_mode == "DISABLED":
        return {}
    if settings.database_ssl_ca_pem:
        return {"ssl": {"ca": _ca_file_from_text(settings.database_ssl_ca_pem)}}
    if settings.database_ssl_ca:
        return {"ssl": {"ca": settings.database_ssl_ca}}
    if settings.database_ssl_mode in ("REQUIRED", "PREFERRED"):
        return {"ssl": {"verify_mode": False}}
    return {}


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


def database_problem() -> str | None:
    """None if the database answers; otherwise a readable reason (password hidden).

    Used at start-up so a failed connection explains itself, e.g. "Access denied for
    user 'avnadmin'" (wrong password) or a TLS certificate error.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return None
    except Exception as exc:  # noqa: BLE001 - every failure must be reported, not raised
        reason = str(getattr(exc, "orig", None) or exc)
        password = engine.url.password
        if password:
            reason = reason.replace(str(password), "***")
        return f"{type(getattr(exc, 'orig', None) or exc).__name__}: {reason}"


def ping_database() -> bool:
    return database_problem() is None


# MySQL error codes raised when row locks collide.
MYSQL_LOCK_WAIT_TIMEOUT = 1205
MYSQL_DEADLOCK = 1213


def is_lock_conflict(exc: OperationalError) -> bool:
    code = exc.orig.args[0] if exc.orig is not None and exc.orig.args else None
    return code in (MYSQL_LOCK_WAIT_TIMEOUT, MYSQL_DEADLOCK)
