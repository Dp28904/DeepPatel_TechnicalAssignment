"""Page/page_size query parameters and a generic paginated response."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def paginate(
    db: Session,
    statement: Select,
    params: PageParams,
    transform: Callable[[Any], Any] = lambda row: row,
) -> dict:
    """Run ``statement`` for one page and count the total matching rows."""
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.offset(params.offset).limit(params.page_size)).unique().all()
    return {
        "items": [transform(row) for row in rows],
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if total else 0,
    }
