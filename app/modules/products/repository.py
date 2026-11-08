"""Database queries for products. No business rules here."""

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.enums import StatusFilter
from app.modules.products.models import Product


def get(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def get_for_update(db: Session, product_id: int) -> Product | None:
    """Load the product and lock its row until the transaction ends (SELECT ... FOR UPDATE).

    ``populate_existing`` makes sure we read the latest committed values, not a copy
    cached earlier in this session.
    """
    return db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_many(db: Session, product_ids: list[int]) -> dict[int, Product]:
    rows = db.scalars(
        select(Product).where(Product.id.in_(product_ids)).execution_options(populate_existing=True)
    )
    return {product.id: product for product in rows}


def lock_many(db: Session, product_ids: list[int]) -> dict[int, Product]:
    """Lock several product rows, always in ascending id order.

    A fixed lock order means two transactions never hold locks the other is
    waiting for, which is how deadlocks happen.
    """
    rows = db.scalars(
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {product.id: product for product in rows}


def get_by_code(db: Session, code: str) -> Product | None:
    return db.scalar(select(Product).where(Product.code == code))


def _apply_status(statement: Select, status: StatusFilter) -> Select:
    if status == StatusFilter.ACTIVE:
        return statement.where(Product.is_active.is_(True))
    if status == StatusFilter.INACTIVE:
        return statement.where(Product.is_active.is_(False))
    return statement


def search_statement(search: str | None, category: str | None, status: StatusFilter) -> Select:
    statement = select(Product)
    if search:
        term = search.strip()
        statement = statement.where(
            or_(
                Product.code.contains(term, autoescape=True),
                Product.name.contains(term, autoescape=True),
            )
        )
    if category:
        statement = statement.where(Product.category == category.strip())
    return _apply_status(statement, status).order_by(Product.code)


def list_categories(db: Session, status: StatusFilter) -> list[str]:
    statement = _apply_status(select(Product.category).distinct(), status)
    return list(db.scalars(statement.order_by(Product.category)))


def add(db: Session, product: Product) -> Product:
    db.add(product)
    db.flush()
    return product


def delete(db: Session, product: Product) -> None:
    db.delete(product)
    db.flush()
